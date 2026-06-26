"""Pure presentation helpers for Textual workflow snapshots."""

from __future__ import annotations

from dataclasses import dataclass
from difflib import get_close_matches
from typing import Mapping, Protocol, Sequence

from trinity.slash_commands import COMMAND_SPECS, SESSION_ONLY_SETTING_NOTICE
from trinity.display_labels import display_kind_value, display_severity_value
from trinity.textual_app.snapshot import WorkflowNexusSnapshot
from trinity.textual_app.widgets.status_label import (
    display_consensus_progress,
    display_readiness_value,
    display_review_status_value,
    display_status_value,
)

NO_CURRENT_CONTEXT_MESSAGE = (
    "No current session context. Start a prompt or resume a workflow first."
)


class AgentRowSpec(Protocol):
    """Small presenter-facing subset of an agent spec."""

    enabled: bool
    provider: object


STATUS_CONTEXT_LABELS = {
    "en": {
        "answer": "Answer",
        "answer_inspect_questions_hint": "Run `/questions` to inspect pending questions first.",
        "answer_usage": "Usage: /answer <question-id|index|next> <answer>",
        "artifact": "Artifact",
        "artifact_usage": "Usage: `/artifact <memory-id>`",
        "ask": "Ask",
        "attempts": "attempts",
        "ask_missing_model": "Missing model after --model.",
        "ask_no_active_agents": "No active agents are available for /ask.",
        "ask_prompt_empty": "Prompt cannot be empty.",
        "ask_unknown_agent": "Unknown or disabled agent",
        "ask_usage": "Usage: /ask <all|agent[,agent...]> [--model MODEL] <prompt>",
        "agent": "Agent",
        "agent_change_hint": "Use `/agent <name> on|off` to change one agent.",
        "agent_current_settings": "Current agent session settings.",
        "agent_disabled": "disabled",
        "agent_enabled": "enabled",
        "agent_usage": "Usage: `/agent <name> on|off`",
        "agent_unknown": "Unknown agent",
        "allowed": "Allowed",
        "caveman": "Caveman",
        "caveman_allowed_modes": "Allowed modes: on, off, lite, full, ultra.",
        "caveman_change_hint": "Use `/caveman <mode>` to change it for this session.",
        "caveman_set": "Caveman set",
        "caveman_usage": "Use: /caveman [on|off|lite|full|ultra]",
        "categories": "Categories",
        "category": "Category",
        "central": "central",
        "command": "Command",
        "continue_until_question": "Continue planning until the central agent raises a question.",
        "context": "Context",
        "context_no_current": NO_CURRENT_CONTEXT_MESSAGE,
        "control_repo_confirmed": "Control repo confirmed",
        "current_max_rounds": "Current max rounds",
        "current_target": "Current target",
        "decision": "Decision",
        "decision_hint": "Answer pending questions with `/answer` to add decisions.",
        "decisions": "Decisions",
        "done_packages": "Done packages",
        "delegated_to": "Delegated To",
        "enabled": "Enabled",
        "execution": "Execution",
        "execute": "Execute",
        "execute_finish_planning_hint": "Finish planning first, then run `/execute` from Nexus.",
        "execute_retry": "Execute Retry",
        "execute_retry_no_packages": (
            "No work packages are available in the current workflow."
        ),
        "execute_retry_no_packages_hint": (
            "Finish planning and execute at least one package first."
        ),
        "execute_recovery_hint": (
            "Use `/execute-retry`, `/execute mark-interrupted`, or `/execute abort`."
        ),
        "execution_log_entries": "Execution log entries",
        "execution_recovery": "Execution Recovery",
        "execution_recovery_none": "No interrupted execution is recorded for this workflow.",
        "execution_results": "Execution Results",
        "final_review": "Final Review",
        "follow_up_requests": "Follow-up Requests",
        "goal": "Goal",
        "help_agent_call": "Agent Call",
        "help_exact_hint": (
            "Use Tab to complete a command without running it. "
            "Use Enter to run an exact command."
        ),
        "help_intro_agent": "Local UI, settings, and file commands do not call agents.",
        "help_intro_trinity": (
            "Trinity-owned slash commands are handled before provider prompts."
        ),
        "history_hint": "Run a prompt, execute a workflow, or use local slash commands first.",
        "history": "History",
        "id": "ID",
        "improve_hint": (
            "Use `/improve high`, `/improve all`, `/improve AI-001`, "
            "or `/improve done`."
        ),
        "improve": "Improve",
        "inside_control_repo": "Inside control repo",
        "intensity": "Intensity",
        "item": "Item",
        "kind": "Kind",
        "last_event": "Last event",
        "local_command": "Local command",
        "local_policy_repairs": "Local Policy Repairs",
        "memory_cleanup": "Memory Cleanup",
        "memory_cleanup_keep_latest_number": "--keep-latest requires a number.",
        "memory_cleanup_keep_latest_range": "--keep-latest must be 0 or greater.",
        "memory_cleanup_unknown_option": "Unknown cleanup option",
        "memory_cleanup_usage": (
            "Usage: `/memory cleanup --oversized-backups "
            "[--apply] [--keep-latest N]`"
        ),
        "memory_compact": "Memory Compact",
        "memory_stats": "Memory Stats",
        "model_settings": "Model Settings",
        "model_settings_unavailable": "Model settings are available on Start and Nexus.",
        "model_settings_updated": "Model settings updated.",
        "mode": "Mode",
        "next": "Next",
        "no": "no",
        "no_decisions": "No workflow decisions recorded in the current session.",
        "none": "(none)",
        "no_history": "No local history recorded in this Textual session.",
        "no_packages": "No workflow work packages generated in the current session.",
        "no_pending_questions": "No pending workflow questions.",
        "no_pending_questions_select": "No pending workflow questions to select.",
        "no_predefined_options": "This question has no predefined options.",
        "no_subtasks": "No provider delegation subtasks recorded in the current session.",
        "no_goal": "(no goal)",
        "new_workflow": "(new)",
        "no_package": "(no package)",
        "not_set": "(not set)",
        "not_checked": "not checked",
        "options": "Options",
        "package": "Package",
        "packages": "Packages",
        "packages_hint": "Finish planning until a blueprint or local WP graph is generated.",
        "path": "Path",
        "pending_questions": "Pending questions",
        "pending_wp_review": "Pending WP review",
        "post_review_action_items": "Post Review Action Items",
        "post_review_items": "Post-review items",
        "action_items": "Action items",
        "provider": "Provider",
        "questions": "Questions",
        "question": "Question",
        "question_hint": "Use question panel buttons or `/answer <id|index|next> <answer>`.",
        "question_answer_usage": "Use `/answer <id|index|next> <answer>`.",
        "question_select_hint": (
            "Use the option buttons in the question panel, "
            "or run `/answer <option-number>`."
        ),
        "readiness": "Readiness",
        "recent_execution_log": "Recent Execution Log",
        "recent_local_items": "Recent Local Items",
        "recent_repair_notes": "Recent repair notes",
        "recommended": "Recommended",
        "reattach_note": (
            "Provider process reattach is not supported. Retry starts a new "
            "one-shot execution only for interrupted, failed, or blocked packages."
        ),
        "recovery": "(recovery)",
        "report": "Report",
        "report_export_complete": "Export Complete",
        "report_export_hint": "Start or resume a workflow before exporting a report.",
        "report_export_unavailable": "Export Unavailable",
        "report_no_export_data": "No workflow data available to export.",
        "report_no_open_data": "No workflow data available for a report.",
        "report_open_hint": "Start or resume a workflow before opening a report.",
        "report_opened": "Report screen opened.",
        "report_saved": "Report saved",
        "resume": "Resume",
        "resume_archives_available": "Saved workflow sessions available to resume.",
        "resume_cancel_hint": "Run `/resume` again to choose an archived workflow.",
        "resume_cancelled": "Resume selection cancelled.",
        "resume_empty_hint": "Start and archive a workflow before using `/resume`.",
        "resume_no_saved": "No saved workflow sessions to resume.",
        "resume_pick_hint": "Pick a workflow from the resume modal.",
        "retry_candidates": "Retry candidates",
        "review_repair": "Review Repair",
        "review_repair_action_hint": (
            "Choose Retry once, Mark done, or Stop from the central panel."
        ),
        "review_repair_none": (
            "No review-repair blocked work packages are recorded."
        ),
        "review_repair_paused": (
            "Review-repair loop guard has paused these work packages:"
        ),
        "repair_state": "Repair state",
        "review": "review",
        "review_title": "Review",
        "review_hint": "Run `/review wp`, `/review final`, or `/review all`.",
        "reviewed_wp": "Reviewed WP",
        "reviewer": "reviewer",
        "round": "Round",
        "rounds": "Rounds",
        "rounds_allowed_range": "Allowed range",
        "rounds_change_hint": "Use `/rounds <1..20>` to change it for this session.",
        "rounds_invalid_number": "Invalid number.",
        "rounds_range_error": "Rounds must be between 1 and 20.",
        "rounds_set": "Max rounds set",
        "rounds_usage": "Use `/rounds <1..20>`.",
        "run": "Run",
        "save": "Save",
        "save_auto_persist_body": (
            "Textual workflows are persisted automatically. "
            "Use /report save for Markdown export."
        ),
        "slash_command": "Slash Command",
        "severity": "severity",
        "source": "Source",
        "running_packages": "Running packages",
        "running_packages_at_exit": "Running packages at exit",
        "selector": "Selector",
        "state": "State",
        "status": "Status",
        "summary": "Summary",
        "subtasks": "Subtasks",
        "subtasks_hint": "Subtasks appear after an executing provider reports delegated work.",
        "supplemental_rounds": "Supplemental rounds",
        "synthesis": "Synthesis",
        "syntax_error": "Syntax Error",
        "target": "Target",
        "target_action_hint": "Use `/target <path>` or Select Workspace before execution.",
        "target_cleared": "Target workspace cleared.",
        "target_control_repo_hint": "Choose a workspace outside the Trinity control repo.",
        "target_not_directory": "Target path exists but is not a directory",
        "target_preflight_cancelled": "Workspace preflight cancelled.",
        "target_prepare_failed": "Could not prepare target workspace",
        "target_selection_cancelled": "Target workspace selection cancelled.",
        "target_workspace": "Target workspace",
        "title": "title",
        "value": "Value",
        "workflow": "Workflow",
        "workflow_history": "Workflow History",
        "work_packages": "Work Packages",
        "local": "local",
        "trinity_commands": "Trinity Commands",
        "unnamed": "(unnamed)",
        "unknown_command": "Unknown Command",
        "unknown_command_body": "is not a Trinity slash command.",
        "unknown_command_did_you_mean": "Did you mean:",
        "unknown_command_help": "Run `/help` to see Trinity-owned commands.",
        "unknown": "(unknown)",
        "suggestion": "Suggestion",
        "yes": "yes",
        "selected_question": "Selected question",
        "free_text": "(free text)",
    },
    "ko": {
        "answer": "답변",
        "answer_inspect_questions_hint": (
            "먼저 `/questions`를 실행해 대기 중인 질문을 확인하세요."
        ),
        "answer_usage": "사용법: /answer <question-id|index|next> <answer>",
        "artifact": "아티팩트",
        "artifact_usage": "사용법: `/artifact <memory-id>`",
        "ask": "질문",
        "attempts": "시도",
        "ask_missing_model": "--model 뒤에 모델을 입력하세요.",
        "ask_no_active_agents": "/ask에 사용할 활성 에이전트가 없습니다.",
        "ask_prompt_empty": "프롬프트를 입력하세요.",
        "ask_unknown_agent": "알 수 없거나 비활성화된 에이전트",
        "ask_usage": "사용법: /ask <all|agent[,agent...]> [--model MODEL] <prompt>",
        "agent": "에이전트",
        "agent_change_hint": "`/agent <name> on|off`로 에이전트 하나를 변경하세요.",
        "agent_current_settings": "현재 에이전트 세션 설정입니다.",
        "agent_disabled": "비활성화",
        "agent_enabled": "활성화",
        "agent_usage": "사용법: `/agent <name> on|off`",
        "agent_unknown": "알 수 없는 에이전트",
        "allowed": "허용값",
        "caveman": "간결 모드",
        "caveman_allowed_modes": "허용 모드: on, off, lite, full, ultra.",
        "caveman_change_hint": "`/caveman <mode>`로 이 세션의 값을 변경하세요.",
        "caveman_set": "간결 모드 설정",
        "caveman_usage": "사용법: /caveman [on|off|lite|full|ultra]",
        "categories": "카테고리",
        "category": "카테고리",
        "central": "중앙",
        "command": "명령",
        "continue_until_question": "중앙 에이전트가 질문을 만들 때까지 계획을 계속 진행하세요.",
        "context": "컨텍스트",
        "context_no_current": "현재 세션 컨텍스트가 없습니다. 먼저 프롬프트를 시작하거나 워크플로우를 재개하세요.",
        "control_repo_confirmed": "제어 저장소 확인",
        "current_max_rounds": "현재 최대 라운드",
        "current_target": "현재 대상",
        "decision": "결정",
        "decision_hint": "대기 중인 질문에 `/answer`로 답하면 결정이 추가됩니다.",
        "decisions": "결정",
        "done_packages": "완료 작업 패키지",
        "delegated_to": "위임 대상",
        "enabled": "활성화",
        "execution": "실행",
        "execute": "실행",
        "execute_finish_planning_hint": "먼저 계획을 완료한 뒤 Nexus에서 `/execute`를 실행하세요.",
        "execute_retry": "실행 재시도",
        "execute_retry_no_packages": (
            "현재 워크플로우에 사용할 수 있는 작업 패키지가 없습니다."
        ),
        "execute_retry_no_packages_hint": (
            "먼저 계획을 완료하고 하나 이상의 작업 패키지를 실행하세요."
        ),
        "execute_recovery_hint": (
            "`/execute-retry`, `/execute mark-interrupted`, "
            "`/execute abort` 중 하나를 실행하세요."
        ),
        "execution_log_entries": "실행 로그 항목",
        "execution_recovery": "실행 복구",
        "execution_recovery_none": "이 워크플로우에 기록된 중단 실행이 없습니다.",
        "execution_results": "실행 결과",
        "final_review": "최종 리뷰",
        "follow_up_requests": "후속 요청",
        "goal": "목표",
        "help_agent_call": "에이전트 호출",
        "help_exact_hint": "Tab으로 명령을 완성하고 Enter로 정확한 명령을 실행하세요.",
        "help_intro_agent": "로컬 UI, 설정, 파일 명령은 에이전트를 호출하지 않습니다.",
        "help_intro_trinity": "Trinity 소유 슬래시 명령은 프로바이더 프롬프트보다 먼저 처리됩니다.",
        "history_hint": "프롬프트 실행, 워크플로우 실행, 로컬 슬래시 명령 사용 후 이력이 표시됩니다.",
        "history": "워크플로우 이력",
        "id": "ID",
        "improve_hint": (
            "`/improve high`, `/improve all`, `/improve AI-001`, "
            "`/improve done` 중 하나를 실행하세요."
        ),
        "improve": "개선",
        "inside_control_repo": "제어 저장소 내부",
        "intensity": "강도",
        "item": "항목",
        "kind": "종류",
        "last_event": "최근 이벤트",
        "local_command": "로컬 명령",
        "local_policy_repairs": "로컬 정책 복구",
        "memory_cleanup": "메모리 정리",
        "memory_cleanup_keep_latest_number": "`--keep-latest`에는 숫자를 입력하세요.",
        "memory_cleanup_keep_latest_range": "`--keep-latest`는 0 이상이어야 합니다.",
        "memory_cleanup_unknown_option": "알 수 없는 정리 옵션",
        "memory_cleanup_usage": (
            "사용법: `/memory cleanup --oversized-backups "
            "[--apply] [--keep-latest N]`"
        ),
        "memory_compact": "메모리 압축",
        "memory_stats": "메모리 통계",
        "model_settings": "모델 설정",
        "model_settings_unavailable": (
            "모델 설정은 시작 화면과 Nexus에서 사용할 수 있습니다."
        ),
        "model_settings_updated": "모델 설정을 업데이트했습니다.",
        "mode": "모드",
        "next": "다음",
        "no": "아니오",
        "no_decisions": "현재 세션에 기록된 워크플로우 결정이 없습니다.",
        "none": "(없음)",
        "no_history": "현재 세션에 기록된 로컬 이력이 없습니다.",
        "no_packages": "현재 세션에 생성된 워크플로우 작업 패키지가 없습니다.",
        "no_pending_questions": "대기 중인 워크플로우 질문이 없습니다.",
        "no_pending_questions_select": "선택할 대기 질문이 없습니다.",
        "no_predefined_options": "이 질문에는 미리 정의된 선택지가 없습니다.",
        "no_subtasks": "현재 세션에 기록된 프로바이더 위임 하위 작업이 없습니다.",
        "no_goal": "(목표 없음)",
        "new_workflow": "(새 워크플로우)",
        "no_package": "(패키지 없음)",
        "not_set": "(미설정)",
        "not_checked": "미확인",
        "options": "선택지",
        "package": "작업 패키지",
        "packages": "작업 패키지",
        "packages_hint": "설계안 또는 로컬 작업 패키지 그래프가 생성될 때까지 계획을 진행하세요.",
        "path": "경로",
        "pending_questions": "대기 중 질문",
        "pending_wp_review": "대기 중 작업 패키지 리뷰",
        "post_review_action_items": "리뷰 후 조치",
        "post_review_items": "리뷰 후 조치",
        "action_items": "조치 항목",
        "provider": "프로바이더",
        "questions": "질문",
        "question": "질문",
        "question_hint": "질문 패널 버튼을 사용하거나 `/answer <id|index|next> <answer>`를 실행하세요.",
        "question_answer_usage": "`/answer <id|index|next> <answer>`를 실행하세요.",
        "question_select_hint": (
            "질문 패널의 선택지 버튼을 사용하거나 `/answer <option-number>`를 실행하세요."
        ),
        "readiness": "준비 상태",
        "recent_execution_log": "최근 실행 로그",
        "recent_local_items": "최근 로컬 항목",
        "recent_repair_notes": "최근 보정 메모",
        "recommended": "추천",
        "reattach_note": (
            "프로바이더 프로세스 재연결은 지원하지 않습니다. 재시도는 중단, 실패, "
            "차단된 작업에 대해 새 단발 실행을 시작합니다."
        ),
        "recovery": "(복구)",
        "report": "리포트",
        "report_export_complete": "내보내기 완료",
        "report_export_hint": "리포트를 내보내려면 먼저 워크플로우를 시작하거나 재개하세요.",
        "report_export_unavailable": "내보내기 불가",
        "report_no_export_data": "내보낼 워크플로우 데이터가 없습니다.",
        "report_no_open_data": "리포트로 표시할 워크플로우 데이터가 없습니다.",
        "report_open_hint": "리포트를 열려면 먼저 워크플로우를 시작하거나 재개하세요.",
        "report_opened": "리포트 화면을 열었습니다.",
        "report_saved": "리포트 저장됨",
        "resume": "재개",
        "resume_archives_available": "재개할 수 있는 저장된 워크플로우가 있습니다.",
        "resume_cancel_hint": "보관된 워크플로우를 선택하려면 `/resume`을 다시 실행하세요.",
        "resume_cancelled": "재개 선택을 취소했습니다.",
        "resume_empty_hint": "`/resume`을 사용하려면 먼저 워크플로우를 시작하고 보관하세요.",
        "resume_no_saved": "재개할 저장된 워크플로우가 없습니다.",
        "resume_pick_hint": "재개 모달에서 워크플로우를 선택하세요.",
        "retry_candidates": "재시도 후보",
        "review_repair": "리뷰 보정",
        "review_repair_action_hint": (
            "중앙 패널에서 한 번 재시도, 완료 처리, 중지 중 하나를 선택하세요."
        ),
        "review_repair_none": "리뷰 보정으로 중단된 작업 패키지가 기록되어 있지 않습니다.",
        "review_repair_paused": "리뷰 보정 루프 가드가 다음 작업 패키지를 일시 중지했습니다:",
        "repair_state": "보정 상태",
        "review": "리뷰",
        "review_title": "리뷰",
        "review_hint": "`/review wp`, `/review final`, `/review all` 중 하나를 실행하세요.",
        "reviewed_wp": "리뷰된 작업 패키지",
        "reviewer": "리뷰어",
        "round": "라운드",
        "rounds": "라운드",
        "rounds_allowed_range": "허용 범위",
        "rounds_change_hint": "`/rounds <1..20>`로 이 세션의 값을 변경하세요.",
        "rounds_invalid_number": "숫자가 올바르지 않습니다.",
        "rounds_range_error": "라운드는 1에서 20 사이여야 합니다.",
        "rounds_set": "최대 라운드 설정",
        "rounds_usage": "`/rounds <1..20>`를 사용하세요.",
        "run": "실행 ID",
        "save": "저장",
        "save_auto_persist_body": (
            "Trinity 워크플로우는 자동으로 저장됩니다. "
            "마크다운 리포트 내보내기는 /report save를 사용하세요."
        ),
        "slash_command": "슬래시 명령",
        "severity": "심각도",
        "source": "출처",
        "running_packages": "실행 중 작업 패키지",
        "running_packages_at_exit": "종료 시 실행 중 작업 패키지",
        "selector": "선택자",
        "state": "상태",
        "status": "상태",
        "summary": "요약",
        "subtasks": "하위 작업",
        "subtasks_hint": "실행 중인 프로바이더가 위임 작업을 보고하면 하위 작업이 표시됩니다.",
        "supplemental_rounds": "보충 라운드",
        "synthesis": "종합",
        "syntax_error": "구문 오류",
        "target": "대상",
        "target_action_hint": "실행 전에 `/target <path>`를 사용하거나 작업 폴더를 선택하세요.",
        "target_cleared": "대상 작업 폴더를 초기화했습니다.",
        "target_control_repo_hint": "Trinity 제어 저장소 밖의 작업 폴더를 선택하세요.",
        "target_not_directory": "대상 경로가 이미 존재하지만 디렉터리가 아닙니다",
        "target_preflight_cancelled": "작업 폴더 사전 확인을 취소했습니다.",
        "target_prepare_failed": "대상 작업 폴더를 준비할 수 없습니다",
        "target_selection_cancelled": "대상 작업 폴더 선택을 취소했습니다.",
        "target_workspace": "대상 작업 폴더",
        "title": "제목",
        "value": "값",
        "workflow": "워크플로우",
        "workflow_history": "워크플로우 이력",
        "work_packages": "작업 패키지",
        "local": "로컬",
        "trinity_commands": "Trinity 명령",
        "unnamed": "(이름 없음)",
        "unknown_command": "알 수 없는 명령",
        "unknown_command_body": "은 Trinity 슬래시 명령이 아닙니다.",
        "unknown_command_did_you_mean": "다음 명령을 찾으셨나요:",
        "unknown_command_help": "`/help`로 Trinity 로컬 명령을 확인하세요.",
        "unknown": "(알 수 없음)",
        "suggestion": "추천",
        "yes": "예",
        "selected_question": "선택된 질문",
        "free_text": "(자유 입력)",
    },
}


