"""Reads the SPECIMEN dispute files. No model, no network.

Card numbers in a customer statement are masked here, when the data loads,
before any tool, the model, the page or the log can read them (hard rule H8).
"""
import csv
import json
import re

from triage import DATA_DIR

# 13 to 19 digits, with optional single spaces or dashes between them.
CARD_NUMBER = re.compile(r"(?<![\d])(?:\d[ -]?){12,18}\d(?![\d])")


def mask_card_numbers(text: str) -> str:
    def mask(match):
        digits = re.sub(r"\D", "", match.group(0))
        return "**** **** **** " + digits[-4:]
    return CARD_NUMBER.sub(mask, text or "")


def read_csv(name: str) -> list[dict]:
    with open(DATA_DIR / name, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def disputes() -> dict:
    rows = {}
    with open(DATA_DIR / "disputes.jsonl", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                row = json.loads(line)
                rows[row["dispute_id"]] = row
    return rows


def load_dispute(dispute_id: str) -> dict | None:
    row = disputes().get(dispute_id)
    if row is None:
        return None
    row = dict(row)
    row["customer_statement"] = mask_card_numbers(row.get("customer_statement", ""))
    return row


def transactions_for(card_id: str) -> dict:
    return {r["txn_id"]: r for r in read_csv("transactions.csv")
            if r["card_id"] == card_id}


def card_status(card_id: str) -> dict | None:
    return next((r for r in read_csv("card_status.csv") if r["card_id"] == card_id), None)


def open_dispute_txns(exclude_dispute: str) -> dict:
    """txn_id -> dispute_id for disputes still OPEN, other than this one."""
    return {r["txn_id"]: r["dispute_id"] for r in read_csv("open_disputes.csv")
            if r["status"] == "OPEN" and r["dispute_id"] != exclude_dispute}
