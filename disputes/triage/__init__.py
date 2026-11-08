"""Card dispute triage assistant: a SPECIMEN teaching build for Puffin & Pine Bank.

Every name, ID, rule and number in this package is invented for training.
"""
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
CONFIG_DIR = ROOT / "config"
POLICY_DIR = ROOT / "policy_manual"
RECORDINGS_DIR = ROOT / "recordings"
STATE_DIR = ROOT / "state"
LOG_DIR = ROOT / "logs"


def load_yaml(name: str) -> dict:
    return yaml.safe_load((CONFIG_DIR / name).read_text(encoding="utf-8"))