@dataclass(frozen=True)
class CentralActionButton:
    """One central Nexus action button to render."""

    action: str
    label_key: str
    variant: str = "default"
    tooltip_key: str = ""


@dataclass(frozen=True)
class CentralActionPlan:
    """Pure presenter result for central Nexus action buttons."""

    title_key: str = ""
    buttons: tuple[CentralActionButton, ...] = ()


def central_action_plan(snapshot: WorkflowNexusSnapshot) -> CentralActionPlan:
    """Return the highest-priority central action group for a snapshot."""
    provider_error_options = provider_error_gate_options(snapshot)
    if provider_error_options:
        buttons = [
            CentralActionButton(
                "provider-error-retry",
                "provider_error_retry",
                "primary",
                "provider-error-retry_tooltip",
            )
        ]
        if "Continue without failed providers" in provider_error_options:
            buttons.append(
                CentralActionButton(
                    "provider-error-continue",
                    "provider_error_continue",
                    "default",
                    "provider-error-continue_tooltip",
                )
            )
        buttons.append(
            CentralActionButton(
                "provider-error-stop",
                "provider_error_stop",
                "error",
                "provider-error-stop_tooltip",
            )
        )
        return CentralActionPlan("provider_error_action", tuple(buttons))

    if should_show_repair_actions(snapshot):
        return CentralActionPlan(
            "repair_action",
            (
                CentralActionButton(
                    "repair-retry-once",
                    "repair_retry_once",
                    "primary",
                    "repair-retry-once_tooltip",
                ),
                CentralActionButton(
                    "repair-mark-done",
                    "repair_mark_done",
                    "default",
                    "repair-mark-done_tooltip",
                ),
                CentralActionButton(
                    "repair-open-review",
                    "repair_open_review",
                    "default",
                    "repair-open-review_tooltip",
                ),
                CentralActionButton(
                    "repair-stop",
                    "repair_stop",
                    "error",
                    "repair-stop_tooltip",
                ),
            ),
        )

    if should_show_execution_retry_action(snapshot):
        return CentralActionPlan(
            "execution_recovery_action",
            (
                CentralActionButton(
                    "execution-retry",
                    "execution_retry",
                    "primary",
                    "execution-retry_tooltip",
                ),
            ),
        )

    if should_show_blueprint_actions(snapshot):
        return CentralActionPlan(
            "next_action",
            (
                CentralActionButton("execute", "execute", "primary", "execute_tooltip"),
                CentralActionButton(
                    "refine-features",
                    "refine_features",
                    "default",
                    "refine-features_tooltip",
                ),
                CentralActionButton(
                    "refine-risks",
                    "refine_risks",
                    "default",
                    "refine-risks_tooltip",
                ),
                CentralActionButton(
                    "refine-work-packages",
                    "refine_work_packages",
                    "default",
                    "refine-work-packages_tooltip",
                ),
            ),
        )

    return CentralActionPlan()


