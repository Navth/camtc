"""PriorityNet DNN — 3-layer feed-forward network for priority scoring."""
import torch
import torch.nn as nn
import numpy as np
from typing import Optional


class PriorityNet(nn.Module):
    def __init__(self, input_dim: int = 6, hidden_dim: int = 64):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, 1),
            nn.Sigmoid(),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x).squeeze(-1)

    def predict(self, features: list[float] | np.ndarray) -> float:
        self.eval()
        with torch.no_grad():
            x = torch.tensor(features, dtype=torch.float32).unsqueeze(0)
            return self(x).item()


def train_priority_net(
    features: np.ndarray,
    labels: np.ndarray,
    hidden_dim: int = 64,
    epochs: int = 200,
    lr: float = 1e-3,
    batch_size: int = 256,
    val_split: float = 0.2,
    seed: int = 42,
) -> tuple[PriorityNet, dict]:
    """Train PriorityNet and return (model, metrics)."""
    torch.manual_seed(seed)

    n = len(features)
    indices = torch.randperm(n)
    n_val = int(n * val_split)
    val_idx, train_idx = indices[:n_val], indices[n_val:]

    X_train = torch.tensor(features[train_idx.numpy()], dtype=torch.float32)
    y_train = torch.tensor(labels[train_idx.numpy()], dtype=torch.float32)
    X_val = torch.tensor(features[val_idx.numpy()], dtype=torch.float32)
    y_val = torch.tensor(labels[val_idx.numpy()], dtype=torch.float32)

    model = PriorityNet(input_dim=6, hidden_dim=hidden_dim)
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    criterion = nn.MSELoss()

    metrics = {"train_loss": [], "val_loss": [], "val_mse": []}
    best_val_mse = float("inf")
    best_state = None

    for epoch in range(epochs):
        model.train()
        perm = torch.randperm(len(X_train))
        epoch_loss = 0.0
        n_batches = 0
        for start in range(0, len(X_train), batch_size):
            idx = perm[start:start + batch_size]
            xb = X_train[idx]
            yb = y_train[idx]
            pred = model(xb)
            loss = criterion(pred, yb)
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            epoch_loss += loss.item()
            n_batches += 1

        model.eval()
        with torch.no_grad():
            val_pred = model(X_val)
            val_mse = criterion(val_pred, y_val).item()

        avg_loss = epoch_loss / max(n_batches, 1)
        metrics["train_loss"].append(avg_loss)
        metrics["val_loss"].append(val_mse)
        metrics["val_mse"].append(val_mse)

        if val_mse < best_val_mse:
            best_val_mse = val_mse
            best_state = {k: v.clone() for k, v in model.state_dict().items()}

    if best_state:
        model.load_state_dict(best_state)

    tier1_th = 0.85
    tier2_th = 0.60

    def classify(score: float) -> int:
        if score > tier1_th:
            return 1
        elif score > tier2_th:
            return 2
        return 3

    model.eval()
    with torch.no_grad():
        val_scores = model(X_val).numpy()
        val_labels = y_val.numpy()
        pred_tiers = np.array([classify(s) for s in val_scores])
        true_tiers = np.array([classify(s) for s in val_labels])
        accuracy = (pred_tiers == true_tiers).mean()

    metrics["final_val_mse"] = best_val_mse
    metrics["tier_accuracy"] = accuracy
    metrics["epochs_trained"] = epochs

    return model, metrics


def save_model(model: PriorityNet, path: str) -> None:
    torch.save(model.state_dict(), path)


def load_model(path: str, hidden_dim: int = 64) -> PriorityNet:
    model = PriorityNet(hidden_dim=hidden_dim)
    model.load_state_dict(torch.load(path, map_location="cpu"))
    model.eval()
    return model
