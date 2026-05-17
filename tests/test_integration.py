"""Integration test — full simulation flow."""
import unittest

from camtc.config.settings import Settings
from camtc.simulator import CAMTCSimulator
from camtc.core.transaction import Transaction, TransactionMeta, Domain


class TestFullSimulation(unittest.TestCase):
    def setUp(self):
        self.settings = Settings(n_validators=10, seed=42)
        self.sim = CAMTCSimulator(self.settings)

    def test_submit_single_transaction(self):
        tx = Transaction(
            meta=TransactionMeta(
                domain=Domain.HEALTHCARE, semantic_type="cardiac-alert",
                urgency=0.95, economic_value=0.3, submitter_reputation=0.8,
                latency_sensitivity=0.95, regulatory_class=0.9,
            )
        )
        result = self.sim.submit_transaction(tx)
        self.assertGreater(result.priority_score, 0.8)
        self.assertIn(result.tier, [1, 2, 3])

    def test_benchmark_100_tx(self):
        self.sim.start_benchmark(n_tx=100, tps=50)
        metrics = self.sim.get_metrics()
        self.assertEqual(metrics["total_tx"], 100)
        self.assertGreater(metrics["total_blocks"], 0)

    def test_train_and_score(self):
        result = self.sim.train_priority_net(epochs=10)
        self.assertIn("mse", result)
        self.assertLess(result["mse"], 0.1)

    def test_inject_byzantine(self):
        self.sim.inject_byzantine(2)
        metrics = self.sim.get_metrics()
        self.assertIn(0, metrics["byzantine_nodes"])
        self.assertIn(1, metrics["byzantine_nodes"])

    def test_fallback(self):
        self.sim.trigger_fallback(2)
        metrics = self.sim.get_metrics()
        self.assertEqual(len(metrics["offline_nodes"]), 2)

    def test_latency_stats(self):
        self.sim.start_benchmark(n_tx=200, tps=50)
        stats = self.sim.get_latency_stats()
        # Should have some latency data
        self.assertIn("tier1_mean", stats)

    def test_reset(self):
        self.sim.start_benchmark(n_tx=50, tps=50)
        self.sim.reset()
        metrics = self.sim.get_metrics()
        self.assertEqual(metrics["total_tx"], 0)


if __name__ == "__main__":
    unittest.main()
