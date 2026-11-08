"""The one personal-data scanner (hard rule H5).

find_pii(text) looks for three kinds of personal data:
- a SPECIMEN name from fixtures/data/parties.csv or fixtures/data/documents.csv;
- a passport number: SPECIMEN-PP- followed by seven digits;
- a date of birth held in fixtures/data/parties.csv or fixtures/data/documents.csv.

Each finding names its type and line number, never the value, so the scan's
own output cannot leak what it caught. FLOOR-4 in tools/validate_floor.py
and tools/scan_log.py both call this function.
"""
import re
from functools import lru_cache

from kyc.data_layer import read_csv

PASSPORT_PATTERN = re.compile(r"SPECIMEN-PP-\d{7}")


@lru_cache(maxsize=1)
def known_values() -> tuple[frozenset, frozenset]:
    """Every name and every date of birth in the data files."""
    names, birth_dates = set(), set()
    for row in read_csv("parties.csv"):
        names.add(row["full_name"])
        birth_dates.add(row["date_of_birth"])
    for row in read_csv("documents.csv"):
        names.add(row["name_on_document"])
        birth_dates.add(row["dob_on_document"])
    return frozenset(names - {""}), frozenset(birth_dates - {""})


def find_pii(text: str) -> list[dict]:
    """Every finding: [{"finding": type, "line": n}], lines counted from 1."""
    names, birth_dates = known_values()
    findings = []
    for number, line in enumerate(text.splitlines(), start=1):
        if "SPECIMEN " in line and any(name in line for name in names):
            findings.append({"finding": "specimen_name", "line": number})
        if PASSPORT_PATTERN.search(line):
            findings.append({"finding": "passport_number", "line": number})
        if any(day in line for day in birth_dates):
            findings.append({"finding": "date_of_birth", "line": number})
    return findings