def should_show_blueprint_actions(snapshot: WorkflowNexusSnapshot) -> bool:
    return snapshot.state == "blueprint_ready" and bool(
        snapshot.work_packages or snapshot.central_work_packages
    )


def should_show_repair_actions(snapshot: WorkflowNexusSnapshot) -> bool:
    recovery = snapshot.execution_recovery
    if recovery and recovery.state == "repair_blocked":
        return True
    if snapshot.state != "needs_user_decision":
        return False
    return any(
        package.status == "blocked" and package.repair_blocked_reason
        for package in snapshot.work_package_details
    )


def should_show_execution_retry_action(snapshot: WorkflowNexusSnapshot) -> bool:
    recovery = snapshot.execution_recovery
    if recovery is None:
        return False
    if recovery.state == "repair_blocked":
        return False
    return bool(recovery.retry_candidates)


def provider_error_gate_options(snapshot: WorkflowNexusSnapshot) -> set[str]:
    for question in snapshot.questions:
        if question.id == "q-provider-error-retry" and not question.answer:
            return set(question.options)
    return set()


def review_repair_blocked_ids(snapshot: WorkflowNexusSnapshot) -> tuple[str, ...]:
    package_ids: list[str] = []
    seen: set[str] = set()
    for package in snapshot.work_package_details:
        if package.status != "blocked" or not package.repair_blocked_reason:
            continue
        package_id = package.id.strip()
        if package_id and package_id not in seen:
            package_ids.append(package_id)
            seen.add(package_id)
    recovery = snapshot.execution_recovery
    if recovery is not None and recovery.state == "repair_blocked":
        for package_id in recovery.retry_candidates:
            normalized = str(package_id).strip()
            if normalized and normalized not in seen:
                package_ids.append(normalized)
                seen.add(normalized)
    return tuple(package_ids)


def review_repair_title(*, lang: str = "en") -> str:
    return _sc_label(lang, "review_repair")


def review_repair_action_hint(*, lang: str = "en") -> str:
    return _sc_label(lang, "review_repair_action_hint")


def review_repair_table_columns(*, lang: str = "en") -> tuple[str, str]:
    return (
        "작업 패키지" if lang == "ko" else "WP",
        _sc_label(lang, "repair_state"),
    )


def review_repair_details_markdown(
    snapshot: WorkflowNexusSnapshot,
    *,
    lang: str = "en",
) -> str:
    rows = review_repair_rows(snapshot, lang=lang)
    if not rows:
        return _sc_label(lang, "review_repair_none")
    lines = [_sc_label(lang, "review_repair_paused")]
    for package_id, detail in rows:
        lines.append(f"- **{package_id}**: {detail}")
    if snapshot.work_package_repairs:
        lines.extend(["", f"### {_sc_label(lang, 'recent_repair_notes')}"])
        lines.extend(f"- {item}" for item in snapshot.work_package_repairs)
    return "\n".join(lines)


def review_repair_rows(
    snapshot: WorkflowNexusSnapshot,
    *,
    lang: str = "en",
) -> tuple[tuple[str, str], ...]:
    rows: list[tuple[str, str]] = []
    seen: set[str] = set()
    for package in snapshot.work_package_details:
        if package.status != "blocked" or not package.repair_blocked_reason:
            continue
        seen.add(package.id)
        review_status = display_review_status_value(
            package.review_status,
            reviewer_agent=package.reviewer_agent,
            summary=package.review_summary,
            lang=lang,
            empty=_none_value(lang),
        )
        rows.append(
            (
                package.id,
                (
                    f"{package.repair_blocked_reason}; "
                    f"{_sc_label(lang, 'attempts')}={package.repair_attempt_count}/"
                    f"{package.repair_max_attempts}; "
                    f"{_sc_label(lang, 'review')}={review_status}"
                ),
            )
        )
    recovery = snapshot.execution_recovery
    if recovery is not None and recovery.state == "repair_blocked":
        for package_id in recovery.retry_candidates:
            normalized = str(package_id).strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            rows.append(
                (
                    normalized,
                    (
                        f"{_status_value('repair_blocked', lang=lang)}; "
                        f"{_sc_label(lang, 'attempts')}="
                        f"{_sc_label(lang, 'unknown')}; "
                        f"{_sc_label(lang, 'review')}={_sc_label(lang, 'recovery')}"
                    ),
                )
            )
    return tuple(rows)


def status_table_columns(*, lang: str = "en") -> tuple[str, str]:
    return (_sc_label(lang, "item"), _sc_label(lang, "value"))


def execution_recovery_markdown(
    snapshot: WorkflowNexusSnapshot,
    *,
    lang: str = "en",
) -> str:
    recovery = snapshot.execution_recovery
    if recovery is None:
        return _sc_label(lang, "execution_recovery_none")
    lines = [
        f"- {_sc_label(lang, 'execution')}: `{_status_value(recovery.state, lang=lang)}`",
        f"- {_sc_label(lang, 'run')}: `{recovery.run_id or _unknown_value(lang)}`",
        f"- {_sc_label(lang, 'target')}: `{recovery.target_workspace or _not_set_value(lang)}`",
        (
            f"- {_sc_label(lang, 'running_packages_at_exit')}: "
            f"`{', '.join(recovery.running_packages) or _none_value(lang)}`"
        ),
        f"- {_sc_label(lang, 'retry_candidates')}: "
        f"`{', '.join(recovery.retry_candidates) or _none_value(lang)}`",
        f"- {_sc_label(lang, 'done_packages')}: "
        f"`{', '.join(recovery.done_packages) or _none_value(lang)}`",
        f"- {_sc_label(lang, 'last_event')}: `{recovery.last_event or _none_value(lang)}`",
        "",
        _sc_label(lang, "reattach_note"),
    ]
    return "\n".join(lines)


