"""Structured deliberation synthesis for workflow blueprints."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from trinity.workflow.models import OpenQuestion


class VoteType(str, Enum):
    """Structured vote emitted by an agent during synthesis."""

    APPROVE = "approve"
    APPROVE_WITH_CHANGES = "approve_with_changes"
    BLOCKED_BY_QUESTION = "blocked_by_question"
    REJECT = "reject"


@dataclass
class ArchitectureComponent:
    """A major component in a proposed blueprint."""

    name: str
    responsibility: str
    owner_agent: str | None = None
    dependencies: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "responsibility": self.responsibility,
            "owner_agent": self.owner_agent,
            "dependencies": list(self.dependencies),
        }


@dataclass
class RiskItem:
    """A risk captured from a proposed blueprint."""

    description: str
    severity: str = "medium"
    mitigation: str = ""
    owner_agent: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "description": self.description,
            "severity": self.severity,
            "mitigation": self.mitigation,
            "owner_agent": self.owner_agent,
        }


@dataclass
class Blueprint:
    """Structured design conclusion produced by deliberation."""

    title: str
    summary: str
    architecture: list[ArchitectureComponent] = field(default_factory=list)
    data_flow: list[str] = field(default_factory=list)
    external_dependencies: list[str] = field(default_factory=list)
    risks: list[RiskItem] = field(default_factory=list)
    acceptance_criteria: list[str] = field(default_factory=list)
    open_questions: list[OpenQuestion] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        """Return whether this blueprint has enough substance to finalize."""
        has_design_detail = any(
            (
                self.architecture,
                self.data_flow,
                self.external_dependencies,
                self.acceptance_criteria,
            )
        )
        return bool(self.title.strip() and self.summary.strip() and has_design_detail)

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "summary": self.summary,
            "architecture": [item.to_dict() for item in self.architecture],
            "data_flow": list(self.data_flow),
            "external_dependencies": list(self.external_dependencies),
            "risks": [item.to_dict() for item in self.risks],
            "acceptance_criteria": list(self.acceptance_criteria),
            "open_questions": [item.to_dict() for item in self.open_questions],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Blueprint":
        architecture = [
            ArchitectureComponent(
                name=str(item.get("name", "")),
                responsibility=str(item.get("responsibility", "")),
                owner_agent=(
                    str(item["owner_agent"])
                    if item.get("owner_agent") is not None
                    else None
                ),
                dependencies=[str(dep) for dep in item.get("dependencies", [])],
            )
            for item in data.get("architecture", [])
            if isinstance(item, dict)
        ]
        risks = [
            RiskItem(
                description=str(item.get("description", "")),
                severity=str(item.get("severity", "medium")),
                mitigation=str(item.get("mitigation", "")),
                owner_agent=(
                    str(item["owner_agent"])
                    if item.get("owner_agent") is not None
                    else None
                ),
            )
            for item in data.get("risks", [])
            if isinstance(item, dict)
        ]
        questions = [
            OpenQuestion.from_dict(item)
            for item in data.get("open_questions", [])
            if isinstance(item, dict)
        ]
        return cls(
            title=str(data.get("title", "")),
            summary=str(data.get("summary", "")),
            architecture=architecture,
            data_flow=[str(item) for item in data.get("data_flow", [])],
            external_dependencies=[
                str(item) for item in data.get("external_dependencies", [])
            ],
            risks=risks,
            acceptance_criteria=[
                str(item) for item in data.get("acceptance_criteria", [])
            ],
            open_questions=questions,
        )


@dataclass
class StructuredVote:
    """One agent's structured vote and extracted artifacts."""

    agent_name: str
    vote: VoteType
    rationale: str = ""
    blueprint: Blueprint | None = None
    open_questions: list[OpenQuestion] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_name": self.agent_name,
            "vote": self.vote.value,
            "rationale": self.rationale,
            "blueprint": self.blueprint.to_dict() if self.blueprint else None,
            "open_questions": [item.to_dict() for item in self.open_questions],
            "blockers": list(self.blockers),
        }


