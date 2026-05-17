"""Transaction model for CAMTC."""
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from ..crypto.merkle import sha256


class Domain(str, Enum):
    HEALTHCARE = "healthcare"
    FINANCE = "finance"
    IOT = "iot"


@dataclass
class TransactionMeta:
    domain: Domain
    semantic_type: str          # e.g. "cardiac-alert", "audit-log"
    urgency: float              # u in [0,1]
    economic_value: float       # v in [0,1]
    submitter_reputation: float # r in [0,1]
    latency_sensitivity: float  # l in [0,1]
    regulatory_class: float     # K in [0,1]

    @property
    def criticality(self) -> float:
        lookup = {
            "cardiac-alert": 0.95, "fire-alarm": 0.93, "hft-order": 0.90,
            "medication-order": 0.70, "vitals-log": 0.40,
            "payment": 0.50, "sensor-read": 0.30,
            "audit-log": 0.20, "monthly-audit": 0.15,
        }
        return lookup.get(self.semantic_type, 0.30)

    @property
    def time_sensitivity(self) -> float:
        return max(self.urgency, self.latency_sensitivity)

    @property
    def resource_availability(self) -> float:
        return 0.5  # default; updated at routing time

    def to_feature_vector(self) -> list[float]:
        """Return the 6-element feature vector for PriorityNet."""
        return [
            self.criticality,
            self.urgency,
            self.economic_value,
            self.submitter_reputation,
            self.latency_sensitivity,
            self.regulatory_class,
        ]


@dataclass
class Transaction:
    tx_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    meta: TransactionMeta = None
    payload: bytes = b""
    sender_vk: bytes = b""
    signature: bytes = b""
    priority_score: float = 0.0
    tier: int = 0                # 1, 2, or 3
    timestamp: float = field(default_factory=time.time)
    committed_at: Optional[float] = None

    def hash(self) -> bytes:
        data = (
            self.tx_id.encode()
            + f"{self.priority_score:.6f}".encode()
            + f"{self.tier}".encode()
            + f"{self.timestamp:.6f}".encode()
            + self.sender_vk
        )
        return sha256(data)

    def serialization_bytes(self) -> bytes:
        return (
            self.tx_id.encode()
            + self.payload
            + self.sender_vk
            + f"{self.timestamp:.6f}".encode()
        )

    @property
    def latency_ms(self) -> float:
        if self.committed_at is None:
            return -1.0
        return (self.committed_at - self.timestamp) * 1000

    def to_dict(self) -> dict:
        return {
            "tx_id": self.tx_id,
            "domain": self.meta.domain.value if self.meta else None,
            "semantic_type": self.meta.semantic_type if self.meta else None,
            "priority_score": round(self.priority_score, 4),
            "tier": self.tier,
            "timestamp": self.timestamp,
            "committed_at": self.committed_at,
            "latency_ms": round(self.latency_ms, 1) if self.latency_ms > 0 else None,
        }
