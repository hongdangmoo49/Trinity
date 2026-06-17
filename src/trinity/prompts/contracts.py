"""Central output contract registry for Trinity provider turns."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class OutputContract:
    """A provider-facing response format contract."""

    id: str
    mode: str
    required_sections: tuple[str, ...]
    optional_sections: tuple[str, ...] = ()
    status_field: str = ""
    allowed_statuses: tuple[str, ...] = ()
    parser: str = ""
    instructions: str = ""
    localized_instructions: dict[str, str] = field(default_factory=dict)

    def render(self, lang: str = "en", **kwargs: object) -> str:
        """Render instructions for prompt inclusion."""
        template = self.localized_instructions.get(lang, self.instructions)
        return template.format(**kwargs).strip()


EXECUTION_CONTRACT_ID = "execution_v1"
REVIEW_CONTRACT_ID = "review_v1"
FINAL_REVIEW_CONTRACT_ID = "final_review_v1"
REPAIR_CONTRACT_ID = "repair_v1"
PLAN_CONTRACT_ID = "plan_v1"
CHAT_CONTRACT_ID = "chat_v1"
DELIBERATION_CONTRACT_ID = "deliberation_round_v1"


_CONTRACTS: dict[str, OutputContract] = {
    EXECUTION_CONTRACT_ID: OutputContract(
        id=EXECUTION_CONTRACT_ID,
        mode="execute",
        required_sections=(
            "Completed",
            "Files Changed",
            "Decisions Made",
            "Blockers",
            "Follow-up",
            "Subtasks",
        ),
        optional_sections=("Tests", "Verification"),
        parser="execution_response_v1",
        instructions=(
            "OUTPUT CONTRACT: execution_v1\n"
            "## Completed\n"
            "## Files Changed\n"
            "## Decisions Made\n"
            "## Blockers\n"
            "## Follow-up\n"
            "## Subtasks\n"
            "### ST-001\n"
            "- delegated_to: <subagent/tool or none>\n"
            "- objective: <input objective>\n"
            "- result_summary: <output summary>\n"
            "- status: done | blocked | failed\n"
            "- decisions_made: <comma-separated decisions or none>\n"
            "- files_changed: <comma-separated files or none>\n"
            "- unresolved_issues: <comma-separated issues or none>"
        ),
    ),
    REVIEW_CONTRACT_ID: OutputContract(
        id=REVIEW_CONTRACT_ID,
        mode="review",
        required_sections=(
            "REVIEW STATUS",
            "SEVERITY",
            "SUMMARY",
            "FINDINGS",
            "REQUIRED CHANGES",
            "REVIEWED FILES",
            "EXECUTION RISKS",
            "ANTI PATTERNS",
            "PERFORMANCE NOTES",
            "FOLLOW UP",
        ),
        status_field="REVIEW STATUS",
        allowed_statuses=("APPROVED", "CHANGES_REQUESTED", "BLOCKED"),
        parser="review_response_v1",
        instructions=(
            "OUTPUT CONTRACT: review_v1\n"
            "REVIEW STATUS: APPROVED | CHANGES_REQUESTED | BLOCKED\n"
            "SEVERITY: LOW | MEDIUM | HIGH | CRITICAL\n\n"
            "SUMMARY:\n"
            "...\n\n"
            "FINDINGS:\n"
            "- ...\n\n"
            "REQUIRED CHANGES:\n"
            "- ...\n\n"
            "REVIEWED FILES:\n"
            "- ...\n\n"
            "EXECUTION RISKS:\n"
            "- ...\n\n"
            "ANTI PATTERNS:\n"
            "- ...\n\n"
            "PERFORMANCE NOTES:\n"
            "- ...\n\n"
            "FOLLOW UP:\n"
            "- ..."
        ),
    ),
    FINAL_REVIEW_CONTRACT_ID: OutputContract(
        id=FINAL_REVIEW_CONTRACT_ID,
        mode="final_review",
        required_sections=(
            "FINAL REVIEW STATUS",
            "SEVERITY",
            "PROJECT OVERVIEW",
            "COMPATIBILITY",
            "RUN INSTRUCTIONS",
            "CRITICAL RISKS",
            "RECOMMENDED FEATURES",
            "REQUIRED CHANGES",
            "FOLLOW UP",
        ),
        status_field="FINAL REVIEW STATUS",
        allowed_statuses=("APPROVED", "CHANGES_REQUESTED", "BLOCKED"),
        parser="review_response_v1",
        instructions=(
            "OUTPUT CONTRACT: final_review_v1\n"
            "FINAL REVIEW STATUS: APPROVED | CHANGES_REQUESTED | BLOCKED\n"
            "SEVERITY: LOW | MEDIUM | HIGH | CRITICAL\n\n"
            "PROJECT OVERVIEW:\n"
            "...\n\n"
            "COMPATIBILITY:\n"
            "- ...\n\n"
            "RUN INSTRUCTIONS:\n"
            "- ...\n\n"
            "CRITICAL RISKS:\n"
            "- ...\n\n"
            "RECOMMENDED FEATURES:\n"
            "- ...\n\n"
            "REQUIRED CHANGES:\n"
            "- ...\n\n"
            "FOLLOW UP:\n"
            "- ..."
        ),
    ),
    REPAIR_CONTRACT_ID: OutputContract(
        id=REPAIR_CONTRACT_ID,
        mode="repair",
        required_sections=(
            "Repair Summary",
            "Addressed Findings",
            "Files Changed",
            "Tests",
            "Remaining Risk",
            "Follow-up",
        ),
        parser="execution_response_v1",
        instructions=(
            "OUTPUT CONTRACT: repair_v1\n"
            "## Repair Summary\n"
            "## Addressed Findings\n"
            "## Files Changed\n"
            "## Tests\n"
            "## Remaining Risk\n"
            "## Follow-up"
        ),
    ),
    PLAN_CONTRACT_ID: OutputContract(
        id=PLAN_CONTRACT_ID,
        mode="plan",
        required_sections=(
            "Goal",
            "Current State",
            "Proposed Design",
            "Work Packages",
            "Risks",
            "Acceptance Criteria",
            "Open Questions",
        ),
        instructions=(
            "OUTPUT CONTRACT: plan_v1\n"
            "## Goal\n"
            "## Current State\n"
            "## Proposed Design\n"
            "## Work Packages\n"
            "## Risks\n"
            "## Acceptance Criteria\n"
            "## Open Questions"
        ),
    ),
    CHAT_CONTRACT_ID: OutputContract(
        id=CHAT_CONTRACT_ID,
        mode="chat",
        required_sections=(),
        instructions=(
            "OUTPUT CONTRACT: chat_v1\n"
            "- Match the user's language.\n"
            "- Do not edit files in chat mode.\n"
            "- State uncertainty when facts need verification."
        ),
    ),
    DELIBERATION_CONTRACT_ID: OutputContract(
        id=DELIBERATION_CONTRACT_ID,
        mode="deliberation",
        required_sections=("VOTE",),
        status_field="VOTE",
        allowed_statuses=(
            "APPROVE",
            "APPROVE_WITH_CHANGES",
            "BLOCKED_BY_QUESTION",
            "REJECT",
        ),
        instructions=(
            "Structured deliberation contract:\n"
            "- Phase: {phase}.\n"
            "- End with exactly one vote line: "
            "VOTE: APPROVE | APPROVE_WITH_CHANGES | "
            "BLOCKED_BY_QUESTION | REJECT.\n"
            "- If a final design is possible, include a BLUEPRINT with "
            "Title, Summary, Architecture, Data Flow, External Dependencies, "
            "Risks, and Acceptance Criteria sections.\n"
            "- If user input is required, vote BLOCKED_BY_QUESTION and include "
            "OPEN QUESTIONS with Question, Options, Recommended, and Rationale."
        ),
        localized_instructions={
            "ko": (
                "응답 언어 규칙:\n"
                "- 사용자에게 보이는 설명, 제목, 요약, 질문, 선택지, 추천, 근거는 반드시 한국어로 작성하세요.\n"
                "- 영어로 된 사용자-facing 문장, 질문, 선택지는 만들지 마세요.\n"
                "- 파서 호환을 위해 마지막 투표 줄만 다음 영어 토큰 중 하나를 그대로 사용하세요: "
                "VOTE: APPROVE | APPROVE_WITH_CHANGES | BLOCKED_BY_QUESTION | REJECT.\n\n"
                "구조화된 토론 계약:\n"
                "- 단계: {phase}.\n"
                "- 최종 설계가 가능하면 제목, 요약, 아키텍처, 데이터 흐름, 외부 의존성, "
                "리스크, 수용 기준 섹션을 포함하세요.\n"
                "- 사용자 입력이 필요하면 BLOCKED_BY_QUESTION으로 투표하고, "
                "질문, 선택지, 추천, 근거를 한국어로 작성하세요."
            )
        },
    ),
}


def get_output_contract(contract_id: str) -> OutputContract:
    """Return a registered output contract."""
    try:
        return _CONTRACTS[contract_id]
    except KeyError as exc:
        raise ValueError(f"Unknown output contract: {contract_id}") from exc


def render_output_contract(contract_id: str, lang: str = "en", **kwargs: object) -> str:
    """Render a registered output contract."""
    return get_output_contract(contract_id).render(lang=lang, **kwargs)

