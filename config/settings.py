"""Global configuration for the CAMTC simulator."""
from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class TierConfig:
    committee_size: int
    quorum_fraction: float
    fallback_quorum: float
    max_batch: int
    batch_wait_ms: int
    timeout_ms: int


@dataclass
class Settings:
    n_validators: int = 10
    f_byzantine: int = 3

    tier1: TierConfig = field(default_factory=lambda: TierConfig(
        committee_size=4, quorum_fraction=0.90, fallback_quorum=0.67,
        max_batch=5, batch_wait_ms=0, timeout_ms=500,
    ))
    tier2: TierConfig = field(default_factory=lambda: TierConfig(
        committee_size=7, quorum_fraction=0.67, fallback_quorum=0.67,
        max_batch=20, batch_wait_ms=2000, timeout_ms=2000,
    ))
    tier3: TierConfig = field(default_factory=lambda: TierConfig(
        committee_size=10, quorum_fraction=0.67, fallback_quorum=0.67,
        max_batch=50, batch_wait_ms=10000, timeout_ms=10000,
    ))

    tier1_threshold: float = 0.85
    tier2_threshold: float = 0.60

    wan_delay_min_ms: int = 20
    wan_delay_max_ms: int = 200

    vrf_weights: Dict[str, float] = field(default_factory=lambda: {
        "stake": 0.40, "reputation": 0.50, "load": 0.10,
    })

    vscore_weights: Dict[str, float] = field(default_factory=lambda: {
        "rep": 0.50, "up": 0.30, "lat": 0.20,
    })

    dnn_hidden_size: int = 64
    dnn_epochs: int = 200
    dnn_lr: float = 1e-3
    dnn_train_size: int = 100_000

    rl_pretrain_steps: int = 5000

    heartbeat_interval_ms: int = 500
    fallback_recovery_intervals: int = 3

    gateway_host: str = "0.0.0.0"
    gateway_port: int = 8000
    dashboard_port: int = 8080

    anchor_enabled: bool = True
    anchor_async: bool = True

    seed: int = 42

    @property
    def tiers(self) -> List[TierConfig]:
        return [self.tier1, self.tier2, self.tier3]
