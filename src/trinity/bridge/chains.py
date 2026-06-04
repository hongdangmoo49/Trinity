"""Chain registry for supported networks."""

from typing import Dict, Set
from trinity.bridge.models import ChainId


class ChainRegistry:
    """Registry of supported L2 and mainnet chains."""

    SUPPORTED_CHAINS: Set[ChainId] = {
        ChainId.ETHEREUM,
        ChainId.ARBITRUM,
        ChainId.OPTIMISM,
        ChainId.BASE,
        ChainId.POLYGON,
        ChainId.LINEA,
    }

    CHAIN_NAMES: Dict[ChainId, str] = {
        ChainId.ETHEREUM: "Ethereum Mainnet",
        ChainId.ARBITRUM: "Arbitrum One",
        ChainId.OPTIMISM: "OP Mainnet",
        ChainId.BASE: "Base",
        ChainId.POLYGON: "Polygon PoS",
        ChainId.LINEA: "Linea",
    }

    @classmethod
    def is_supported(cls, chain: ChainId) -> bool:
        return chain in cls.SUPPORTED_CHAINS

    @classmethod
    def get_name(cls, chain: ChainId) -> str:
        return cls.CHAIN_NAMES.get(chain, "Unknown Chain")
