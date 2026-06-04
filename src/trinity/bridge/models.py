"""Data models for the L2 Bridge Path Bot."""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class PreferenceMode(str, Enum):
    """User preference mode for routing."""
    SPEED = "speed"
    COST = "cost"
    BALANCED = "balanced"


class ChainId(str, Enum):
    """Supported Layer 2 and mainnet chains."""
    ETHEREUM = "ethereum"
    ARBITRUM = "arbitrum"
    OPTIMISM = "optimism"
    BASE = "base"
    POLYGON = "polygon"
    LINEA = "linea"


@dataclass(frozen=True)
class TokenAmount:
    """Represents a token amount with its currency/symbol."""
    amount: float
    symbol: str = "ETH"
    amount_usd: float = 0.0


@dataclass(frozen=True)
class BridgeRouteQuote:
    """A quote for a specific bridge route."""
    provider: str
    source_chain: ChainId
    target_chain: ChainId
    input_amount: TokenAmount
    output_amount: TokenAmount
    fee_usd: float
    estimated_time_sec: int
    risk_score: float  # 0.0 (safe) to 1.0 (risky)
    is_active: bool = True
    available_liquidity_usd: float = float("inf")


@dataclass(frozen=True)
class BridgeRequest:
    """A request for bridge routing."""
    source_chain: ChainId
    target_chain: ChainId
    amount: TokenAmount
    mode: PreferenceMode = PreferenceMode.BALANCED
    disabled_providers: List[str] = field(default_factory=list)


class ValidationErrorCode(str, Enum):
    # Input-level errors (BridgeInputValidator)
    INVALID_CHAIN = "invalid_chain"
    INVALID_AMOUNT = "invalid_amount"
    SAME_CHAIN = "same_chain"
    UNSUPPORTED_TOKEN = "unsupported_token"
    # Preflight errors (PreflightValidator)
    INSUFFICIENT_BALANCE = "insufficient_balance"
    INSUFFICIENT_ALLOWANCE = "insufficient_allowance"
    BELOW_MIN_RECEIVED = "below_min_received"
    PROVIDER_UNSUPPORTED = "provider_unsupported"
    INSUFFICIENT_LIQUIDITY = "insufficient_liquidity"


@dataclass
class ValidationError:
    code: ValidationErrorCode
    message: str


@dataclass
class ParseResult:
    """Result of parsing a bridge command."""
    request: Optional[BridgeRequest] = None
    error: Optional[str] = None
    is_valid: bool = False


@dataclass(frozen=True)
class WalletContext:
    """Simulated wallet state for preflight validation."""
    address: str
    balance: float  # token units available
    allowance: float  # approved amount for bridge contract (ERC20 only)
    symbol: str = "ETH"


@dataclass
class PreflightCheckResult:
    """Result of preflight validation on a single quote."""
    provider: str
    passed: bool
    errors: List[ValidationError]
    warnings: List[str]
