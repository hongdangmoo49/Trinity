"""Transaction tracker for bridge operations."""

import asyncio
import random
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Optional


class TransactionStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class TransactionUpdate:
    tx_hash: str
    status: TransactionStatus
    message: str


class BridgeTracker:
    """Tracks bridge transaction status and provides notifications."""

    def __init__(self):
        self.active_tracks = {}

    async def track(
        self, 
        tx_hash: str, 
        callback: Optional[Callable[[TransactionUpdate], None]] = None
    ) -> TransactionUpdate:
        """
        Simulate tracking a transaction until it completes or fails.
        In a real app, this would poll a bridge API or on-chain events.
        """
        # Simulate tracking for 2 to 5 seconds
        duration = random.uniform(2.0, 5.0)
        
        # Initial status
        update = TransactionUpdate(tx_hash, TransactionStatus.PENDING, "Transaction initiated. Waiting for source confirmation...")
        if callback:
            callback(update)
            
        await asyncio.sleep(duration / 2)
        
        # Intermediate status
        update = TransactionUpdate(tx_hash, TransactionStatus.PENDING, "Source confirmed. Funds in transit...")
        if callback:
            callback(update)
            
        await asyncio.sleep(duration / 2)
        
        # Final status
        # 95% success rate simulation
        if random.random() < 0.95:
            final_status = TransactionStatus.COMPLETED
            msg = "Transaction completed successfully! Funds arrived at target chain."
        else:
            final_status = TransactionStatus.FAILED
            msg = "Transaction failed due to bridge error. Please contact support."
            
        final_update = TransactionUpdate(tx_hash, final_status, msg)
        if callback:
            callback(final_update)
            
        return final_update
