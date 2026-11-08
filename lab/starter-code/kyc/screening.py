"""Watchlist screening against the Global Designations List (SPECIMEN).

match_party scores a party's name against every list entry of the same kind
(a person against people, a company against companies). It reports scores;
it never decides whether a candidate is the same person (hard rules H1, H3).
Screening IDs reuse the party number (SPECIMEN-PTY-0013 gives
SPECIMEN-SCR-0013), so a replayed run gets the same ID every time.
"""
import difflib

from kyc.data_layer import read_csv
from kyc.rules import load_config, normalise_name

LIST_NAME = "Global Designations List (SPECIMEN)"
# Entries scoring below this are not listed as candidates at all.
CANDIDATE_FLOOR = 0.75


def name_score(left: str, right: str) -> float:
    """How alike two names are, from 0 to 1, rounded to two places."""
    matcher = difflib.SequenceMatcher(None, normalise_name(left),
                                      normalise_name(right))
    return round(matcher.ratio(), 2)


def match_party(party: dict) -> dict:
    """Screen one party; the answer holds IDs, scores and the list version."""
    threshold = load_config()["possible_match_threshold"]
    watchlist = read_csv("watchlist.csv")
    name = party.get("full_name") or party.get("legal_name") or ""
    candidates = []
    for entry in watchlist:
        if entry["entity_type"] != party["party_type"]:
            continue
        score = name_score(name, entry["full_name"])
        if score >= CANDIDATE_FLOOR:
            candidates.append({"entry_id": entry["entry_id"],
                               "list_type": entry["list_type"],
                               "score": score})
    candidates.sort(key=lambda c: (-c["score"], c["entry_id"]))
    possible = any(c["score"] >= threshold for c in candidates)
    return {
        "found": True,
        "screening_id": party["party_id"].replace("-PTY-", "-SCR-"),
        "party_id": party["party_id"],
        "party_type": party["party_type"],
        "outcome": "POSSIBLE_MATCH" if possible else "NO_MATCH",
        "candidates": candidates,
        "list_name": LIST_NAME,
        "list_version": max(entry["list_version"] for entry in watchlist),
    }
