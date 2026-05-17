from setuptools import setup, find_packages

setup(
    name="camtc",
    version="1.0.0",
    description="Context-Adaptive Multi-Tier Hybrid Consensus Simulator",
    packages=find_packages(),
    python_requires=">=3.11",
    install_requires=[
        "fastapi>=0.104",
        "uvicorn>=0.24",
        "pynacl>=1.5",
        "torch>=2.1",
        "numpy>=1.24",
        "gymnasium>=0.29",
        "stable-baselines3>=2.0",
        "web3>=6.0",
        "httpx>=0.25",
        "jinja2>=3.1",
        "pydantic>=2.0",
        "aiofiles>=23.0",
    ],
)
