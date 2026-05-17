"""VRF-Based Proposer Selection for CAMTC."""
import hashlib
from typing import Dict, List, Optional, Tuple

from ..crypto.vrf import vrf_evaluate, vrf_verify, vrf_output_to_float


class VRFLeaderElection:
    """Selects proposer per epoch using VRF weighted by stake + reputation + load."""

    def __init__(
        self,
        n_validators: int,
        stake_distribution: Optional[Dict[int, float]] = None,
        w_stake: float = 0.40,
        w_reputation: float = 0.50,
        w_load: float = 0.10,
    ):
        self.n = n_validators
        if stake_distribution is None:
            stake = 1.0 / n_validators
            self.stakes = {i: stake for i in range(n_validators)}
        else:
            total = sum(stake_distribution.values())
            self.stakes = {k: v / total for k, v in stake_distribution.items()}
        self.w_stake = w_stake
        self.w_reputation = w_reputation
        self.w_load = w_load

    def compute_threshold(self, validator_id: int, tier_load: float = 0.0) -> float:
        """Compute eligibility threshold Theta_k(v) for a validator."""
        stake_frac = self.stakes.get(validator_id, 0.0)
        threshold = (
            self.w_stake * stake_frac
            + self.w_reputation * 0.5  # placeholder; updated with real VS
            + self.w_load * (1.0 - tier_load)
        )
        return max(0.01, min(threshold, 1.0))

    def compute_threshold_with_vscore(
        self, validator_id: int, vscore: float, tier_load: float = 0.0
    ) -> float:
        stake_frac = self.stakes.get(validator_id, 0.0)
        threshold = (
            self.w_stake * stake_frac
            + self.w_reputation * vscore
            + self.w_load * (1.0 - tier_load)
        )
        return max(0.01, min(threshold, 1.0))

    def elect(
        self,
        sk_bytes_map: Dict[int, bytes],
        vk_bytes_map: Dict[int, bytes],
        prev_block_hash: bytes,
        epoch: int,
        tier: int,
        vscores: Dict[int, float],
        tier_load: float = 0.0,
    ) -> Optional[Tuple[int, bytes, bytes]]:
        """Run leader election. Returns (winner_id, vrf_output, vrf_proof) or None."""
        alpha = hashlib.sha256(
            prev_block_hash + str(epoch).encode() + str(tier).encode()
        ).digest()

        candidates = []
        for vid in sk_bytes_map:
            output, proof = vrf_evaluate(sk_bytes_map[vid], alpha)
            vrf_float = vrf_output_to_float(output)
            threshold = self.compute_threshold_with_vscore(
                vid, vscores.get(vid, 0.5), tier_load
            )

            if vrf_float < threshold:
                candidates.append((vid, output, proof, vrf_float))

        if not candidates:
            return None

        candidates.sort(key=lambda x: x[3])
        winner = candidates[0]
        return winner[0], winner[1], winner[2]
