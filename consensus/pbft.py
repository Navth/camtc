"""Adaptive PBFT Consensus Engine for CAMTC.

Per-tier PBFT instances with:
- Three phases: Pre-Prepare -> Prepare -> Commit
- Fast path (unanimous Prepare skips Commit)
- Quorum fallback for Tier-1
"""
import asyncio
import time
import random
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, List, Optional, Callable, Set

from ..core.block import Block
from ..core.transaction import Transaction


class Phase(Enum):
    IDLE = auto()
    PRE_PREPARE = auto()
    PREPARE = auto()
    COMMIT = auto()
    COMMITTED = auto()
    VIEW_CHANGE = auto()


@dataclass
class ConsensusMessage:
    msg_type: str            # "pre-prepare", "prepare", "commit", "fallback-notice"
    epoch: int
    tier: int
    sender_id: int
    block_hash: bytes = b""
    block: Optional[Block] = None
    signature: bytes = b""
    timestamp: float = field(default_factory=time.time)


@dataclass
class QuorumFallbackState:
    active: bool = False
    active_validators: int = 0
    normal_quorum: float = 0.90
    fallback_quorum: float = 0.67
    recovery_count: int = 0


class PBFTEngine:
    """Single-tier PBFT engine instance."""

    def __init__(
        self,
        tier: int,
        committee: List[int],
        quorum_fraction: float,
        max_batch: int,
        timeout_ms: int,
        fallback_quorum: float = 0.67,
        enable_fast_path: bool = True,
    ):
        self.tier = tier
        self.committee = list(committee)
        self.committee_size = len(committee)
        self.quorum_fraction = quorum_fraction
        self.fallback_quorum = fallback_quorum
        self.current_quorum = quorum_fraction
        self.max_batch = max_batch
        self.timeout_ms = timeout_ms
        self.enable_fast_path = enable_fast_path

        self.epoch = 0
        self.phase = Phase.IDLE
        self.current_block: Optional[Block] = None

        self.prepare_votes: Dict[bytes, Set[int]] = {}
        self.commit_votes: Dict[bytes, Set[int]] = {}

        self.fallback = QuorumFallbackState(
            normal_quorum=quorum_fraction,
            fallback_quorum=fallback_quorum,
        )

        self._on_commit_callback: Optional[Callable] = None
        self._message_callback: Optional[Callable] = None
        self.committed_blocks: List[Block] = []

    def set_callbacks(
        self,
        on_commit: Optional[Callable] = None,
        on_message: Optional[Callable] = None,
    ):
        self._on_commit_callback = on_commit
        self._message_callback = on_message

    @property
    def quorum_size(self) -> int:
        return int(self.current_quorum * self.committee_size)

    def check_fallback(self, active_count: int) -> bool:
        needed = int(self.fallback.normal_quorum * self.committee_size)
        if active_count < needed:
            self.fallback.active = True
            self.fallback.active_validators = active_count
            self.current_quorum = self.fallback.fallback_quorum
            return True
        return False

    def recover_from_fallback(self, active_count: int, required_intervals: int = 3) -> bool:
        needed = int(self.fallback.normal_quorum * self.committee_size)
        if active_count >= needed:
            self.fallback.recovery_count += 1
            if self.fallback.recovery_count >= required_intervals:
                self.fallback.active = False
                self.fallback.recovery_count = 0
                self.current_quorum = self.fallback.normal_quorum
                return True
        else:
            self.fallback.recovery_count = 0
        return False

    def start_proposal(self, block: Block, leader_id: int) -> ConsensusMessage:
        self.epoch += 1
        self.phase = Phase.PRE_PREPARE
        self.current_block = block
        block_hash = block.hash()
        self.prepare_votes[block_hash] = {leader_id}
        self.commit_votes[block_hash] = {leader_id}
        return ConsensusMessage(
            msg_type="pre-prepare",
            epoch=self.epoch,
            tier=self.tier,
            sender_id=leader_id,
            block_hash=block_hash,
            block=block,
        )

    def receive_prepare(self, msg: ConsensusMessage) -> Optional[ConsensusMessage]:
        if msg.epoch != self.epoch:
            return None
        bh = msg.block_hash
        if bh not in self.prepare_votes:
            self.prepare_votes[bh] = set()
        self.prepare_votes[bh].add(msg.sender_id)

        n_votes = len(self.prepare_votes[bh])

        # Fast path: unanimous Prepare -> skip Commit
        if self.enable_fast_path and n_votes == self._count_active():
            self.phase = Phase.COMMITTED
            self._finalize(msg.block if msg.block else self.current_block)
            return None

        # Normal quorum check
        if n_votes >= self.quorum_size and self.phase != Phase.COMMIT:
            self.phase = Phase.COMMIT
            return ConsensusMessage(
                msg_type="commit",
                epoch=self.epoch,
                tier=self.tier,
                sender_id=msg.sender_id,
                block_hash=bh,
            )
        return None

    def receive_commit(self, msg: ConsensusMessage) -> bool:
        if msg.epoch != self.epoch:
            return False
        bh = msg.block_hash
        if bh not in self.commit_votes:
            self.commit_votes[bh] = set()
        self.commit_votes[bh].add(msg.sender_id)

        if len(self.commit_votes[bh]) >= self.quorum_size:
            self.phase = Phase.COMMITTED
            self._finalize(self.current_block)
            return True
        return False

    def _count_active(self) -> int:
        if self.fallback.active:
            return self.fallback.active_validators
        return self.committee_size

    def _finalize(self, block: Optional[Block]):
        if block is None:
            return
        self.committed_blocks.append(block)
        if self._on_commit_callback:
            self._on_commit_callback(block, self.tier)
        self.phase = Phase.IDLE
        self.current_block = None

    def to_dict(self) -> dict:
        return {
            "tier": self.tier,
            "epoch": self.epoch,
            "phase": self.phase.name,
            "committee_size": self.committee_size,
            "quorum": f"{self.current_quorum:.0%}",
            "fallback_active": self.fallback.active,
            "blocks_committed": len(self.committed_blocks),
        }


class TieredConsensus:
    """Manages three PBFT engines (one per tier)."""

    def __init__(
        self,
        tier1_committee: List[int],
        tier2_committee: List[int],
        tier3_committee: List[int],
        tier1_quorum: float = 0.90,
        tier2_quorum: float = 0.67,
        tier3_quorum: float = 0.67,
        tier1_batch: int = 5,
        tier2_batch: int = 20,
        tier3_batch: int = 50,
        tier1_timeout_ms: int = 500,
        tier2_timeout_ms: int = 2000,
        tier3_timeout_ms: int = 10000,
    ):
        self.engines: Dict[int, PBFTEngine] = {
            1: PBFTEngine(1, tier1_committee, tier1_quorum, tier1_batch, tier1_timeout_ms,
                          fallback_quorum=0.67, enable_fast_path=True),
            2: PBFTEngine(2, tier2_committee, tier2_quorum, tier2_batch, tier2_timeout_ms),
            3: PBFTEngine(3, tier3_committee, tier3_quorum, tier3_batch, tier3_timeout_ms,
                          enable_fast_path=False),
        }

    def get_engine(self, tier: int) -> PBFTEngine:
        return self.engines[tier]

    def to_dict(self) -> dict:
        return {f"tier{t}": e.to_dict() for t, e in self.engines.items()}