def execution_recovery_rows(
    snapshot: WorkflowNexusSnapshot,
    *,
    lang: str = "en",
) -> tuple[tuple[str, str], ...]:
    recovery = snapshot.execution_recovery
    if recovery is None:
        return ((_sc_label(lang, "execution"), _none_value(lang)),)
    return (
        (_sc_label(lang, "execution"), _status_value(recovery.state, lang=lang)),
        (_sc_label(lang, "run"), recovery.run_id or _unknown_value(lang)),
        (_sc_label(lang, "target"), recovery.target_workspace or _not_set_value(lang)),
        (
            _sc_label(lang, "running_packages"),
            ", ".join(recovery.running_packages) or _none_value(lang),
        ),
        (
            _sc_label(lang, "retry_candidates"),
            ", ".join(recovery.retry_candidates) or _none_value(lang),
        ),
        (
            _sc_label(lang, "done_packages"),
            ", ".join(recovery.done_packages) or _none_value(lang),
        ),
        (_sc_label(lang, "last_event"), recovery.last_event or _none_value(lang)),
        (_sc_label(lang, "next"), _sc_label(lang, "execute_recovery_hint")),
    )


def execute_title(*, lang: str = "en") -> str:
    return _sc_label(lang, "execute")


def execute_retry_title(*, lang: str = "en") -> str:
    return _sc_label(lang, "execute_retry")


def execute_retry_no_packages_markdown(*, lang: str = "en") -> str:
    return _sc_label(lang, "execute_retry_no_packages")


def execute_retry_no_packages_action_hint(*, lang: str = "en") -> str:
    return _sc_label(lang, "execute_retry_no_packages_hint")


def execute_finish_planning_action_hint(*, lang: str = "en") -> str:
    return _sc_label(lang, "execute_finish_planning_hint")


def execution_recovery_title(*, lang: str = "en") -> str:
    return _sc_label(lang, "execution_recovery")


def execution_recovery_action_hint(*, lang: str = "en") -> str:
    return _sc_label(lang, "execute_recovery_hint")


def execution_recovery_table_columns(*, lang: str = "en") -> tuple[str, str]:
    return status_table_columns(lang=lang)


def snapshot_status_markdown(
    snapshot: WorkflowNexusSnapshot,
    *,
    lang: str = "en",
) -> str:
    state = _status_value(snapshot.state or "idle", lang=lang)
    goal = snapshot.goal or _none_value(lang)
    lines = [
        f"- {_sc_label(lang, 'workflow')}: `{snapshot.session_id or _new_workflow_value(lang)}`",
        f"- {_sc_label(lang, 'state')}: `{state}`",
        f"- {_sc_label(lang, 'round')}: `{snapshot.round_num}`",
        f"- {_sc_label(lang, 'goal')}: {goal}",
        "",
        (
            f"| {_sc_label(lang, 'provider')} | {_sc_label(lang, 'enabled')} "
            f"| {_sc_label(lang, 'status')} | {_sc_label(lang, 'readiness')} |"
        ),
        "| :--- | :--- | :--- | :--- |",
    ]
    if snapshot.providers:
        lines.extend(
            (
                f"| {provider.name} | {_yes_no(provider.enabled, lang=lang)} "
                f"| {_status_value(provider.status, lang=lang)} "
                f"| {readiness_label(provider.readiness, lang=lang)} |"
            )
            for provider in snapshot.providers
        )
    else:
        lines.append("| - | - | - | - |")
    if snapshot.execution_recovery is not None:
        lines.extend(["", f"### {_sc_label(lang, 'execution_recovery')}"])
        lines.append(execution_recovery_markdown(snapshot, lang=lang))
    return "\n".join(lines)


def snapshot_status_rows(
    snapshot: WorkflowNexusSnapshot,
    *,
    lang: str = "en",
) -> tuple[tuple[str, str], ...]:
    rows = [
        (_sc_label(lang, "workflow"), snapshot.session_id or _new_workflow_value(lang)),
        (_sc_label(lang, "state"), _status_value(snapshot.state or "idle", lang=lang)),
        (_sc_label(lang, "round"), str(snapshot.round_num)),
        (_sc_label(lang, "goal"), snapshot.goal or _none_value(lang)),
    ]
    for provider in snapshot.providers:
        rows.append(
            (
                f"{_sc_label(lang, 'provider')}: {provider.name}",
                (
                    f"{_status_value(provider.status, lang=lang)}; "
                    f"{_sc_label(lang, 'enabled').lower()}="
                    f"{_yes_no(provider.enabled, lang=lang)}; "
                    f"{_sc_label(lang, 'readiness').lower()}="
                    f"{readiness_label(provider.readiness, lang=lang)}"
                ),
            )
        )
    if snapshot.execution_recovery is not None:
        rows.extend(execution_recovery_rows(snapshot, lang=lang))
    return tuple(rows)


def readiness_label(readiness: str, *, lang: str = "en") -> str:
    if readiness == "unknown":
        return _sc_label(lang, "not_checked")
    return display_readiness_value(readiness, lang=lang, empty=_sc_label(lang, "empty"))


WORKFLOW_OUTCOME_MESSAGES_KO = {
    "Workflow is still running.": "워크플로우가 아직 실행 중입니다.",
    "Workflow is already running.": "워크플로우가 이미 실행 중입니다.",
    "No active agents are configured.": "활성화된 에이전트가 없습니다.",
    "No interrupted execution to mark.": "표시할 중단된 실행이 없습니다.",
    "Execution marked as interrupted.": "실행을 중단 상태로 표시했습니다.",
    "No interrupted execution to abort.": "중단을 취소할 실행이 없습니다.",
    "Interrupted execution aborted.": "중단된 실행을 취소했습니다.",
    "Choose a target workspace before restarting repairs.": (
        "보정 재시작 전에 대상 작업 폴더를 선택하세요."
    ),
    "Previous execution was interrupted. Review running packages before retrying.": (
        "이전 실행이 중단되었습니다. 재시도 전에 실행 중이던 작업 패키지를 확인하세요."
    ),
    "Previous execution was interrupted.": "이전 실행이 중단되었습니다.",
    "No blueprint is ready. Finish planning before execution.": (
        "준비된 설계안이 없습니다. 실행 전에 계획을 완료하세요."
    ),
    "No retryable work packages match the request.": (
        "요청과 일치하는 재시도 가능한 작업 패키지가 없습니다."
    ),
    "Choose a target workspace before retrying execution.": (
        "실행 재시도 전에 대상 작업 폴더를 선택하세요."
    ),
    "No review-repair blocked packages to retry.": (
        "재시도할 리뷰 보정 차단 패키지가 없습니다."
    ),
    "No review-repair blocked packages to accept.": (
        "완료 처리할 리뷰 보정 차단 패키지가 없습니다."
    ),
    "No review-repair blocked packages to stop.": (
        "중단할 리뷰 보정 차단 패키지가 없습니다."
    ),
    "Choose a target workspace before running review.": (
        "리뷰 실행 전에 대상 작업 폴더를 선택하세요."
    ),
    "No pending work package reviews match the request.": (
        "요청과 일치하는 대기 중인 작업 패키지 리뷰가 없습니다."
    ),
    "No saved workflow sessions to resume.": (
        "재개할 저장된 워크플로우 세션이 없습니다."
    ),
    "Execution failed. Review failed packages before retrying.": (
        "실행이 실패했습니다. 재시도 전에 실패한 패키지를 확인하세요."
    ),
    "Review started after execution.": "실행 후 리뷰를 시작했습니다.",
    "Review requires a user decision before continuing.": (
        "계속하기 전에 리뷰에 대한 사용자 결정이 필요합니다."
    ),
    "Answer cannot be empty.": "답변은 비워둘 수 없습니다.",
    "Instruction cannot be empty.": "지시문은 비워둘 수 없습니다.",
    "Workflow action cancelled.": "워크플로우 작업을 취소했습니다.",
    "No approved blueprint is available to execute.": "실행할 승인된 설계안이 없습니다.",
    "No active agents are attached to this workflow.": (
        "이 워크플로우에 연결된 활성 에이전트가 없습니다."
    ),
    "Target workspace is required before implementation.": (
        "구현 전에 대상 작업 폴더가 필요합니다."
    ),
    "Current blueprint work packages are ready for execution.": (
        "현재 설계안의 작업 패키지가 실행 준비되었습니다."
    ),
    "Continue is not available because no usable consensus exists.": (
        "사용 가능한 합의가 없어 계속할 수 없습니다."
    ),
    "Continuing without failed providers.": "실패한 프로바이더를 제외하고 계속합니다.",
    "Workflow stopped after provider errors.": (
        "프로바이더 오류 이후 워크플로우를 중단했습니다."
    ),
    "Retrying failed providers.": "실패한 프로바이더를 재시도합니다.",
    "No post-review follow-up is ready for this workflow.": (
        "이 워크플로우에는 준비된 리뷰 후속 작업이 없습니다."
    ),
    "Post-review follow-up closed. Workflow is done.": (
        "리뷰 후속 작업을 닫았습니다. 워크플로우가 완료되었습니다."
    ),
    "Target workspace is required before post-review improvement.": (
        "리뷰 후속 개선 전에 대상 작업 폴더가 필요합니다."
    ),
    "No matching post-review action items. Use /improve, /improve high, /improve all, /improve AI-001, or /improve done.": (
        "일치하는 리뷰 후속 작업 항목이 없습니다. /improve, /improve high, "
        "/improve all, /improve AI-001, 또는 /improve done을 사용하세요."
    ),
    "Selected post-review items do not require execution.": (
        "선택한 리뷰 후속 항목은 실행이 필요하지 않습니다."
    ),
    "Accepted blocked review repairs.": "차단된 리뷰 보정을 완료 처리했습니다.",
    "Stopped blocked review repairs.": "차단된 리뷰 보정을 중단했습니다.",
}