@dataclass
class StructuredConsensusResult:
    """Structured result for workflow state transitions."""

    reached: bool
    vote_count: dict[VoteType, int]
    final_blueprint: Blueprint | None = None
    open_questions: list[OpenQuestion] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    votes: dict[str, StructuredVote] = field(default_factory=dict)
    summary: str = ""

    @property
    def approval_count(self) -> int:
        return self.vote_count.get(VoteType.APPROVE, 0) + self.vote_count.get(
            VoteType.APPROVE_WITH_CHANGES,
            0,
        )

    @property
    def total_votes(self) -> int:
        return sum(self.vote_count.values())

    def to_dict(self) -> dict[str, Any]:
        return {
            "reached": self.reached,
            "vote_count": {key.value: value for key, value in self.vote_count.items()},
            "approval_count": self.approval_count,
            "total_votes": self.total_votes,
            "final_blueprint": (
                self.final_blueprint.to_dict() if self.final_blueprint else None
            ),
            "open_questions": [item.to_dict() for item in self.open_questions],
            "blockers": list(self.blockers),
            "votes": {name: vote.to_dict() for name, vote in self.votes.items()},
            "summary": self.summary,
        }


class StructuredConsensusSynthesizer:
    """Extract votes, blueprints, and user questions from agent opinions."""

    SECTION_ALIASES = {
        "title": {"title", "제목"},
        "summary": {"summary", "요약"},
        "architecture": {
            "architecture",
            "components",
            "architecture components",
            "아키텍처",
            "구성요소",
        },
        "data_flow": {"data flow", "flow", "데이터 흐름", "흐름"},
        "external_dependencies": {
            "external dependencies",
            "dependencies",
            "외부 의존성",
            "의존성",
        },
        "risks": {"risks", "risk", "위험", "리스크"},
        "acceptance_criteria": {
            "acceptance criteria",
            "criteria",
            "완료 기준",
            "수용 기준",
        },
        "open_questions": {
            "open questions",
            "questions",
            "user questions",
            "사용자 질문",
            "질문",
        },
        "blockers": {"blockers", "blocking issues", "차단 사유", "블로커"},
    }

    VOTE_PATTERN = re.compile(
        r"\b(APPROVE_WITH_CHANGES|BLOCKED_BY_QUESTION|APPROVE|REJECT)\b",
        re.IGNORECASE,
    )
    TITLE_PATTERN = re.compile(r"^\s*(?:[-*]\s*)?title\s*:\s*(.+)$", re.IGNORECASE)
    SUMMARY_PATTERN = re.compile(
        r"^\s*(?:[-*]\s*)?summary\s*:\s*(.+)$",
        re.IGNORECASE,
    )
    QUESTION_PATTERN = re.compile(
        r"^\s*(?:[-*]\s*)?(?:q(?:uestion)?\s*[:.)-]\s*)?(.+\?)\s*$",
        re.IGNORECASE,
    )
    QUESTION_FIELD_PATTERN = re.compile(
        r"^\s*(?:[-*]\s*)?question\s*:\s*(.+)$",
        re.IGNORECASE,
    )
    OPTIONS_PATTERN = re.compile(
        r"^\s*(?:[-*]\s*)?options?\s*:\s*(.+)$",
        re.IGNORECASE,
    )
    RECOMMENDED_PATTERN = re.compile(
        r"^\s*(?:[-*]\s*)?recommended(?:_option)?\s*:\s*(.+)$",
        re.IGNORECASE,
    )
    RATIONALE_PATTERN = re.compile(
        r"^\s*(?:[-*]\s*)?rationale\s*:\s*(.+)$",
        re.IGNORECASE,
    )

    def __init__(self, required_fraction: float = 0.6):
        self.required_fraction = required_fraction

    def evaluate(self, opinions: dict[str, str]) -> StructuredConsensusResult:
        """Evaluate structured consensus from usable agent opinion text."""
        votes = {
            agent_name: self.extract_vote(agent_name, text)
            for agent_name, text in opinions.items()
            if text and text.strip()
        }
        vote_count = {vote_type: 0 for vote_type in VoteType}
        for vote in votes.values():
            vote_count[vote.vote] += 1

        open_questions = self._dedupe_questions(
            question
            for vote in votes.values()
            for question in vote.open_questions
        )
        blockers = [
            blocker
            for vote in votes.values()
            for blocker in vote.blockers
            if blocker.strip()
        ]
        final_blueprint = self._select_blueprint(votes)

        reached = self._has_reached_consensus(
            votes=votes,
            final_blueprint=final_blueprint,
            open_questions=open_questions,
        )
        summary = self._build_summary(
            reached=reached,
            votes=votes,
            final_blueprint=final_blueprint,
            open_questions=open_questions,
            blockers=blockers,
        )
        return StructuredConsensusResult(
            reached=reached,
            vote_count=vote_count,
            final_blueprint=final_blueprint,
            open_questions=open_questions,
            blockers=blockers,
            votes=votes,
            summary=summary,
        )

    def extract_vote(self, agent_name: str, text: str) -> StructuredVote:
        """Extract a single agent's structured vote from free-form text."""
        json_payload = self._extract_json_payload(text)
        if json_payload:
            return self._vote_from_json(agent_name, json_payload, text)

        blueprint = self._extract_blueprint(text)
        open_questions = self._extract_open_questions(agent_name, text)
        blockers = self._extract_blockers(text)
        vote_type = self._extract_vote_type(text, blueprint, open_questions, blockers)
        rationale = self._extract_rationale(text, blockers)
        return StructuredVote(
            agent_name=agent_name,
            vote=vote_type,
            rationale=rationale,
            blueprint=blueprint if blueprint and blueprint.is_valid else None,
            open_questions=open_questions,
            blockers=blockers,
        )

    def _has_reached_consensus(
        self,
        votes: dict[str, StructuredVote],
        final_blueprint: Blueprint | None,
        open_questions: list[OpenQuestion],
    ) -> bool:
        if not votes or final_blueprint is None or open_questions:
            return False

        total = len(votes)
        approval_count = sum(
            1
            for vote in votes.values()
            if vote.vote in {VoteType.APPROVE, VoteType.APPROVE_WITH_CHANGES}
        )
        if total == 1:
            return approval_count == 1
        return approval_count / total >= self.required_fraction

    def _select_blueprint(
        self,
        votes: dict[str, StructuredVote],
    ) -> Blueprint | None:
        blueprints = [
            vote.blueprint
            for vote in votes.values()
            if vote.blueprint is not None and vote.blueprint.is_valid
        ]
        if not blueprints:
            return None

        def score(blueprint: Blueprint) -> int:
            return (
                len(blueprint.architecture) * 3
                + len(blueprint.data_flow)
                + len(blueprint.external_dependencies)
                + len(blueprint.acceptance_criteria)
                + len(blueprint.risks)
            )

        return max(blueprints, key=score)

    def _extract_vote_type(
        self,
        text: str,
        blueprint: Blueprint | None,
        open_questions: list[OpenQuestion],
        blockers: list[str],
    ) -> VoteType:
        match = self.VOTE_PATTERN.search(text)
        if match:
            raw = match.group(1).upper()
            if raw == "APPROVE_WITH_CHANGES":
                return VoteType.APPROVE_WITH_CHANGES
            if raw == "BLOCKED_BY_QUESTION":
                return VoteType.BLOCKED_BY_QUESTION
            if raw == "REJECT":
                return VoteType.REJECT
            return VoteType.APPROVE

        normalized = text.lower()
        if open_questions or "사용자 결정" in text:
            return VoteType.BLOCKED_BY_QUESTION
        if blockers or re.search(r"\b(reject|rejected|cannot approve)\b", normalized):
            return VoteType.REJECT
        if re.search(r"\bapprove(?:d)?\b|\bagree(?:d)?\b", normalized):
            return VoteType.APPROVE
        if blueprint and blueprint.is_valid:
            return VoteType.APPROVE
        return VoteType.REJECT

    def _extract_blueprint(self, text: str) -> Blueprint | None:
        sections = self._parse_sections(text)
        title = self._extract_title(text, sections)
        summary = self._extract_summary(text, sections)
        architecture = [
            self._component_from_line(line)
            for line in sections.get("architecture", [])
            if self._clean_list_item(line)
        ]
        data_flow = self._clean_list(sections.get("data_flow", []))
        external_dependencies = self._clean_list(
            sections.get("external_dependencies", [])
        )
        risks = [
            RiskItem(description=item)
            for item in self._clean_list(sections.get("risks", []))
        ]
        acceptance_criteria = self._clean_list(
            sections.get("acceptance_criteria", [])
        )
        open_questions = self._questions_from_section(
            "blueprint",
            sections.get("open_questions", []),
        )
        blueprint = Blueprint(
            title=title,
            summary=summary,
            architecture=architecture,
            data_flow=data_flow,
            external_dependencies=external_dependencies,
            risks=risks,
            acceptance_criteria=acceptance_criteria,
            open_questions=open_questions,
        )
        return blueprint if blueprint.is_valid else None

    def _parse_sections(self, text: str) -> dict[str, list[str]]:
        sections: dict[str, list[str]] = {}
        current: str | None = None
        for line in text.splitlines():
            section = self._section_key(line)
            if section:
                current = section
                inline_value = self._inline_section_value(line)
                if inline_value:
                    sections.setdefault(section, []).append(inline_value)
                else:
                    sections.setdefault(section, [])
                continue
            if current is not None:
                sections.setdefault(current, []).append(line)
        return sections

    def _section_key(self, line: str) -> str | None:
        heading = line.strip().strip("#").strip()
        heading = re.sub(r"^\d+[.)]\s*", "", heading)
        heading = heading.rstrip(":").strip().lower()
        if not heading:
            return None

        for key, aliases in self.SECTION_ALIASES.items():
            if heading in aliases:
                return key
        return None

    @staticmethod
    def _inline_section_value(line: str) -> str:
        stripped = line.strip()
        if ":" not in stripped:
            return ""
        before, after = stripped.split(":", 1)
        if len(before.split()) > 4:
            return ""
        return after.strip()

    def _extract_title(self, text: str, sections: dict[str, list[str]]) -> str:
        for line in text.splitlines():
            match = self.TITLE_PATTERN.match(line)
            if match:
                return match.group(1).strip()
            stripped = line.strip()
            if stripped.startswith("#") and not stripped.lower().startswith(
                ("## summary", "## architecture"),
            ):
                return stripped.strip("#").strip()
        title_lines = self._clean_list(sections.get("title", []))
        if title_lines:
            return title_lines[0]
        return "Proposed Blueprint"

    def _extract_summary(self, text: str, sections: dict[str, list[str]]) -> str:
        for line in text.splitlines():
            match = self.SUMMARY_PATTERN.match(line)
            if match:
                return match.group(1).strip()
        summary_lines = self._clean_list(sections.get("summary", []))
        if summary_lines:
            return " ".join(summary_lines[:3])
        return self._first_paragraph(text)

    def _component_from_line(self, line: str) -> ArchitectureComponent:
        item = self._clean_list_item(line)
        if ":" in item:
            name, responsibility = item.split(":", 1)
        elif " - " in item:
            name, responsibility = item.split(" - ", 1)
        else:
            name, responsibility = item, item
        return ArchitectureComponent(
            name=name.strip(),
            responsibility=responsibility.strip(),
        )

    def _extract_open_questions(
        self,
        agent_name: str,
        text: str,
    ) -> list[OpenQuestion]:
        sections = self._parse_sections(text)
        questions = self._questions_from_section(
            agent_name,
            sections.get("open_questions", []),
        )
        if questions:
            return questions

        if "BLOCKED_BY_QUESTION" not in text.upper():
            return []
        fallback_questions = []
        for idx, line in enumerate(text.splitlines(), start=1):
            match = self.QUESTION_PATTERN.match(line)
            if match:
                fallback_questions.append(
                    OpenQuestion(
                        id=f"q-{agent_name}-{idx:03d}",
                        question=match.group(1).strip(),
                        raised_by=[agent_name],
                    )
                )
        return fallback_questions

    def _questions_from_section(
        self,
        agent_name: str,
        lines: list[str],
    ) -> list[OpenQuestion]:
        questions: list[OpenQuestion] = []
        current: dict[str, str] = {}

        def flush() -> None:
            if not current.get("question"):
                return
            idx = len(questions) + 1
            questions.append(
                OpenQuestion(
                    id=f"q-{agent_name}-{idx:03d}",
                    question=current["question"].strip(),
                    options=self._split_options(current.get("options", "")),
                    recommended_option=(
                        current.get("recommended_option", "").strip() or None
                    ),
                    blocking=True,
                    raised_by=[agent_name],
                    rationale=current.get("rationale", "").strip(),
                )
            )
            current.clear()

        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            question_match = self.QUESTION_FIELD_PATTERN.match(stripped)
            if question_match:
                flush()
                current["question"] = question_match.group(1).strip()
                continue
            plain_question = self.QUESTION_PATTERN.match(stripped)
            if plain_question and "question" not in current:
                flush()
                current["question"] = plain_question.group(1).strip()
                continue
            options_match = self.OPTIONS_PATTERN.match(stripped)
            if options_match:
                current["options"] = options_match.group(1).strip()
                continue
            recommended_match = self.RECOMMENDED_PATTERN.match(stripped)
            if recommended_match:
                current["recommended_option"] = recommended_match.group(1).strip()
                continue
            rationale_match = self.RATIONALE_PATTERN.match(stripped)
            if rationale_match:
                current["rationale"] = rationale_match.group(1).strip()
                continue
            if stripped.endswith("?"):
                flush()
                current["question"] = self._clean_list_item(stripped)
        flush()
        return questions

    def _extract_blockers(self, text: str) -> list[str]:
        sections = self._parse_sections(text)
        blockers = self._clean_list(sections.get("blockers", []))
        if blockers:
            return blockers
        if "REJECT" not in text.upper():
            return []
        for line in text.splitlines():
            if re.search(r"\b(reason|because|blocker)\b", line, re.IGNORECASE):
                cleaned = self._clean_list_item(line)
                if cleaned:
                    return [cleaned]
        return []

    @staticmethod
    def _extract_rationale(text: str, blockers: list[str]) -> str:
        if blockers:
            return blockers[0]
        for line in text.splitlines():
            if re.match(r"^\s*(?:[-*]\s*)?rationale\s*:", line, re.IGNORECASE):
                return line.split(":", 1)[1].strip()
        return ""

    def _extract_json_payload(self, text: str) -> dict[str, Any] | None:
        candidates = []
        fenced = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        candidates.extend(fenced)
        object_match = re.search(r"(\{.*\})", text, re.DOTALL)
        if object_match:
            candidates.append(object_match.group(1))

        for candidate in candidates:
            try:
                parsed = json.loads(candidate)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                return parsed
        return None

    def _vote_from_json(
        self,
        agent_name: str,
        payload: dict[str, Any],
        raw_text: str,
    ) -> StructuredVote:
        vote_raw = str(payload.get("vote", "")).upper()
        blueprint_data = payload.get("blueprint") or payload.get("final_blueprint")
        blueprint = (
            Blueprint.from_dict(blueprint_data)
            if isinstance(blueprint_data, dict)
            else self._extract_blueprint(raw_text)
        )
        open_questions_data = payload.get("open_questions", [])
        open_questions = [
            OpenQuestion.from_dict(item)
            for item in open_questions_data
            if isinstance(item, dict)
        ]
        blockers = [str(item) for item in payload.get("blockers", [])]
        vote_type = self._vote_type_from_raw(vote_raw)
        if vote_type is None:
            vote_type = self._extract_vote_type(
                raw_text,
                blueprint,
                open_questions,
                blockers,
            )
        return StructuredVote(
            agent_name=agent_name,
            vote=vote_type,
            rationale=str(payload.get("rationale", "")),
            blueprint=blueprint if blueprint and blueprint.is_valid else None,
            open_questions=open_questions,
            blockers=blockers,
        )

    @staticmethod
    def _vote_type_from_raw(raw: str) -> VoteType | None:
        normalized = raw.strip().upper()
        if normalized == "APPROVE":
            return VoteType.APPROVE
        if normalized == "APPROVE_WITH_CHANGES":
            return VoteType.APPROVE_WITH_CHANGES
        if normalized == "BLOCKED_BY_QUESTION":
            return VoteType.BLOCKED_BY_QUESTION
        if normalized == "REJECT":
            return VoteType.REJECT
        return None

    def _build_summary(
        self,
        reached: bool,
        votes: dict[str, StructuredVote],
        final_blueprint: Blueprint | None,
        open_questions: list[OpenQuestion],
        blockers: list[str],
    ) -> str:
        if open_questions:
            first = open_questions[0].question
            return f"User decision required before final blueprint: {first}"
        if reached and final_blueprint:
            return (
                f"Structured consensus reached on blueprint "
                f"'{final_blueprint.title}' ({self._approval_count(votes)}/"
                f"{len(votes)} approve). {final_blueprint.summary}"
            )
        if blockers:
            return f"Structured consensus blocked: {blockers[0]}"
        if votes:
            return (
                f"Structured consensus not reached "
                f"({self._approval_count(votes)}/{len(votes)} approve)."
            )
        return "No structured consensus: no usable agent opinions."

    @staticmethod
    def _approval_count(votes: dict[str, StructuredVote]) -> int:
        return sum(
            1
            for vote in votes.values()
            if vote.vote in {VoteType.APPROVE, VoteType.APPROVE_WITH_CHANGES}
        )

    @staticmethod
    def _dedupe_questions(questions: Any) -> list[OpenQuestion]:
        deduped: list[OpenQuestion] = []
        seen: set[str] = set()
        for question in questions:
            normalized = re.sub(r"\s+", " ", question.question.strip().lower())
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            deduped.append(question)
        return deduped

    @staticmethod
    def _clean_list(lines: list[str]) -> list[str]:
        return [
            item
            for item in (StructuredConsensusSynthesizer._clean_list_item(line)
                         for line in lines)
            if item
        ]

    @staticmethod
    def _clean_list_item(line: str) -> str:
        item = line.strip()
        item = re.sub(r"^\s*[-*]\s*", "", item)
        item = re.sub(r"^\s*\d+[.)]\s*", "", item)
        return item.strip()

    @staticmethod
    def _split_options(raw: str) -> list[str]:
        if not raw.strip():
            return []
        parts = re.split(r"\s*(?:\||,|/)\s*", raw.strip())
        return [part.strip() for part in parts if part.strip()]

    @staticmethod
    def _first_paragraph(text: str) -> str:
        ignored_prefixes = ("vote:", "blueprint:", "open questions:", "blockers:")
        for paragraph in re.split(r"\n\s*\n", text.strip()):
            clean = " ".join(
                line.strip()
                for line in paragraph.splitlines()
                if line.strip()
                and not line.strip().lower().startswith(ignored_prefixes)
            ).strip()
            if clean:
                return clean[:500]
        return ""
