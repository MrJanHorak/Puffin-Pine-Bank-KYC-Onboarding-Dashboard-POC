"""Settings: a command-line option, then the environment, then .env.

.env is copied from .env.example. With no .env at all, every script runs in
replay, so no key is ever needed for a lesson step.
"""
import os

from dotenv import load_dotenv

DEFAULTS = {
    "KYC_MODE": "replay",
    "KYC_RECORDINGS": "recordings/current",
    "MODEL_API_KEY": "",
    "MODEL_NAME_LARGE": "",
    "KYC_POLICY_SEARCH": "off",
    "KYC_POLICY_AS_OF_DATE": "2026-11-05",
}


def setting(name: str, option: str | None = None) -> str:
    """The value of one setting; a blank value counts as not set."""
    if option:
        return option
    # load_dotenv never overrides a variable already in the environment.
    load_dotenv(".env")
    return os.environ.get(name) or DEFAULTS.get(name, "")