WORKFLOW_OUTCOME_PREFIXES_KO = (
    ("Workflow error: ", "워크플로우 오류: "),
    ("Retrying work packages: ", "작업 패키지를 재시도합니다: "),
    ("Accepted blocked review repairs: ", "차단된 리뷰 보정을 완료 처리했습니다: "),
    (
        "Stopped workflow after blocked review repairs: ",
        "리뷰 보정 차단 이후 워크플로우를 중단했습니다: ",
    ),
    ("Review started: ", "리뷰를 시작했습니다: "),
    ("No matching workflow session: ", "일치하는 워크플로우 세션이 없습니다: "),
    ("Resumed workflow ", "워크플로우를 재개했습니다: "),
    ("No matching workflow question: ", "일치하는 워크플로우 질문이 없습니다: "),
    ("Option must be a number: ", "옵션은 숫자여야 합니다: "),
    ("Queued post-review improvement from ", "리뷰 후속 개선을 대기열에 추가했습니다: "),
    ("Improvement requested: ", "개선을 요청했습니다: "),
)

WORKFLOW_OUTCOME_FRAGMENT_REPLACEMENTS_KO = (
    (
        "Review requested repairs; restarting execution for: ",
        "리뷰가 수정을 요청했습니다. 다음 작업 패키지의 실행을 다시 시작합니다: ",
    ),
    ("Blocked by repair guard: ", "보정 루프 가드에 의해 차단됨: "),
    (
        "Choose a target workspace before restarting repairs.",
        "보정 재시작 전에 대상 작업 폴더를 선택하세요.",
    ),
    (
        " is already answered. Use /answer --replace to update it.",
        " 질문은 이미 답변되었습니다. 업데이트하려면 /answer --replace를 사용하세요.",
    ),
    ("Question ", "질문 "),
    (" has no option ", "에는 해당 옵션이 없습니다: "),
)


def _sc_label(lang: str, key: str) -> str:
    labels = STATUS_CONTEXT_LABELS.get(lang, STATUS_CONTEXT_LABELS["en"])
    return labels.get(key, STATUS_CONTEXT_LABELS["en"][key])


def _none_value(lang: str = "en") -> str:
    return _sc_label(lang, "none")


def _unknown_value(lang: str = "en") -> str:
    return _sc_label(lang, "unknown")


def _status_value(status: str, *, lang: str = "en") -> str:
    return display_status_value(status, lang=lang, empty=_unknown_value(lang))


def _question_status_value(status: str, *, lang: str = "en") -> str:
    raw = str(status or "open").strip() or "open"
    if lang == "ko":
        labels = {
            "answered": "답변됨",
            "open": "열림",
        }
        return labels.get(raw, _status_value(raw, lang=lang))
    return raw


def _not_set_value(lang: str = "en") -> str:
    return _sc_label(lang, "not_set")


def _new_workflow_value(lang: str = "en") -> str:
    return _sc_label(lang, "new_workflow")


def _unnamed_value(lang: str = "en") -> str:
    return _sc_label(lang, "unnamed")


def _no_package_value(lang: str = "en") -> str:
    return _sc_label(lang, "no_package")


def workflow_outcome_message_markdown(message: str, *, lang: str = "en") -> str:
    if not message or lang != "ko":
        return message
    exact = WORKFLOW_OUTCOME_MESSAGES_KO.get(message)
    if exact is not None:
        return exact
    for prefix, localized_prefix in WORKFLOW_OUTCOME_PREFIXES_KO:
        if message.startswith(prefix):
            return f"{localized_prefix}{message[len(prefix):]}"
    localized = message
    for source, replacement in WORKFLOW_OUTCOME_FRAGMENT_REPLACEMENTS_KO:
        localized = localized.replace(source, replacement)
    return localized


def _yes_no(value: bool, *, lang: str = "en") -> str:
    return _sc_label(lang, "yes" if value else "no")


def status_title(*, lang: str = "en") -> str:
    return _sc_label(lang, "status")


def workflow_title(*, lang: str = "en") -> str:
    return _sc_label(lang, "workflow")


def questions_title(*, lang: str = "en") -> str:
    return _sc_label(lang, "questions")


def decisions_title(*, lang: str = "en") -> str:
    return _sc_label(lang, "decisions")


def packages_title(*, lang: str = "en") -> str:
    return _sc_label(lang, "packages")


def subtasks_title(*, lang: str = "en") -> str:
    return _sc_label(lang, "subtasks")


def history_title(*, lang: str = "en") -> str:
    return _sc_label(lang, "history")


def model_settings_title(*, lang: str = "en") -> str:
    return _sc_label(lang, "model_settings")


def model_settings_unavailable_markdown(*, lang: str = "en") -> str:
    return _sc_label(lang, "model_settings_unavailable")


def model_settings_updated_markdown(*, lang: str = "en") -> str:
    return _sc_label(lang, "model_settings_updated")


def slash_command_notification_title(*, lang: str = "en") -> str:
    return _sc_label(lang, "slash_command")


def answer_title(*, lang: str = "en") -> str:
    return _sc_label(lang, "answer")


def answer_usage_markdown(*, lang: str = "en") -> str:
    return _sc_label(lang, "answer_usage")


def answer_action_hint(*, lang: str = "en") -> str:
    return _sc_label(lang, "answer_inspect_questions_hint")


def report_title(*, lang: str = "en") -> str:
    return _sc_label(lang, "report")


def report_export_unavailable_title(*, lang: str = "en") -> str:
    return _sc_label(lang, "report_export_unavailable")


def report_export_complete_title(*, lang: str = "en") -> str:
    return _sc_label(lang, "report_export_complete")


def report_no_export_data_markdown(*, lang: str = "en") -> str:
    return _sc_label(lang, "report_no_export_data")


def report_no_open_data_markdown(*, lang: str = "en") -> str:
    return _sc_label(lang, "report_no_open_data")


def report_export_action_hint(*, lang: str = "en") -> str:
    return _sc_label(lang, "report_export_hint")


def report_open_action_hint(*, lang: str = "en") -> str:
    return _sc_label(lang, "report_open_hint")


def report_opened_markdown(*, lang: str = "en") -> str:
    return _sc_label(lang, "report_opened")


def report_saved_markdown(path: str, *, lang: str = "en") -> str:
    return f"{_sc_label(lang, 'report_saved')}: `{path}`"


def report_saved_notification(path: str, *, lang: str = "en") -> str:
    return f"{_sc_label(lang, 'report_saved')}: {path}"


def report_saved_rows(path: str, *, lang: str = "en") -> tuple[tuple[str, str], ...]:
    return ((_sc_label(lang, "path"), path),)


def report_summary_rows(
    snapshot: WorkflowNexusSnapshot,
    *,
    lang: str = "en",
) -> tuple[tuple[str, str], ...]:
    return (
        (_sc_label(lang, "workflow"), snapshot.session_id or _new_workflow_value(lang)),
        (_sc_label(lang, "state"), _status_value(snapshot.state or "idle", lang=lang)),
        (_sc_label(lang, "questions"), str(len(snapshot.questions))),
        (_sc_label(lang, "decisions"), str(len(snapshot.decisions))),
        (
            _sc_label(lang, "work_packages"),
            str(len(snapshot.central_work_packages) + len(snapshot.work_packages)),
        ),
        (_sc_label(lang, "subtasks"), str(len(snapshot.subtasks))),
    )


def save_title(*, lang: str = "en") -> str:
    return _sc_label(lang, "save")


def save_auto_persist_markdown(*, lang: str = "en") -> str:
    return _sc_label(lang, "save_auto_persist_body")


def target_title(*, lang: str = "en") -> str:
    return _sc_label(lang, "target")


def target_selection_cancelled_markdown(*, lang: str = "en") -> str:
    return _sc_label(lang, "target_selection_cancelled")


def target_preflight_cancelled_markdown(*, lang: str = "en") -> str:
    return _sc_label(lang, "target_preflight_cancelled")


def target_control_repo_action_hint(*, lang: str = "en") -> str:
    return _sc_label(lang, "target_control_repo_hint")


def target_current_markdown(current: str | None, *, lang: str = "en") -> str:
    value = current or _sc_label(lang, "not_set")
    return f"{_sc_label(lang, 'current_target')}: `{value}`"


def target_action_hint(*, lang: str = "en") -> str:
    return _sc_label(lang, "target_action_hint")


def target_cleared_markdown(*, lang: str = "en") -> str:
    return _sc_label(lang, "target_cleared")


def target_not_directory_markdown(path: str, *, lang: str = "en") -> str:
    return f"{_sc_label(lang, 'target_not_directory')}: `{path}`"


def target_prepare_failed_markdown(error: str, *, lang: str = "en") -> str:
    return f"{_sc_label(lang, 'target_prepare_failed')}: {error}"


def target_workspace_markdown(path: str, *, lang: str = "en") -> str:
    return f"{_sc_label(lang, 'target_workspace')}: `{path}`"


def target_rows(
    path: str,
    *,
    inside_control_repo: bool,
    control_repo_confirmed: bool,
    lang: str = "en",
) -> tuple[tuple[str, str], ...]:
    return (
        (_sc_label(lang, "path"), path),
        (_sc_label(lang, "inside_control_repo"), _yes_no(inside_control_repo, lang=lang)),
        (
            _sc_label(lang, "control_repo_confirmed"),
            _yes_no(control_repo_confirmed, lang=lang),
        ),
    )


def rounds_title(*, lang: str = "en") -> str:
    return _sc_label(lang, "rounds")


def rounds_current_markdown(value: int, *, lang: str = "en") -> str:
    return f"{_sc_label(lang, 'current_max_rounds')}: `{value}`."


def rounds_set_markdown(value: int, *, lang: str = "en") -> str:
    if lang == "ko":
        return f"이 세션의 최대 라운드를 `{value}`로 설정했습니다."
    return f"{_sc_label(lang, 'rounds_set')} to `{value}` for this session only."


def rounds_invalid_number_markdown(*, lang: str = "en") -> str:
    return _sc_label(lang, "rounds_invalid_number")


def rounds_range_error_markdown(*, lang: str = "en") -> str:
    return _sc_label(lang, "rounds_range_error")


def rounds_change_action_hint(*, lang: str = "en") -> str:
    return _sc_label(lang, "rounds_change_hint")


def rounds_usage_action_hint(*, lang: str = "en") -> str:
    return _sc_label(lang, "rounds_usage")


def rounds_rows(value: int, *, lang: str = "en") -> tuple[tuple[str, str], ...]:
    return (
        (_sc_label(lang, "current_max_rounds"), str(value)),
        (_sc_label(lang, "rounds_allowed_range"), "1..20"),
    )


def agent_title(*, lang: str = "en") -> str:
    return _sc_label(lang, "agent")


