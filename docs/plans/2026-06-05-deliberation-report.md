# Deliberation Report 기능 구현 계획

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 협의(discussion) 완료 후 `/report` 명령으로 전체 워크플로우 결과를 개괄 형식의 Report로 볼 수 있는 기능 추가

**Architecture:** `DeliberationReport` 모듈을 새로 만들어 `WorkflowSession` + `DeliberationResult` 데이터를 기반으로 Rich Panel/Table 기반의 개괄 Report를 생성. `InteractiveSession`에 `/report` 명령을 추가하고, 자동으로 협의 완료 후에도 Report를 제안.

**Tech Stack:** Python 3.12+, Rich (Panel, Table, Markdown), dataclasses

---

### Task 1: Report 데이터 모델 및 빌더

**Files:**
- Create: `src/trinity/tui/report.py`

**Step 1: Report 데이터 모델 구현**

```python
"""Deliberation report — 개괄 보고서 빌더.

협의 완료 후 /report 명령으로 전체 워크플로우 결과를
구조화된 개괄 형식으로 표시합니다.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

from rich.console import Group
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from trinity.models import ConsensusResult, DeliberationResult
from trinity.tui.theme import get_theme
from trinity.workflow.models import (
    Blueprint,
    DecisionRecord,
    ExecutionResult,
    WorkPackage,
    WorkflowSession,
)


@dataclass(frozen=True)
class ReportMeta:
    """Report 메타데이터."""

    session_id: str
    goal: str
    created_at: float
    duration_seconds: float
    total_tokens: int
    rounds_completed: int
    agents: list[str]


@dataclass(frozen=True)
class ReportConsensus:
    """합의 결과 요약."""

    reached: bool
    agreement_ratio: str  # "2/3"
    summary: str


@dataclass(frozen=True)
class ReportBlueprint:
    """Blueprint 개괄."""

    title: str
    summary: str
    architecture_count: int
    risk_count: int
    data_flow_count: int
    acceptance_criteria_count: int


@dataclass(frozen=True)
class ReportPackage:
    """Work Package 개괄."""

    id: str
    title: str
    owner: str
    status: str
    objective_summary: str  # 최대 120자


@dataclass(frozen=True)
class ReportExecution:
    """실행 결과 개괄."""

    package_id: str
    agent: str
    status: str
    summary: str  # 최대 120자
    files_count: int


@dataclass(frozen=True)
class ReportDecision:
    """사용자 결정 개괄."""

    id: str
    decision: str
    decided_by: str


class DeliberationReportBuilder:
    """협의 결과를 개괄 Report 형식으로 빌드합니다."""

    def __init__(self) -> None:
        pass

    def build(
        self,
        session: WorkflowSession,
        result: DeliberationResult | None = None,
    ) -> DeliberationReport:
        """WorkflowSession + DeliberationResult → DeliberationReport."""
        meta = self._build_meta(session, result)
        consensus = self._build_consensus(session, result)
        blueprint = self._build_blueprint(session)
        packages = self._build_packages(session)
        executions = self._build_executions(session)
        decisions = self._build_decisions(session)
        return DeliberationReport(
            meta=meta,
            consensus=consensus,
            blueprint=blueprint,
            packages=packages,
            executions=executions,
            decisions=decisions,
        )

    def _build_meta(
        self,
        session: WorkflowSession,
        result: DeliberationResult | None,
    ) -> ReportMeta:
        return ReportMeta(
            session_id=session.id,
            goal=session.goal or "(none)",
            created_at=session.created_at,
            duration_seconds=result.duration_seconds if result else 0.0,
            total_tokens=result.total_tokens_used if result else 0,
            rounds_completed=result.rounds_completed if result else session.current_round,
            agents=list(session.active_agents),
        )

    def _build_consensus(
        self,
        session: WorkflowSession,
        result: DeliberationResult | None,
    ) -> ReportConsensus | None:
        if result is None or result.consensus is None:
            return None
        c = result.consensus
        return ReportConsensus(
            reached=c.reached,
            agreement_ratio=(
                f"{c.agreement_count}/{c.total_agents}"
                if c.total_agents > 0
                else "N/A"
            ),
            summary=c.summary or "(no summary)",
        )

    def _build_blueprint(
        self,
        session: WorkflowSession,
    ) -> ReportBlueprint | None:
        bp = session.blueprint
        if bp is None:
            return None
        return ReportBlueprint(
            title=bp.title,
            summary=bp.summary,
            architecture_count=len(bp.architecture),
            risk_count=len(bp.risks),
            data_flow_count=len(bp.data_flow),
            acceptance_criteria_count=len(bp.acceptance_criteria),
        )

    def _build_packages(
        self,
        session: WorkflowSession,
    ) -> list[ReportPackage]:
        packages: list[ReportPackage] = []
        for pkg in session.work_packages:
            objective = pkg.objective
            if len(objective) > 120:
                objective = objective[:117] + "..."
            packages.append(ReportPackage(
                id=pkg.id,
                title=pkg.title,
                owner=pkg.owner_agent,
                status=(
                    pkg.status.value
                    if pkg.requires_execution
                    else "planning_only"
                ),
                objective_summary=objective,
            ))
        return packages

    def _build_executions(
        self,
        session: WorkflowSession,
    ) -> list[ReportExecution]:
        executions: list[ReportExecution] = []
        for ex in session.execution_results:
            summary = ex.summary
            if len(summary) > 120:
                summary = summary[:117] + "..."
            executions.append(ReportExecution(
                package_id=ex.package_id,
                agent=ex.agent_name,
                status=ex.status.value,
                summary=summary,
                files_count=len(ex.files_changed),
            ))
        return executions

    def _build_decisions(
        self,
        session: WorkflowSession,
    ) -> list[ReportDecision]:
        return [
            ReportDecision(
                id=d.id,
                decision=d.decision,
                decided_by=d.decided_by,
            )
            for d in session.decisions
        ]


@dataclass(frozen=True)
class DeliberationReport:
    """협의 결과 개괄 Report."""

    meta: ReportMeta
    consensus: ReportConsensus | None
    blueprint: ReportBlueprint | None
    packages: list[ReportPackage]
    executions: list[ReportExecution]
    decisions: list[ReportDecision]

    def render(self) -> Group:
        """Rich Group으로 렌더링."""
        panels: list[Panel | Table] = []

        # 1. Overview Panel
        panels.append(self._render_overview())

        # 2. Consensus Panel
        if self.consensus:
            panels.append(self._render_consensus())

        # 3. Blueprint Panel
        if self.blueprint:
            panels.append(self._render_blueprint())

        # 4. Decisions Panel
        if self.decisions:
            panels.append(self._render_decisions())

        # 5. Work Packages Table
        if self.packages:
            panels.append(self._render_packages())

        # 6. Execution Results Table
        if self.executions:
            panels.append(self._render_executions())

        return Group(*panels)

    def _render_overview(self) -> Panel:
        """총괄 개요 Panel."""
        duration_str = (
            f"{self.meta.duration_seconds:.1f}s"
            if self.meta.duration_seconds > 0
            else "N/A"
        )
        tokens_str = (
            f"{self.meta.total_tokens:,}"
            if self.meta.total_tokens > 0
            else "N/A"
        )
        created_str = self._format_timestamp(self.meta.created_at)
        agents_str = ", ".join(self.meta.agents) if self.meta.agents else "(none)"

        content = (
            f"[bold]Goal[/bold]: {self.meta.goal}\n"
            f"[bold]Session[/bold]: {self.meta.session_id}\n"
            f"[bold]Created[/bold]: {created_str}\n"
            f"[bold]Agents[/bold]: {agents_str}\n"
            f"[bold]Rounds[/bold]: {self.meta.rounds_completed}\n"
            f"[bold]Duration[/bold]: {duration_str}\n"
            f"[bold]Tokens[/bold]: {tokens_str}"
        )
        return Panel.fit(content, title="📋 Overview", border_style="cyan")

    def _render_consensus(self) -> Panel:
        """합의 결과 Panel."""
        if self.consensus.reached:
            icon = "✅"
            style = "green"
        else:
            icon = "⚠️"
            style = "yellow"
        ratio = self.consensus.agreement_ratio
        content = (
            f"[{style} bold]{icon} "
            f"{'Consensus Reached' if self.consensus.reached else 'No Consensus'}"
            f"[/{style} bold] ({ratio})\n\n"
            f"{self.consensus.summary}"
        )
        return Panel.fit(
            content,
            title="🤝 Consensus",
            border_style=style,
        )

    def _render_blueprint(self) -> Panel:
        """Blueprint 개괄 Panel."""
        bp = self.blueprint
        lines = [
            f"[bold]{bp.title}[/bold]\n",
            f"{bp.summary}\n",
            f"  🏗 Architecture: {bp.architecture_count} components",
            f"  📊 Data Flow: {bp.data_flow_count} steps",
            f"  ⚠ Risks: {bp.risk_count} identified",
            f"  ✅ Acceptance Criteria: {bp.acceptance_criteria_count} items",
        ]
        return Panel.fit(
            "\n".join(lines),
            title="📐 Blueprint",
            border_style="magenta",
        )

    def _render_decisions(self) -> Panel:
        """사용자 결정 개괄."""
        lines: list[str] = []
        for d in self.decisions:
            lines.append(
                f"  [cyan]{d.id}[/cyan] → {d.decision} "
                f"[dim](by {d.decided_by})[/dim]"
            )
        return Panel.fit(
            "\n".join(lines),
            title="📝 Decisions",
            border_style="blue",
        )

    def _render_packages(self) -> Table:
        """Work Packages 테이블."""
        table = Table(title="📦 Work Packages")
        table.add_column("ID", style="cyan", max_width=16)
        table.add_column("Title", max_width=30)
        table.add_column("Owner", max_width=12)
        table.add_column("Status", max_width=14)
        table.add_column("Objective", max_width=40)

        for pkg in self.packages:
            theme = get_theme(pkg.owner)
            owner = f"[{theme.color}]{theme.icon} {pkg.owner}[/{theme.color}]"
            table.add_row(pkg.id, pkg.title, owner, pkg.status, pkg.objective_summary)

        return table

    def _render_executions(self) -> Table:
        """실행 결과 테이블."""
        table = Table(title="🛠 Execution Results")
        table.add_column("Package", style="cyan", max_width=16)
        table.add_column("Agent", max_width=12)
        table.add_column("Status", max_width=12)
        table.add_column("Files", justify="right", max_width=6)
        table.add_column("Summary", max_width=50)

        for ex in self.executions:
            theme = get_theme(ex.agent)
            agent = f"[{theme.color}]{theme.icon} {ex.agent}[/{theme.color}]"
            table.add_row(
                ex.package_id,
                agent,
                ex.status,
                str(ex.files_count),
                ex.summary,
            )

        return table

    @staticmethod
    def _format_timestamp(timestamp: float) -> str:
        try:
            return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(timestamp))
        except (OSError, ValueError):
            return "unknown"

    def to_markdown(self) -> str:
        """Markdown 형식으로 출력 (파일 저장용)."""
        lines: list[str] = []
        lines.append(f"# Deliberation Report")
        lines.append("")
        lines.append(f"## Overview")
        lines.append(f"- **Goal**: {self.meta.goal}")
        lines.append(f"- **Session**: {self.meta.session_id}")
        lines.append(
            f"- **Created**: {self._format_timestamp(self.meta.created_at)}"
        )
        lines.append(f"- **Agents**: {', '.join(self.meta.agents)}")
        lines.append(f"- **Rounds**: {self.meta.rounds_completed}")
        lines.append(
            f"- **Duration**: {self.meta.duration_seconds:.1f}s"
            if self.meta.duration_seconds > 0
            else "- **Duration**: N/A"
        )
        lines.append(
            f"- **Tokens**: {self.meta.total_tokens:,}"
            if self.meta.total_tokens > 0
            else "- **Tokens**: N/A"
        )
        lines.append("")

        if self.consensus:
            status = (
                "Consensus Reached" if self.consensus.reached
                else "No Consensus"
            )
            lines.append(f"## Consensus: {status}")
            lines.append(
                f"- Agreement: {self.consensus.agreement_ratio}"
            )
            lines.append(f"- Summary: {self.consensus.summary}")
            lines.append("")

        if self.blueprint:
            bp = self.blueprint
            lines.append(f"## Blueprint: {bp.title}")
            lines.append(f"- Summary: {bp.summary}")
            lines.append(f"- Architecture: {bp.architecture_count} components")
            lines.append(f"- Data Flow: {bp.data_flow_count} steps")
            lines.append(f"- Risks: {bp.risk_count} identified")
            lines.append(
                f"- Acceptance Criteria: {bp.acceptance_criteria_count} items"
            )
            lines.append("")

        if self.decisions:
            lines.append("## Decisions")
            for d in self.decisions:
                lines.append(
                    f"- **{d.id}**: {d.decision} (by {d.decided_by})"
                )
            lines.append("")

        if self.packages:
            lines.append("## Work Packages")
            lines.append("| ID | Title | Owner | Status | Objective |")
            lines.append("|---|---|---|---|---|")
            for pkg in self.packages:
                lines.append(
                    f"| {pkg.id} | {pkg.title} | {pkg.owner} "
                    f"| {pkg.status} | {pkg.objective_summary} |"
                )
            lines.append("")

        if self.executions:
            lines.append("## Execution Results")
            lines.append("| Package | Agent | Status | Files | Summary |")
            lines.append("|---|---|---|---|---|")
            for ex in self.executions:
                lines.append(
                    f"| {ex.package_id} | {ex.agent} | {ex.status} "
                    f"| {ex.files_count} | {ex.summary} |"
                )
            lines.append("")

        return "\n".join(lines)
```

