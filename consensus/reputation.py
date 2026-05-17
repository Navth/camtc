"""V-Score Reputation Model for validator scoring."""
from dataclasses import dataclass, field
from typing import Dict


@dataclass
class ValidatorReputation:
    """Tracks per-validator reputation, uptime, and latency."""
    rep: float = 1.0       # proposal correctness
    up: float = 1.0        # uptime fraction
    lat: float = 1.0       # inverse-normalised latency score
    _correct_proposals: int = 0
    _invalid_proposals: int = 0
    _heartbeat_responses: int = 0
    _heartbeat_total: int = 0
    _total_latency_ms: float = 0.0
    _latency_count: int = 0

    @property
    def vscore(self) -> float:
        """Compute V-Score: VS(v) = 0.50*Rep + 0.30*Up + 0.20*Lat"""
        return 0.50 * self.rep + 0.30 * self.up + 0.20 * self.lat

    def record_correct_proposal(self):
        self._correct_proposals += 1
        self.rep = min(1.0, self.rep + 0.02)

    def record_invalid_proposal(self):
        self._invalid_proposals += 1
        self.rep = max(0.0, self.rep - 0.10)

    def record_heartbeat(self, responded: bool):
        self._heartbeat_total += 1
        if responded:
            self._heartbeat_responses += 1
        if self._heartbeat_total > 0:
            self.up = self._heartbeat_responses / self._heartbeat_total
        if not responded and self._heartbeat_total > 100:
            self.up = max(0.0, self.up - 0.05)

    def record_latency(self, latency_ms: float):
        self._latency_count += 1
        self._total_latency_ms += latency_ms
        avg = self._total_latency_ms / self._latency_count
        self.lat = max(0.0, min(1.0, 1.0 - (avg / 1000.0)))

    def is_tier1_eligible(self) -> bool:
        return self.vscore >= 0.30

    def is_quarantined(self) -> bool:
        return self.vscore < 0.15


class ReputationManager:
    """Manages V-Score for all validators."""

    def __init__(self, n_validators: int):
        self.scores: Dict[int, ValidatorReputation] = {
            i: ValidatorReputation() for i in range(n_validators)
        }

    def get_vscore(self, validator_id: int) -> float:
        return self.scores[validator_id].vscore

    def get_eligible_tier1(self) -> list[int]:
        return [vid for vid, rep in self.scores.items() if rep.is_tier1_eligible()]

    def get_active(self) -> list[int]:
        return [vid for vid, rep in self.scores.items() if not rep.is_quarantined()]

    def update(self, validator_id: int, event: str, **kwargs):
        rep = self.scores.get(validator_id)
        if rep is None:
            return
        if event == "correct_proposal":
            rep.record_correct_proposal()
        elif event == "invalid_proposal":
            rep.record_invalid_proposal()
        elif event == "heartbeat":
            rep.record_heartbeat(kwargs.get("responded", True))
        elif event == "latency":
            rep.record_latency(kwargs.get("latency_ms", 0.0))
        elif event == "silence":
            rep.up = max(0.0, rep.up - 0.05)

    def to_dict(self) -> dict:
        return {
            vid: {
                "vscore": round(rep.vscore, 4),
                "rep": round(rep.rep, 4),
                "up": round(rep.up, 4),
                "lat": round(rep.lat, 4),
                "tier1_eligible": rep.is_tier1_eligible(),
                "quarantined": rep.is_quarantined(),
            }
            for vid, rep in self.scores.items()
        }
