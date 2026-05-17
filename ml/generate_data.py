"""Synthetic training data generator for PriorityNet."""
import random
import numpy as np
from typing import List, Tuple

from ..core.transaction import TransactionMeta, Domain


TRANSACTION_PROFILES = {
    # healthcare (40%)
    "cardiac-alert":   {"domain": Domain.HEALTHCARE, "criticality": 0.95, "urgency": (0.85, 1.0), "value": (0.1, 0.3), "reputation": (0.5, 1.0), "latency": (0.9, 1.0), "regulatory": (0.8, 1.0)},
    "medication-order": {"domain": Domain.HEALTHCARE, "criticality": 0.70, "urgency": (0.5, 0.8), "value": (0.2, 0.5), "reputation": (0.4, 0.9), "latency": (0.5, 0.8), "regulatory": (0.6, 0.9)},
    "vitals-log":      {"domain": Domain.HEALTHCARE, "criticality": 0.40, "urgency": (0.1, 0.4), "value": (0.0, 0.1), "reputation": (0.3, 0.8), "latency": (0.2, 0.5), "regulatory": (0.4, 0.7)},
    "monthly-audit":   {"domain": Domain.HEALTHCARE, "criticality": 0.20, "urgency": (0.0, 0.15), "value": (0.0, 0.05), "reputation": (0.2, 0.7), "latency": (0.0, 0.2), "regulatory": (0.5, 0.9)},

    # finance (30%)
    "hft-order":       {"domain": Domain.FINANCE, "criticality": 0.90, "urgency": (0.8, 1.0), "value": (0.7, 1.0), "reputation": (0.5, 1.0), "latency": (0.9, 1.0), "regulatory": (0.3, 0.6)},
    "payment":         {"domain": Domain.FINANCE, "criticality": 0.50, "urgency": (0.3, 0.6), "value": (0.3, 0.7), "reputation": (0.3, 0.8), "latency": (0.3, 0.6), "regulatory": (0.4, 0.7)},
    "settlement":      {"domain": Domain.FINANCE, "criticality": 0.35, "urgency": (0.1, 0.4), "value": (0.2, 0.5), "reputation": (0.3, 0.8), "latency": (0.1, 0.4), "regulatory": (0.5, 0.8)},

    # IoT (30%)
    "fire-alarm":      {"domain": Domain.IOT, "criticality": 0.93, "urgency": (0.85, 1.0), "value": (0.1, 0.3), "reputation": (0.5, 1.0), "latency": (0.9, 1.0), "regulatory": (0.7, 0.9)},
    "sensor-read":     {"domain": Domain.IOT, "criticality": 0.30, "urgency": (0.1, 0.4), "value": (0.0, 0.1), "reputation": (0.3, 0.8), "latency": (0.1, 0.4), "regulatory": (0.1, 0.4)},
    "device-heartbeat": {"domain": Domain.IOT, "criticality": 0.25, "urgency": (0.05, 0.25), "value": (0.0, 0.05), "reputation": (0.3, 0.7), "latency": (0.05, 0.25), "regulatory": (0.1, 0.3)},
}

DOMAIN_WEIGHTS = {Domain.HEALTHCARE: 0.40, Domain.FINANCE: 0.30, Domain.IOT: 0.30}


def _sample_range(r: tuple, rng: random.Random) -> float:
    return r[0] + (r[1] - r[0]) * rng.random()


def compute_ground_truth_score(meta: TransactionMeta) -> float:
    """Domain-expert ground truth priority score."""
    C = meta.criticality
    S = max(meta.urgency, meta.latency_sensitivity)
    R = 0.5  # resource placeholder
    K = meta.regulatory_class

    if C > 0.85:
        alpha, beta, gamma, delta = 0.40, 0.30, 0.10, 0.20
    elif C > 0.50:
        alpha, beta, gamma, delta = 0.30, 0.35, 0.15, 0.20
    else:
        alpha, beta, gamma, delta = 0.20, 0.30, 0.20, 0.30

    return min(1.0, max(0.0, alpha * C + beta * S + gamma * R + delta * K))


def generate_dataset(n: int = 100_000, seed: int = 42) -> Tuple[np.ndarray, np.ndarray, List[str]]:
    """Generate (features, labels, semantic_types) for PriorityNet training.

    features: (n, 6) float array
    labels: (n,) float array of priority scores in [0,1]
    """
    rng = random.Random(seed)
    np_rng = np.random.default_rng(seed)

    types_by_domain: dict[Domain, list[str]] = {}
    for t, p in TRANSACTION_PROFILES.items():
        d = p["domain"]
        types_by_domain.setdefault(d, []).append(t)

    domain_list = list(DOMAIN_WEIGHTS.keys())
    domain_weights_list = [DOMAIN_WEIGHTS[d] for d in domain_list]

    features = np.zeros((n, 6), dtype=np.float32)
    labels = np.zeros(n, dtype=np.float32)
    sem_types = []

    for i in range(n):
        domain = rng.choices(domain_list, weights=domain_weights_list, k=1)[0]
        sem_type = rng.choice(types_by_domain[domain])
        profile = TRANSACTION_PROFILES[sem_type]

        meta = TransactionMeta(
            domain=domain,
            semantic_type=sem_type,
            urgency=_sample_range(profile["urgency"], rng),
            economic_value=_sample_range(profile["value"], rng),
            submitter_reputation=_sample_range(profile["reputation"], rng),
            latency_sensitivity=_sample_range(profile["latency"], rng),
            regulatory_class=_sample_range(profile["regulatory"], rng),
        )

        features[i] = meta.to_feature_vector()
        labels[i] = compute_ground_truth_score(meta) + np_rng.normal(0, 0.02)
        labels[i] = np.clip(labels[i], 0.0, 1.0)
        sem_types.append(sem_type)

    return features, labels, sem_types


def generate_single(
    semantic_type: str | None = None,
    domain: Domain | None = None,
    seed: int | None = None,
) -> Tuple[TransactionMeta, float]:
    """Generate a single labelled transaction."""
    rng = random.Random(seed)
    if semantic_type is None:
        semantic_type = rng.choice(list(TRANSACTION_PROFILES.keys()))
    profile = TRANSACTION_PROFILES[semantic_type]
    d = domain or profile["domain"]

    meta = TransactionMeta(
        domain=d,
        semantic_type=semantic_type,
        urgency=_sample_range(profile["urgency"], rng),
        economic_value=_sample_range(profile["value"], rng),
        submitter_reputation=_sample_range(profile["reputation"], rng),
        latency_sensitivity=_sample_range(profile["latency"], rng),
        regulatory_class=_sample_range(profile["regulatory"], rng),
    )
    score = compute_ground_truth_score(meta)
    return meta, score