**Step 2: 커밋**

```bash
git add src/trinity/tui/report.py
git commit -m "feat: add DeliberationReport builder and renderer module"
```

---

### Task 2: InteractiveSession에 /report 명령 추가

**Files:**
- Modify: `src/trinity/tui/session.py:182-239` (`_handle_command` 메서드)
- Modify: `src/trinity/tui/session.py` (새 `_cmd_report` 메서드 추가)
- Modify: `src/trinity/tui/session.py:980-999` (`_display_result` 이후 report 제안)

**Step 1: `_handle_command`에 `report` 명령 분기 추가**

`src/trinity/tui/session.py`의 `_handle_command` 메서드에서 `elif cmd == "subtasks":` 이후에 추가:

```python
        elif cmd == "report":
            self._cmd_report(args)
```

**Step 2: `_cmd_report` 메서드 구현**

`_cmd_subtasks` 메서드 이후에 추가:

```python
    def _cmd_report(self, args: list[str]) -> None:
        """협의 결과를 개괄 Report 형식으로 표시.

        Usage:
            /report          — TUI에 Rich 형식으로 표시
            /report save     — Markdown 파일로 저장
        """
        from trinity.tui.report import DeliberationReportBuilder

        result = self.tui.last_result
        session = self.workflow.session
        if not session.goal and result is None:
            self.console.print(
                "[yellow]아직 협의 결과가 없습니다. "
                "먼저 질문을 입력해 협의를 시작하세요.[/yellow]"
            )
            return

        builder = DeliberationReportBuilder()
        report = builder.build(session, result)

        save_requested = args and args[0].lower() in ("save", "s")
        if save_requested:
            self._save_report_markdown(report)
        else:
            self.console.print(report.render())
            self.console.print(
                "\n[dim]/report save 로 Markdown 파일로 저장할 수 있습니다.[/dim]"
            )

    def _save_report_markdown(self, report) -> None:
        """Report를 Markdown 파일로 저장."""
        report_dir = self.config.effective_state_dir / "reports"
        report_dir.mkdir(parents=True, exist_ok=True)
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        filename = f"report-{report.meta.session_id[:8]}-{timestamp}.md"
        filepath = report_dir / filename
        filepath.write_text(report.to_markdown(), encoding="utf-8")
        self.console.print(
            f"[green]📋 Report 저장 완료: {filepath}[/green]"
        )
```

