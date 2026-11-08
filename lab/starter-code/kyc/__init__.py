"""Puffin & Pine Bank KYC onboarding assistant: the end-of-Day-9 build.

SPECIMEN: synthetic course data only. Folder paths are worked out from this
package's own folder, so data and config are found from any working folder.
"""
from pathlib import Path

STARTER_ROOT = Path(__file__).resolve().parent.parent
# The lab data set lives once, in the lab's fixtures/ folder beside starter-code/.
DATA_DIR = STARTER_ROOT.parent / "fixtures" / "data"
CONFIG_DIR = STARTER_ROOT / "config"
