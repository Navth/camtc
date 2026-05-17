"""PPO Reinforcement Learning agent for adaptive tier routing thresholds."""
import numpy as np
from typing import Tuple, Optional

try:
    import gymnasium as gym
    from gymnasium import spaces
    HAS_GYM = True
except ImportError:
    HAS_GYM = False

try:
    from stable_baselines3 import PPO
    HAS_SB3 = True
except ImportError:
    HAS_SB3 = False


if HAS_GYM:
    class CAMTCRoutingEnv(gym.Env):
        """Custom Gymnasium environment for CAMTC tier routing.

        State: normalised queue depths (|Q1|/max1, |Q2|/max2, |Q3|/max3)
        Action: (delta_theta1, delta_theta2) in [-0.05, +0.05]
        Reward: -w_L * 1[L1 > 500ms] - w_O * 1[|Q3| > cap]
        """
        metadata = {"render_modes": []}

        def __init__(
            self,
            tier1_cap: int = 5, tier2_cap: int = 20, tier3_cap: int = 50,
            w_L: float = 2.0, w_O: float = 1.0,
            target_latency_ms: float = 500.0,
        ):
            super().__init__()
            self.tier_caps = [tier1_cap, tier2_cap, tier3_cap]
            self.w_L = w_L
            self.w_O = w_O
            self.target_latency_ms = target_latency_ms

            self.observation_space = spaces.Box(
                low=0.0, high=1.0, shape=(3,), dtype=np.float32
            )
            self.action_space = spaces.Box(
                low=-0.05, high=0.05, shape=(2,), dtype=np.float32
            )

            self.theta1 = 0.85
            self.theta2 = 0.60
            self.queue_depths = np.zeros(3, dtype=np.float32)
            self._step_count = 0

        def set_state(self, queue_depths: Tuple[int, int, int], tier1_latency_ms: float = 0.0):
            """Set the environment state from live metrics."""
            for i in range(3):
                self.queue_depths[i] = min(queue_depths[i] / max(self.tier_caps[i], 1), 1.0)
            self._tier1_latency = tier1_latency_ms

        def reset(self, seed=None, options=None):
            super().reset(seed=seed)
            self.theta1 = 0.85
            self.theta2 = 0.60
            self.queue_depths = np.zeros(3, dtype=np.float32)
            self._tier1_latency = 0.0
            self._step_count = 0
            return self.queue_depths.copy(), {}

        def step(self, action):
            d1 = np.clip(action[0], -0.05, 0.05)
            d2 = np.clip(action[1], -0.05, 0.05)

            self.theta1 = np.clip(self.theta1 + d1, 0.50, 0.95)
            self.theta2 = np.clip(self.theta2 + d2, 0.30, 0.80)
            if self.theta1 <= self.theta2 + 0.10:
                self.theta1 = self.theta2 + 0.10

            latency_penalty = self.w_L if self._tier1_latency > self.target_latency_ms else 0.0
            overflow_penalty = self.w_O if self.queue_depths[2] >= 1.0 else 0.0

            reward = -(latency_penalty + overflow_penalty)

            self._step_count += 1
            terminated = False
            truncated = self._step_count >= 512

            return self.queue_depths.copy(), reward, terminated, truncated, {
                "theta1": float(self.theta1),
                "theta2": float(self.theta2),
            }


class RLAgent:
    """Wrapper around the PPO agent for threshold adaptation."""

    def __init__(self, env=None, model_path: Optional[str] = None):
        self.env = env
        self.model = None
        self.theta1 = 0.85
        self.theta2 = 0.60

        if HAS_SB3 and HAS_GYM:
            if env is None:
                env = CAMTCRoutingEnv()
            self.env = env
            if model_path:
                self.model = PPO.load(model_path, env=self.env)

    def train(self, total_timesteps: int = 5000):
        if not HAS_SB3 or not HAS_GYM:
            return
        if self.env is None:
            self.env = CAMTCRoutingEnv()
        self.model = PPO("MlpPolicy", self.env, verbose=0, seed=42)
        self.model.learn(total_timesteps=total_timesteps)

    def adapt(self, queue_depths: Tuple[int, int, int], tier1_latency_ms: float = 0.0) -> Tuple[float, float]:
        """Get adapted thresholds based on current network state."""
        if self.model is not None and HAS_SB3:
            obs = np.array([
                min(queue_depths[0] / 5, 1.0),
                min(queue_depths[1] / 20, 1.0),
                min(queue_depths[2] / 50, 1.0),
            ], dtype=np.float32)
            action, _ = self.model.predict(obs, deterministic=True)
            self.theta1 = np.clip(self.theta1 + action[0], 0.50, 0.95)
            self.theta2 = np.clip(self.theta2 + action[1], 0.30, 0.80)
            if self.theta1 <= self.theta2 + 0.10:
                self.theta1 = self.theta2 + 0.10
        return self.theta1, self.theta2

    def save(self, path: str):
        if self.model:
            self.model.save(path)

    def get_thresholds(self) -> Tuple[float, float]:
        return self.theta1, self.theta2