**Step 3: `_display_result` 이후에 report 안내 메시지 추가**

`_display_result` 메서드 마지막에 다음 줄 추가 (duration/tokens 출력 직후):

```python
        self.console.print(
            "[dim]/report 로 전체 협의 결과 개괄 보기, "
            "/report save 로 파일 저장[/dim]"
        )
```

**Step 4: `_show_welcome`의 help 메시지에 `/report` 추가**

이미 `/help` 명령이 `get_welcome_text()`를 사용하므로, TUI 앱의 웰컴 텍스트에 `/report` 명령 설명을 추가해야 함. `src/trinity/tui/app.py`의 `get_welcome_text` 메서드를 확인 후 `/report` 추가.

**Step 5: 커밋**

```bash
git add src/trinity/tui/session.py
git commit -m "feat: add /report command to interactive session"
```

---

### Task 3: TUI welcome/help에 /report 추가

**Files:**
- Modify: `src/trinity/tui/app.py` (`get_welcome_text` 메서드)

**Step 1: `get_welcome_text`에서 명령 목록에 `/report` 추가**

`src/trinity/tui/app.py`의 `get_welcome_text` 메서드에서 명령 목록에 다음 항목 추가:

```
  /report          협의 결과 개괄 보고서
  /report save     보고서를 Markdown 파일로 저장
```

