"""Unit tests for PriorityNet DNN."""
import unittest
import numpy as np

from camtc.ml.generate_data import generate_dataset, generate_single
from camtc.ml.priority_net import PriorityNet, train_priority_net


class TestDataGeneration(unittest.TestCase):
    def test_generate_dataset(self):
        features, labels, types = generate_dataset(n=1000, seed=42)
        self.assertEqual(features.shape, (1000, 6))
        self.assertEqual(labels.shape, (1000,))
        self.assertTrue(np.all(labels >= 0))
        self.assertTrue(np.all(labels <= 1))

    def test_generate_single(self):
        meta, score = generate_single("cardiac-alert")
        self.assertGreater(score, 0.8)
        self.assertEqual(len(meta.to_feature_vector()), 6)


class TestPriorityNet(unittest.TestCase):
    def test_forward(self):
        import torch
        model = PriorityNet()
        x = torch.randn(4, 6)
        out = model(x)
        self.assertEqual(out.shape, (4,))
        self.assertTrue(torch.all(out >= 0))
        self.assertTrue(torch.all(out <= 1))

    def test_predict(self):
        model = PriorityNet()
        score = model.predict([0.9, 0.8, 0.5, 0.7, 0.9, 0.8])
        self.assertGreater(score, 0)
        self.assertLess(score, 1)

    def test_train(self):
        features, labels, _ = generate_dataset(n=2000, seed=42)
        model, metrics = train_priority_net(features, labels, epochs=5)
        self.assertIn("final_val_mse", metrics)
        self.assertLess(metrics["final_val_mse"], 0.1)


if __name__ == "__main__":
    unittest.main()
