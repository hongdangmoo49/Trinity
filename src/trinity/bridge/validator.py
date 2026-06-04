"""Validator for bridge inputs."""

from typing import List

from trinity.bridge.chains import ChainRegistry
from trinity.bridge.models import (
    BridgeRequest,
    ValidationError,
    ValidationErrorCode,
)


class BridgeInputValidator:
    """Validates bridge requests."""

    def validate(self, request: BridgeRequest) -> List[ValidationError]:
        errors = []

        if not ChainRegistry.is_supported(request.source_chain):
            errors.append(ValidationError(
                code=ValidationErrorCode.INVALID_CHAIN,
                message=f"Source chain {request.source_chain} is not supported."
            ))

        if not ChainRegistry.is_supported(request.target_chain):
            errors.append(ValidationError(
                code=ValidationErrorCode.INVALID_CHAIN,
                message=f"Target chain {request.target_chain} is not supported."
            ))

        if request.source_chain == request.target_chain:
            errors.append(ValidationError(
                code=ValidationErrorCode.SAME_CHAIN,
                message="Source and target chains must be different."
            ))

        if request.amount.amount <= 0:
            errors.append(ValidationError(
                code=ValidationErrorCode.INVALID_AMOUNT,
                message="Amount must be greater than zero."
            ))

        return errors