**Step 2: 커밋**

```bash
git add src/trinity/tui/app.py
git commit -m "feat: add /report to help text"
```

---

### Task 4: 단위 테스트 작성

**Files:**
- Create: `tests/test_report.py`

**Step 1: 테스트 작성**

```python
"""Tests for deliberation report builder and renderer."""

import time

from trinity.models import ConsensusResult, DeliberationResult
from trinity.tui.report import DeliberationReportBuilder, DeliberationReport
from trinity.workflow.models import (
    Blueprint,
    DecisionRecord,
    ExecutionResult,
    WorkPackage,
    WorkflowSession,
    WorkflowState,
    WorkStatus,
    ArchitectureComponent,
    RiskItem,
)


def _sample_session() -> WorkflowSession:
    return WorkflowSession(
        id="test-session-001",
        goal="인증 시스템 설계",
        state=WorkflowState.BLUEPRINT_READY,
        active_agents=["claude", "codex", "antigravity"],
        current_round=3,
        blueprint=Blueprint(
            title="JWT 인증 시스템",
            summary="JWT 기반 인증 설계",
            architecture=[
                ArchitectureComponent(
                    name="AuthController",
                    responsibility="인증 요청 처리",
                    owner_agent="codex",
                ),
            ],
            data_flow=["Client → AuthController → TokenService"],
            risks=[
                RiskItem(
                    description="토큰 만료 처리 누락",
                    severity="high",
                    mitigation="자동 갱신 로직 추가",
                ),
            ],
            acceptance_criteria=["로그인/로그아웃 동작"],
        ),
        work_packages=[
            WorkPackage(
                id="wp-001",
                title="인증 컨트롤러 구현",
                owner_agent="codex",
                objective="JWT 인증 컨트롤러 및 미들웨어 구현",
                status=WorkStatus.DONE,
            ),
        ],
        execution_results=[
            ExecutionResult(
                package_id="wp-001",
                agent_name="codex",
                status=WorkStatus.DONE,
                summary="인증 컨트롤러 구현 완료",
                files_changed=["src/auth/controller.py", "src/auth/middleware.py"],
            ),
        ],
        decisions=[
            DecisionRecord(
                id="dec-001",
                decision="JWT 사용",
                decided_by="user",
            ),
        ],
        created_at=time.time(),
    )


def _sample_result() -> DeliberationResult:
    return DeliberationResult(
        user_prompt="인증 시스템 설계",
        rounds_completed=3,
        consensus=ConsensusResult(
            reached=True,
            agreement_count=3,
            total_agents=3,
            opinions={"claude": "approve", "codex": "approve", "antigravity": "approve"},
            summary="JWT 기반 인증 시스템 설계에 합의",
        ),
        total_tokens_used=15000,
        duration_seconds=45.3,
    )


def test_report_builds_from_session_and_result():
    builder = DeliberationReportBuilder()
    report = builder.build(_sample_session(), _sample_result())
    assert report.meta.session_id == "test-session-001"
    assert report.meta.goal == "인증 시스템 설계"
    assert report.meta.rounds_completed == 3
    assert report.meta.total_tokens == 15000
    assert len(report.meta.agents) == 3


def test_report_consensus():
    builder = DeliberationReportBuilder()
    report = builder.build(_sample_session(), _sample_result())
    assert report.consensus is not None
    assert report.consensus.reached is True
    assert report.consensus.agreement_ratio == "3/3"


def test_report_blueprint():
    builder = DeliberationReportBuilder()
    report = builder.build(_sample_session(), _sample_result())
    assert report.blueprint is not None
    assert report.blueprint.title == "JWT 인증 시스템"
    assert report.blueprint.architecture_count == 1
    assert report.blueprint.risk_count == 1


def test_report_packages():
    builder = DeliberationReportBuilder()
    report = builder.build(_sample_session(), _sample_result())
    assert len(report.packages) == 1
    assert report.packages[0].id == "wp-001"
    assert report.packages[0].owner == "codex"


def test_report_executions():
    builder = DeliberationReportBuilder()
    report = builder.build(_sample_session(), _sample_result())
    assert len(report.executions) == 1
    assert report.executions[0].files_count == 2


def test_report_decisions():
    builder = DeliberationReportBuilder()
    report = builder.build(_sample_session(), _sample_result())
    assert len(report.decisions) == 1
    assert report.decisions[0].decision == "JWT 사용"


def test_report_render_does_not_raise():
    builder = DeliberationReportBuilder()
    report = builder.build(_sample_session(), _sample_result())
    # render() should produce a Rich Group without errors
    group = report.render()
    assert group is not None


def test_report_to_markdown():
    builder = DeliberationReportBuilder()
    report = builder.build(_sample_session(), _sample_result())
    md = report.to_markdown()
    assert "# Deliberation Report" in md
    assert "인증 시스템 설계" in md
    assert "JWT 인증 시스템" in md
    assert "Consensus Reached" in md


def test_report_without_result():
    builder = DeliberationReportBuilder()
    report = builder.build(_sample_session(), result=None)
    assert report.meta.total_tokens == 0
    assert report.consensus is None


def test_report_empty_session():
    session = WorkflowSession(
        id="empty-session",
        goal="",
        state=WorkflowState.IDLE,
    )
    builder = DeliberationReportBuilder()
    report = builder.build(session, result=None)
    assert report.meta.goal == "(none)"
    assert report.consensus is None
    assert report.blueprint is None
    assert report.packages == []
    assert report.executions == []
    assert report.decisions == []


def test_long_objective_truncated():
    session = WorkflowSession(
        id="trunc-session",
        goal="test",
        state=WorkflowState.BLUEPRINT_READY,
        work_packages=[
            WorkPackage(
                id="wp-long",
                title="Long",
                owner_agent="codex",
                objective="x" * 200,
                status=WorkStatus.PENDING,
            ),
        ],
    )
    builder = DeliberationReportBuilder()
    report = builder.build(session, result=None)
    assert len(report.packages[0].objective_summary) <= 120
```

**Step 2: 테스트 실행**

Run: `cd /Users/identity/dev/project/Trinity && python -m pytest tests/test_report.py -v`
Expected: 모든 테스트 PASS

**Step 3: 커밋**

```bash
git add tests/test_report.py
git commit -m "test: add deliberation report builder tests"
```

---

### Task 5: 통합 테스트 및 최종 검증

**Step 1: 전체 테스트 스위트 실행**

Run: `cd /Users/identity/dev/project/Trinity && python -m pytest -v`
Expected: 기존 테스트 + 새 테스트 모두 PASS

**Step 2: import 체인 검증**

Run: `python -c "from trinity.tui.report import DeliberationReportBuilder; print('OK')"`
Expected: OK

**Step 3: 최종 커밋**

```bash
git add -A
git commit -m "feat: deliberation report feature complete"
```