def agent_current_settings_markdown(*, lang: str = "en") -> str:
    return _sc_label(lang, "agent_current_settings")


def agent_change_action_hint(*, lang: str = "en") -> str:
    return _sc_label(lang, "agent_change_hint")


def agent_usage_markdown(*, lang: str = "en") -> str:
    return _sc_label(lang, "agent_usage")


def agent_unknown_markdown(name: str, *, lang: str = "en") -> str:
    return f"{_sc_label(lang, 'agent_unknown')}: `{name}`"


def agent_status_markdown(name: str, enabled: bool, *, lang: str = "en") -> str:
    status = _sc_label(lang, "agent_enabled" if enabled else "agent_disabled")
    if lang == "ko":
        return f"이 세션에서 에이전트 `{name}`를 {status}했습니다."
    return f"Agent `{name}` {status} for this session only."


def agent_table_columns(*, lang: str = "en") -> tuple[str, str, str]:
    return (
        _sc_label(lang, "agent"),
        _sc_label(lang, "enabled"),
        _sc_label(lang, "provider"),
    )


def agent_enabled_value(value: bool, *, lang: str = "en") -> str:
    return _yes_no(value, lang=lang)


def session_setting_body(message: str) -> str:
    return f"{message}\n\n{SESSION_ONLY_SETTING_NOTICE}"


def agent_rows(
    agents: Mapping[str, AgentRowSpec],
    *,
    lang: str = "en",
) -> tuple[tuple[str, str, str], ...]:
    return tuple(
        (
            name,
            agent_enabled_value(spec.enabled, lang=lang),
            (
                spec.provider.value
                if hasattr(spec.provider, "value")
                else str(spec.provider)
            ),
        )
        for name, spec in sorted(agents.items())
    )


def caveman_title(*, lang: str = "en") -> str:
    return _sc_label(lang, "caveman")


def caveman_current_markdown(mode: str, intensity: str, *, lang: str = "en") -> str:
    label = _sc_label(lang, "caveman")
    return f"{label}: `{mode}` (`{intensity}`)."


def caveman_set_markdown(mode: str, intensity: str, *, lang: str = "en") -> str:
    if lang == "ko":
        return f"이 세션의 간결 모드를 `{mode}` (`{intensity}`)로 설정했습니다."
    return (
        f"{_sc_label(lang, 'caveman_set')} to `{mode}` (`{intensity}`) "
        "for this session only."
    )


def caveman_usage_markdown(*, lang: str = "en") -> str:
    return _sc_label(lang, "caveman_usage")


def caveman_allowed_action_hint(*, lang: str = "en") -> str:
    return _sc_label(lang, "caveman_allowed_modes")


def caveman_change_action_hint(*, lang: str = "en") -> str:
    return _sc_label(lang, "caveman_change_hint")


def caveman_rows(
    mode: str,
    intensity: str,
    *,
    lang: str = "en",
) -> tuple[tuple[str, str], ...]:
    return (
        (_sc_label(lang, "mode"), mode),
        (_sc_label(lang, "intensity"), intensity),
        (_sc_label(lang, "allowed"), "on, off, lite, full, ultra"),
    )


def ask_title(*, lang: str = "en") -> str:
    return _sc_label(lang, "ask")


def ask_usage_markdown(*, lang: str = "en") -> str:
    return _sc_label(lang, "ask_usage")


def ask_unknown_agent_markdown(names: Sequence[str], *, lang: str = "en") -> str:
    return f"{_sc_label(lang, 'ask_unknown_agent')}: {', '.join(names)}"


def ask_no_active_agents_markdown(*, lang: str = "en") -> str:
    return _sc_label(lang, "ask_no_active_agents")


def ask_missing_model_markdown(*, lang: str = "en") -> str:
    return _sc_label(lang, "ask_missing_model")


def ask_prompt_empty_markdown(*, lang: str = "en") -> str:
    return _sc_label(lang, "ask_prompt_empty")


def ask_action_hint(*, lang: str = "en") -> str:
    return "/ask <all|agent[,agent...]> [--model MODEL] <prompt>"


def slash_command_suggestions(token: str) -> tuple[str, ...]:
    names = tuple(name for spec in COMMAND_SPECS for name in spec.names)
    return tuple(get_close_matches(token.lower(), names, n=3, cutoff=0.45))


def syntax_error_title(*, lang: str = "en") -> str:
    return _sc_label(lang, "syntax_error")


def unknown_command_title(*, lang: str = "en") -> str:
    return _sc_label(lang, "unknown_command")


def unknown_command_table_columns(*, lang: str = "en") -> tuple[str, str]:
    return (_sc_label(lang, "suggestion"), _sc_label(lang, "summary"))


def unknown_command_markdown(
    token: str,
    suggestions: tuple[str, ...],
    *,
    lang: str = "en",
) -> str:
    if lang == "ko":
        lines = [f"`{token}`{_sc_label(lang, 'unknown_command_body')}"]
    else:
        lines = [f"`{token}` {_sc_label(lang, 'unknown_command_body')}"]
    if suggestions:
        lines.extend(["", _sc_label(lang, "unknown_command_did_you_mean")])
        lines.extend(f"- `{name}`" for name in suggestions)
    else:
        lines.extend(["", _sc_label(lang, "unknown_command_help")])
    return "\n".join(lines)


def unknown_command_rows(
    suggestions: tuple[str, ...],
    *,
    lang: str = "en",
) -> tuple[tuple[str, str], ...]:
    summary_by_name = {name: spec.summary for spec in COMMAND_SPECS for name in spec.names}
    if lang == "ko":
        summary_by_name = {
            name: spec.summary_ko for spec in COMMAND_SPECS for name in spec.names
        }
    return tuple((name, summary_by_name.get(name, "")) for name in suggestions)


def help_title(*, lang: str = "en") -> str:
    return _sc_label(lang, "trinity_commands")


def help_table_columns(*, lang: str = "en") -> tuple[str, str, str, str]:
    return (
        _sc_label(lang, "command"),
        _sc_label(lang, "category"),
        _sc_label(lang, "help_agent_call"),
        _sc_label(lang, "summary"),
    )


def help_markdown(*, lang: str = "en") -> str:
    """Return registry-backed help text for Trinity-owned slash commands."""
    category_counts: dict[str, int] = {}
    for spec in COMMAND_SPECS:
        category = spec.category.value
        category_counts[category] = category_counts.get(category, 0) + 1
    lines = [
        _sc_label(lang, "help_intro_trinity"),
        _sc_label(lang, "help_intro_agent"),
        "",
        f"### {_sc_label(lang, 'categories')}",
    ]
    lines.extend(f"- `{category}`: {count}" for category, count in sorted(category_counts.items()))
    lines.extend(["", _sc_label(lang, "help_exact_hint")])
    return "\n".join(lines)


def help_rows(
    *,
    lang: str = "en",
    use_korean: bool | None = None,
) -> tuple[tuple[str, str, str, str], ...]:
    """Return slash command registry rows for read-only help tables."""
    if use_korean is None:
        use_korean = lang == "ko"
    rows: list[tuple[str, str, str, str]] = []
    for spec in COMMAND_SPECS:
        command = spec.name
        if spec.aliases:
            command = f"{command} ({', '.join(spec.aliases)})"
        rows.append(
            (
                command,
                spec.category.value,
                spec.agent_call.value,
                spec.summary_ko if use_korean else spec.summary,
            )
        )
    return tuple(rows)


def snapshot_workflow_markdown(
    snapshot: WorkflowNexusSnapshot,
    *,
    lang: str = "en",
) -> str:
    state = _status_value(snapshot.state or "idle", lang=lang)
    goal = snapshot.goal or _none_value(lang)
    lines = [
        f"- {_sc_label(lang, 'id')}: `{snapshot.session_id or _new_workflow_value(lang)}`",
        f"- {_sc_label(lang, 'state')}: `{state}`",
        f"- {_sc_label(lang, 'goal')}: {goal}",
        f"- {_sc_label(lang, 'round')}: `{snapshot.round_num}`",
        f"- {_sc_label(lang, 'pending_questions')}: `{len(snapshot.questions)}`",
        f"- {_sc_label(lang, 'decisions')}: `{len(snapshot.decisions)}`",
        f"- {_sc_label(lang, 'work_packages')}: `{len(snapshot.work_packages)}`",
        f"- {_sc_label(lang, 'subtasks')}: `{len(snapshot.subtasks)}`",
        f"- {_sc_label(lang, 'local_policy_repairs')}: `{len(snapshot.work_package_repairs)}`",
        f"- {_sc_label(lang, 'post_review_items')}: `{len(snapshot.post_review_items)}`",
        f"- {_sc_label(lang, 'supplemental_rounds')}: `{snapshot.supplemental_round}`",
        f"- {_sc_label(lang, 'execution_log_entries')}: `{len(snapshot.execution_log)}`",
    ]
    if snapshot.execution_recovery is not None:
        lines.extend(["", f"### {_sc_label(lang, 'execution_recovery')}"])
        lines.append(execution_recovery_markdown(snapshot, lang=lang))
    return "\n".join(lines)


def snapshot_workflow_rows(
    snapshot: WorkflowNexusSnapshot,
    *,
    lang: str = "en",
) -> tuple[tuple[str, str], ...]:
    rows = [
        (_sc_label(lang, "id"), snapshot.session_id or _new_workflow_value(lang)),
        (_sc_label(lang, "state"), _status_value(snapshot.state or "idle", lang=lang)),
        (_sc_label(lang, "goal"), snapshot.goal or _none_value(lang)),
        (_sc_label(lang, "round"), str(snapshot.round_num)),
        (_sc_label(lang, "pending_questions"), str(len(snapshot.questions))),
        (_sc_label(lang, "decisions"), str(len(snapshot.decisions))),
        (_sc_label(lang, "work_packages"), str(len(snapshot.work_packages))),
        (_sc_label(lang, "subtasks"), str(len(snapshot.subtasks))),
        (_sc_label(lang, "local_policy_repairs"), str(len(snapshot.work_package_repairs))),
        (_sc_label(lang, "post_review_items"), str(len(snapshot.post_review_items))),
        (_sc_label(lang, "supplemental_rounds"), str(snapshot.supplemental_round)),
        (_sc_label(lang, "execution_log_entries"), str(len(snapshot.execution_log))),
    ]
    if snapshot.execution_recovery is not None:
        rows.extend(execution_recovery_rows(snapshot, lang=lang))
    return tuple(rows)


