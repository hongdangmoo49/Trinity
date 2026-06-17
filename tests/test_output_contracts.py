"""Tests for centralized provider output contracts."""

import pytest

from trinity.prompts.contracts import (
    DELIBERATION_CONTRACT_ID,
    EXECUTION_CONTRACT_ID,
    FINAL_REVIEW_CONTRACT_ID,
    REVIEW_CONTRACT_ID,
    get_output_contract,
    render_output_contract,
)


def test_execution_contract_preserves_parser_sections():
    rendered = render_output_contract(EXECUTION_CONTRACT_ID)

    assert "OUTPUT CONTRACT: execution_v1" in rendered
    assert "## Completed" in rendered
    assert "## Files Changed" in rendered
    assert "## Subtasks" in rendered


def test_review_contract_preserves_status_fields():
    rendered = render_output_contract(REVIEW_CONTRACT_ID)
    contract = get_output_contract(REVIEW_CONTRACT_ID)

    assert contract.status_field == "REVIEW STATUS"
    assert "CHANGES_REQUESTED" in contract.allowed_statuses
    assert "REVIEW STATUS: APPROVED | CHANGES_REQUESTED | BLOCKED" in rendered
    assert "REQUIRED CHANGES:" in rendered


def test_final_review_contract_uses_final_status_field():
    rendered = render_output_contract(FINAL_REVIEW_CONTRACT_ID)
    contract = get_output_contract(FINAL_REVIEW_CONTRACT_ID)

    assert contract.status_field == "FINAL REVIEW STATUS"
    assert "FINAL REVIEW STATUS: APPROVED | CHANGES_REQUESTED | BLOCKED" in rendered
    assert "PROJECT OVERVIEW:" in rendered


def test_deliberation_contract_renders_korean_phase():
    rendered = render_output_contract(
        DELIBERATION_CONTRACT_ID,
        lang="ko",
        phase="제안",
    )

    assert "반드시 한국어" in rendered
    assert "구조화된 토론 계약" in rendered
    assert "- 단계: 제안." in rendered
    assert "VOTE: APPROVE" in rendered


def test_unknown_contract_raises():
    with pytest.raises(ValueError, match="Unknown output contract"):
        get_output_contract("missing")

