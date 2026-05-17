#!/usr/bin/env python3
"""CAMTC Simulator — Main entry point.

Starts the gateway API server and the real-time dashboard.

Usage:
    python -m camtc.main [--gateway-port 8000] [--dashboard-port 8080] [--train]
"""
import argparse
import asyncio
import sys
import os
import threading

# Ensure package is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main():
    parser = argparse.ArgumentParser(description="CAMTC Simulator")
    parser.add_argument("--gateway-port", type=int, default=8000, help="Gateway API port")
    parser.add_argument("--dashboard-port", type=int, default=8080, help="Dashboard port")
    parser.add_argument("--train", action="store_true", help="Train PriorityNet and RL agent on startup")
    parser.add_argument("--n-validators", type=int, default=10, help="Number of validator nodes")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    args = parser.parse_args()

    from camtc.config.settings import Settings
    from camtc.simulator import CAMTCSimulator
    from camtc.gateway.server import create_gateway_app
    from camtc.dashboard.app import create_dashboard_app

    settings = Settings(
        n_validators=args.n_validators,
        seed=args.seed,
        gateway_port=args.gateway_port,
        dashboard_port=args.dashboard_port,
    )

    print("=" * 60)
    print("  CAMTC — Context-Adaptive Multi-Tier Hybrid Consensus")
    print("  Simulator v1.0.0")
    print("=" * 60)
    print()

    # Create simulator
    sim = CAMTCSimulator(settings)

    # Train models if requested
    if args.train:
        print("[1/2] Training PriorityNet DNN...")
        result = sim.train_priority_net(epochs=200)
        print(f"       MSE: {result['mse']}  Accuracy: {result['accuracy']}")
        print("[2/2] Training PPO RL Agent...")
        sim.train_rl_agent(steps=5000)
        print("       Done.")
        print()

    # Create FastAPI apps
    gateway_app = create_gateway_app(simulator=sim)
    dashboard_app = create_dashboard_app(simulator=sim)

    import uvicorn

    print(f"  Gateway API:    http://localhost:{args.gateway_port}")
    print(f"  API Docs:       http://localhost:{args.gateway_port}/docs")
    print(f"  Dashboard:      http://localhost:{args.dashboard_port}")
    print()
    print("  Press Ctrl+C to stop.")
    print()

    # Run both servers
    def run_gateway():
        uvicorn.run(gateway_app, host="0.0.0.0", port=args.gateway_port, log_level="warning")

    def run_dashboard():
        uvicorn.run(dashboard_app, host="0.0.0.0", port=args.dashboard_port, log_level="warning")

    gateway_thread = threading.Thread(target=run_gateway, daemon=True)
    dashboard_thread = threading.Thread(target=run_dashboard, daemon=True)

    gateway_thread.start()
    dashboard_thread.start()

    try:
        gateway_thread.join()
    except KeyboardInterrupt:
        print("\nShutting down...")


if __name__ == "__main__":
    main()