def snapshot_has_current_context(snapshot: WorkflowNexusSnapshot) -> bool:
    return bool(
        snapshot.session_id
        or snapshot.goal
        or snapshot.round_num
        or snapshot.synthesis.summary
        or snapshot.synthesis.consensus_progress
        or snapshot.questions
        or snapshot.decisions
        or snapshot.central_work_packages
        or snapshot.work_packages
        or snapshot.subtasks
        or snapshot.work_package_repairs
        or snapshot.post_review_items
        or snapshot.follow_up_requests
        or snapshot.workflow_events
        or snapshot.execution_log
    )


def snapshot_context_markdown(
    snapshot: WorkflowNexusSnapshot,
    *,
    lang: str = "en",
) -> str:
    if not snapshot_has_current_context(snapshot):
        return context_no_current_markdown(lang=lang)

    lines = [
        f"- {_sc_label(lang, 'workflow')}: `{snapshot.session_id or _new_workflow_value(lang)}`",
        f"- {_sc_label(lang, 'state')}: `{_status_value(snapshot.state or 'idle', lang=lang)}`",
        f"- {_sc_label(lang, 'goal')}: {snapshot.goal or _none_value(lang)}",
        f"- {_sc_label(lang, 'round')}: `{snapshot.round_num}`",
    ]
    if snapshot.synthesis.consensus_progress:
        progress = display_consensus_progress(
            snapshot.synthesis.consensus_progress,
            lang=lang,
        )
        lines.append(
            f"- {_sc_label(lang, 'synthesis')}: "
            f"`{progress}`"
        )
    if snapshot.synthesis.summary:
        lines.extend(["", f"### {_sc_label(lang, 'synthesis')}", snapshot.synthesis.summary])
    if snapshot.questions:
        lines.extend(["", f"### {_sc_label(lang, 'questions')}"])
        for question in snapshot.questions:
            status = _question_status_value(question.status, lang=lang)
            lines.append(f"- **{question.id}** [{status}] {question.question}")
            if question.answer:
                lines.append(f"  - {_sc_label(lang, 'answer')}: {question.answer}")
    if snapshot.decisions:
        lines.extend(["", f"### {_sc_label(lang, 'decisions')}"])
        lines.extend(f"- {item}" for item in snapshot.decisions)
    packages = snapshot.work_packages or snapshot.central_work_packages
    if packages:
        lines.extend(["", f"### {_sc_label(lang, 'work_packages')}"])
        lines.extend(f"- {item}" for item in packages)
    if snapshot.subtasks:
        lines.extend(["", f"### {_sc_label(lang, 'subtasks')}"])
        for subtask in snapshot.subtasks:
            summary = subtask.result_summary or subtask.objective or _none_value(lang)
            status = _status_value(subtask.status, lang=lang)
            lines.append(
                f"- **{subtask.id or _unnamed_value(lang)}** "
                f"[{status}] "
                f"{subtask.parent_package_id or _no_package_value(lang)} -> "
                f"{subtask.delegated_to or _unknown_value(lang)}: {summary}"
            )
    if snapshot.work_package_repairs:
        lines.extend(["", f"### {_sc_label(lang, 'local_policy_repairs')}"])
        lines.extend(f"- {item}" for item in snapshot.work_package_repairs)
    if snapshot.final_review is not None:
        lines.extend(["", f"### {_sc_label(lang, 'final_review')}"])
        status = display_review_status_value(snapshot.final_review.status, lang=lang)
        if lang == "ko":
            lines.append(
                f"- `{status}` / "
                f"{_sc_label(lang, 'reviewer')} "
                f"`{snapshot.final_review.reviewer_agent or _unknown_value(lang)}`"
            )
        else:
            lines.append(
                f"- `{status}` by "
                f"`{snapshot.final_review.reviewer_agent or _unknown_value(lang)}`"
            )
        if snapshot.final_review.summary:
            lines.append(f"- {snapshot.final_review.summary}")
    if snapshot.post_review_items:
        lines.extend(["", f"### {_sc_label(lang, 'post_review_action_items')}"])
        for item in snapshot.post_review_items:
            status = _status_value(item.status, lang=lang)
            severity = display_severity_value(item.severity, lang=lang)
            lines.append(
                f"- **{item.id}** [{severity}][{status}] "
                f"{item.title or item.summary}"
            )
    if snapshot.follow_up_requests:
        lines.extend(["", f"### {_sc_label(lang, 'follow_up_requests')}"])
        lines.extend(f"- {item}" for item in snapshot.follow_up_requests)
    if snapshot.workflow_events:
        lines.extend(["", f"### {_sc_label(lang, 'workflow_history')}"])
        lines.extend(f"- {item}" for item in snapshot.workflow_events)
    extra_execution_log = [
        item for item in snapshot.execution_log if item not in snapshot.workflow_events
    ]
    if extra_execution_log:
        lines.extend(["", f"### {_sc_label(lang, 'execution_results')}"])
        lines.extend(f"- {item}" for item in extra_execution_log)
    return "\n".join(lines)


def context_title(*, lang: str = "en") -> str:
    return _sc_label(lang, "context")


def context_no_current_markdown(*, lang: str = "en") -> str:
    return _sc_label(lang, "context_no_current")


def memory_title(action: str = "stats", *, lang: str = "en") -> str:
    normalized = action.lower().strip()
    if normalized == "compact":
        return _sc_label(lang, "memory_compact")
    if normalized == "cleanup":
        return _sc_label(lang, "memory_cleanup")
    return _sc_label(lang, "memory_stats")


def memory_cleanup_error_markdown(error: str, *, lang: str = "en") -> str:
    if lang != "ko":
        return error
    if error == "--keep-latest requires a number.":
        return _sc_label(lang, "memory_cleanup_keep_latest_number")
    if error == "--keep-latest must be 0 or greater.":
        return _sc_label(lang, "memory_cleanup_keep_latest_range")
    usage = "Usage: `/memory cleanup --oversized-backups [--apply] [--keep-latest N]`"
    if error == usage:
        return _sc_label(lang, "memory_cleanup_usage")
    prefix = "Unknown cleanup option: "
    if error.startswith(prefix):
        return f"{_sc_label(lang, 'memory_cleanup_unknown_option')}: {error[len(prefix):]}"
    return error


def artifact_title(*, lang: str = "en") -> str:
    return _sc_label(lang, "artifact")


def artifact_usage_markdown(*, lang: str = "en") -> str:
    return _sc_label(lang, "artifact_usage")


def questions_action_hint(*, has_questions: bool, lang: str = "en") -> str:
    key = "question_hint" if has_questions else "continue_until_question"
    return _sc_label(lang, key)


def questions_table_columns(*, lang: str = "en") -> tuple[str, str, str, str]:
    return (
        _sc_label(lang, "id"),
        _sc_label(lang, "status"),
        _sc_label(lang, "question"),
        _sc_label(lang, "options"),
    )


def questions_markdown(
    snapshot: WorkflowNexusSnapshot,
    *,
    lang: str = "en",
) -> str:
    if not snapshot.questions:
        return _sc_label(lang, "no_pending_questions")
    lines: list[str] = []
    for index, question in enumerate(snapshot.questions, start=1):
        status = _question_status_value(question.status, lang=lang)
        lines.append(f"{index}. **{question.id}** [{status}] {question.question}")
        if question.answer:
            lines.append(f"   - {_sc_label(lang, 'answer')}: {question.answer}")
        if question.recommended_option:
            lines.append(
                f"   - {_sc_label(lang, 'recommended')}: {question.recommended_option}"
            )
        for option_index, option in enumerate(question.options, start=1):
            lines.append(f"   - {option_index}. {option}")
    lines.append("")
    lines.append(_sc_label(lang, "question_hint"))
    return "\n".join(lines)


def questions_select_markdown(
    snapshot: WorkflowNexusSnapshot,
    *,
    lang: str = "en",
) -> str:
    if not snapshot.questions:
        return _sc_label(lang, "no_pending_questions_select")
    question = snapshot.questions[0]
    lines = [
        f"{_sc_label(lang, 'selected_question')}: **{question.id}**",
        question.question,
    ]
    if question.options:
        lines.append("")
        lines.append(_sc_label(lang, "question_select_hint"))
        for index, option in enumerate(question.options, start=1):
            lines.append(f"- {index}. {option}")
    else:
        lines.append("")
        lines.append(_sc_label(lang, "no_predefined_options"))
        lines.append(_sc_label(lang, "question_answer_usage"))
    return "\n".join(lines)


def questions_rows(
    snapshot: WorkflowNexusSnapshot,
    *,
    lang: str = "en",
) -> tuple[tuple[str, str, str, str], ...]:
    return tuple(
        (
            question.id,
            _question_status_value(question.status, lang=lang),
            question.question,
            ", ".join(question.options) if question.options else _sc_label(lang, "free_text"),
        )
        for question in snapshot.questions
    )


def decisions_action_hint(*, has_decisions: bool, lang: str = "en") -> str:
    return "" if has_decisions else _sc_label(lang, "decision_hint")


def decisions_table_columns(*, lang: str = "en") -> tuple[str, str]:
    return ("#", _sc_label(lang, "decision"))


def decisions_markdown(
    snapshot: WorkflowNexusSnapshot,
    *,
    lang: str = "en",
) -> str:
    if not snapshot.decisions:
        return _sc_label(lang, "no_decisions")
    return "\n".join(
        f"{index}. {decision}" for index, decision in enumerate(snapshot.decisions, start=1)
    )


def decisions_rows(
    snapshot: WorkflowNexusSnapshot,
    *,
    lang: str = "en",
) -> tuple[tuple[str, str], ...]:
    return tuple(
        (str(index), decision) for index, decision in enumerate(snapshot.decisions, start=1)
    )


def packages_action_hint(*, has_packages: bool, lang: str = "en") -> str:
    return "" if has_packages else _sc_label(lang, "packages_hint")


def packages_table_columns(*, lang: str = "en") -> tuple[str, str, str]:
    return ("#", _sc_label(lang, "source"), _sc_label(lang, "package"))


def packages_markdown(
    snapshot: WorkflowNexusSnapshot,
    *,
    lang: str = "en",
) -> str:
    rows = packages_rows(snapshot, lang=lang)
    if not rows:
        return _sc_label(lang, "no_packages")
    lines = []
    for index, source, package in rows:
        lines.append(f"{index}. **{source}** {package}")
    return "\n".join(lines)


