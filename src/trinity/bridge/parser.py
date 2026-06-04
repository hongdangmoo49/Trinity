"""Parser for bridge commands."""

import re

from trinity.bridge.models import (
    BridgeRequest,
    ChainId,
    ParseResult,
    PreferenceMode,
    TokenAmount,
)


class BridgeCommandParser:
    """Parses bridge commands like 'bridge 1 ETH from ethereum to base --speed'."""

    # Simple regex for parsing: bridge <amount> <symbol> from <source> to <target> [--mode]
    BRIDGE_PATTERN = re.compile(
        r"bridge\s+(?P<amount>[\d\.]+)\s+(?P<symbol>\w+)\s+from\s+(?P<source>\w+)\s+to\s+(?P<target>\w+)(?:\s+--(?P<mode>\w+))?",
        re.IGNORECASE
    )

    def parse(self, command: str) -> ParseResult:
        match = self.BRIDGE_PATTERN.search(command)
        if not match:
            return ParseResult(error="Invalid bridge command format. Use: bridge <amount> <symbol> from <source> to <target> [--speed|--cost|--balanced]")

        data = match.groupdict()
        try:
            amount_val = float(data["amount"])
            symbol = data["symbol"].upper()
            source = ChainId(data["source"].lower())
            target = ChainId(data["target"].lower())
            
            mode_str = data.get("mode") or "balanced"
            mode = PreferenceMode(mode_str.lower())
        except ValueError as e:
            return ParseResult(error=f"Error parsing command components: {e}")
        except Exception as e:
            return ParseResult(error=f"Unknown parsing error: {e}")

        # Assume 1 ETH = $3000 for simplicity in the parser/demo
        amount_usd = amount_val * 3000.0 if symbol == "ETH" else amount_val

        request = BridgeRequest(
            source_chain=source,
            target_chain=target,
            amount=TokenAmount(amount=amount_val, symbol=symbol, amount_usd=amount_usd),
            mode=mode
        )

        return ParseResult(request=request, is_valid=True)