def packages_rows(
    snapshot: WorkflowNexusSnapshot,
    *,
    lang: str = "en",
) -> tuple[tuple[str, str, str], ...]:
    rows: list[tuple[str, str, str]] = []
    for package in snapshot.central_work_packages:
        rows.append((str(len(rows) + 1), _sc_label(lang, "central"), package))
    for package in snapshot.work_packages:
        rows.append((str(len(rows) + 1), _sc_label(lang, "local"), package))
    return tuple(rows)


def review_action_hint(*, lang: str = "en") -> str:
    return _sc_label(lang, "review_hint")


def review_title(*, lang: str = "en") -> str:
    return _sc_label(lang, "review_title")


def review_table_columns(*, lang: str = "en") -> tuple[str, str]:
    return status_table_columns(lang=lang)


def review_rows(
    snapshot: WorkflowNexusSnapshot,
    *,
    lang: str = "en",
) -> tuple[tuple[str, str], ...]:
    rows: list[tuple[str, str]] = [
        (_sc_label(lang, "workflow"), snapshot.session_id or _new_workflow_value(lang)),
        (_sc_label(lang, "state"), _status_value(snapshot.state or "idle", lang=lang)),
        (_sc_label(lang, "work_packages"), str(len(snapshot.work_package_details))),
    ]
    pending = [
        package.id for package in snapshot.work_package_details if not package.review_status
    ]
    reviewed = []
    for package in snapshot.work_package_details:
        if not package.review_status:
            continue
        status = display_review_status_value(
            package.review_status,
            reviewer_agent=package.reviewer_agent,
            summary=package.review_summary,
            lang=lang,
        )
        reviewed.append(f"{package.id}:{status}")
    rows.append((_sc_label(lang, "pending_wp_review"), ", ".join(pending) or _none_value(lang)))
    rows.append((_sc_label(lang, "reviewed_wp"), ", ".join(reviewed) or _none_value(lang)))
    if snapshot.final_review is not None:
        reviewer = snapshot.final_review.reviewer_agent or _unknown_value(lang)
        status = display_review_status_value(snapshot.final_review.status, lang=lang)
        final_review_value = (
            f"{status} / {_sc_label(lang, 'reviewer')} {reviewer}"
            if lang == "ko"
            else f"{status} by {reviewer}"
        )
        rows.append(
            (
                _sc_label(lang, "final_review"),
                final_review_value,
            )
        )
    else:
        rows.append((_sc_label(lang, "final_review"), _none_value(lang)))
    return tuple(rows)


def improve_action_hint(*, lang: str = "en") -> str:
    return _sc_label(lang, "improve_hint")


def improve_title(*, lang: str = "en") -> str:
    return _sc_label(lang, "improve")


def improve_table_columns(*, lang: str = "en") -> tuple[str, str]:
    return status_table_columns(lang=lang)


def improve_rows(
    snapshot: WorkflowNexusSnapshot,
    *,
    lang: str = "en",
) -> tuple[tuple[str, str], ...]:
    rows: list[tuple[str, str]] = [
        (_sc_label(lang, "workflow"), snapshot.session_id or _new_workflow_value(lang)),
        (_sc_label(lang, "state"), _status_value(snapshot.state or "idle", lang=lang)),
        (_sc_label(lang, "supplemental_rounds"), str(snapshot.supplemental_round)),
    ]
    if not snapshot.post_review_items:
        rows.append((_sc_label(lang, "action_items"), _none_value(lang)))
        return tuple(rows)
    for item in snapshot.post_review_items:
        status = _status_value(item.status, lang=lang)
        severity = display_severity_value(item.severity, lang=lang)
        kind = display_kind_value(item.kind, lang=lang)
        rows.append(
            (
                item.id,
                (
                    f"{status}; {_sc_label(lang, 'severity')}={severity}; "
                    f"{_sc_label(lang, 'kind')}={kind}; "
                    f"{_sc_label(lang, 'title')}={item.title or item.summary}"
                ),
            )
        )
    return tuple(rows)


def subtasks_action_hint(*, has_subtasks: bool, lang: str = "en") -> str:
    return "" if has_subtasks else _sc_label(lang, "subtasks_hint")


def subtasks_table_columns(*, lang: str = "en") -> tuple[str, str, str, str, str]:
    return (
        _sc_label(lang, "id"),
        _sc_label(lang, "package"),
        _sc_label(lang, "delegated_to"),
        _sc_label(lang, "status"),
        _sc_label(lang, "summary"),
    )


def subtasks_markdown(
    snapshot: WorkflowNexusSnapshot,
    *,
    lang: str = "en",
) -> str:
    if not snapshot.subtasks:
        return _sc_label(lang, "no_subtasks")
    lines = []
    for index, subtask in enumerate(snapshot.subtasks, start=1):
        summary = subtask.result_summary or subtask.objective or _none_value(lang)
        status = _status_value(subtask.status, lang=lang)
        lines.append(
            f"{index}. **{subtask.id or _unnamed_value(lang)}** "
            f"[{status}] "
            f"{subtask.parent_package_id or _no_package_value(lang)} -> "
            f"{subtask.delegated_to or _unknown_value(lang)}: {summary}"
        )
    return "\n".join(lines)


def subtasks_rows(
    snapshot: WorkflowNexusSnapshot,
    *,
    lang: str = "en",
) -> tuple[tuple[str, str, str, str, str], ...]:
    return tuple(
        (
            subtask.id or _unnamed_value(lang),
            subtask.parent_package_id or _none_value(lang),
            subtask.delegated_to or _unknown_value(lang),
            _status_value(subtask.status, lang=lang),
            subtask.result_summary or subtask.objective or _none_value(lang),
        )
        for subtask in snapshot.subtasks
    )


def history_action_hint(*, has_history: bool, lang: str = "en") -> str:
    return "" if has_history else _sc_label(lang, "history_hint")


def history_table_columns(*, lang: str = "en") -> tuple[str, str]:
    return (_sc_label(lang, "kind"), _sc_label(lang, "item"))


def history_rows(
    snapshot: WorkflowNexusSnapshot,
    local_command_results: Sequence[object] = (),
    *,
    lang: str = "en",
) -> tuple[tuple[str, str], ...]:
    rows: list[tuple[str, str]] = []
    if snapshot.session_id or snapshot.goal:
        rows.append((_sc_label(lang, "workflow"), snapshot.session_id or _new_workflow_value(lang)))
        rows.append((_sc_label(lang, "state"), _status_value(snapshot.state or "idle", lang=lang)))
        rows.append((_sc_label(lang, "round"), str(snapshot.round_num)))
        if snapshot.goal:
            rows.append((_sc_label(lang, "goal"), snapshot.goal))
    for command in local_command_results[-10:]:
        rows.append(
            (
                _sc_label(lang, "local_command"),
                f"{getattr(command, 'command', '')} - {getattr(command, 'title', '')}",
            )
        )
    for entry in snapshot.execution_log[-10:]:
        rows.append((_sc_label(lang, "execution"), entry))
    return tuple(rows)


def history_markdown(
    snapshot: WorkflowNexusSnapshot,
    rows: tuple[tuple[str, str], ...],
    *,
    lang: str = "en",
) -> str:
    if not rows:
        return _sc_label(lang, "no_history")
    lines = [
        f"- {_sc_label(lang, 'workflow')}: `{snapshot.session_id or _new_workflow_value(lang)}`",
        f"- {_sc_label(lang, 'state')}: `{_status_value(snapshot.state or 'idle', lang=lang)}`",
        f"- {_sc_label(lang, 'round')}: `{snapshot.round_num}`",
    ]
    if snapshot.goal:
        lines.append(f"- {_sc_label(lang, 'goal')}: {snapshot.goal}")
    if snapshot.execution_log:
        lines.extend(["", f"### {_sc_label(lang, 'recent_execution_log')}"])
        lines.extend(f"- {entry}" for entry in snapshot.execution_log[-10:])
    if rows:
        lines.extend(["", f"### {_sc_label(lang, 'recent_local_items')}"])
        lines.extend(f"- **{kind}**: {item}" for kind, item in rows[-12:])
    return "\n".join(lines)


def resume_title(*, lang: str = "en") -> str:
    return _sc_label(lang, "resume")


def resume_no_saved_markdown(*, lang: str = "en") -> str:
    return _sc_label(lang, "resume_no_saved")


def resume_no_saved_action_hint(*, lang: str = "en") -> str:
    return _sc_label(lang, "resume_empty_hint")


def resume_pick_action_hint(*, lang: str = "en") -> str:
    return _sc_label(lang, "resume_pick_hint")


def resume_cancelled_markdown(*, lang: str = "en") -> str:
    return _sc_label(lang, "resume_cancelled")


def resume_cancel_action_hint(*, lang: str = "en") -> str:
    return _sc_label(lang, "resume_cancel_hint")


def resume_archive_table_columns(*, lang: str = "en") -> tuple[str, str, str, str]:
    return (
        _sc_label(lang, "selector"),
        _sc_label(lang, "workflow"),
        _sc_label(lang, "state"),
        _sc_label(lang, "goal"),
    )


def resume_result_table_columns(*, lang: str = "en") -> tuple[str, str]:
    return status_table_columns(lang=lang)


def resume_archives_markdown(archives: list[object], *, lang: str = "en") -> str:
    lines = [_sc_label(lang, "resume_archives_available")]
    for archive in archives:
        selector = str(getattr(archive, "selector", ""))
        session_id = str(getattr(archive, "session_id", ""))
        state = _status_value(str(getattr(archive, "state", "")), lang=lang)
        goal = str(getattr(archive, "goal", "")).strip() or _sc_label(lang, "no_goal")
        lines.append(f"- `{selector}` {session_id} [{state}] {goal}")
    return "\n".join(lines)


def resume_archive_rows(
    archives: list[object],
    *,
    lang: str = "en",
) -> tuple[tuple[str, str, str, str], ...]:
    return tuple(
        (
            str(getattr(archive, "selector", "")),
            str(getattr(archive, "session_id", "")),
            _status_value(str(getattr(archive, "state", "")), lang=lang),
            str(getattr(archive, "goal", "")).strip() or _sc_label(lang, "no_goal"),
        )
        for archive in archives
    )


def resume_result_rows(
    snapshot: WorkflowNexusSnapshot,
    *,
    lang: str = "en",
) -> tuple[tuple[str, str], ...]:
    return (
        (_sc_label(lang, "workflow"), snapshot.session_id or _new_workflow_value(lang)),
        (_sc_label(lang, "state"), _status_value(snapshot.state or "idle", lang=lang)),
        (_sc_label(lang, "goal"), snapshot.goal or _none_value(lang)),
        (_sc_label(lang, "round"), str(snapshot.round_num)),
    )
