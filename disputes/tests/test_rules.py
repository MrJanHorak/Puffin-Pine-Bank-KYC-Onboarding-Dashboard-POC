"""Given tests for the rules participants fill in (Task 6). Run from disputes/:
    python -m unittest discover -s tests -v
"""
import unittest

from triage import load_yaml, rules

CONFIG = load_yaml("rules.yaml")
LEDGER = {"T-1": {"amount": "30.00", "posted_at": "2026-10-12T09:30"}}


def dispute(txn_ids, claimed):
    return {"txn_ids": txn_ids, "claimed_amounts": claimed}


class CheckLedgerTests(unittest.TestCase):
    def test_missing_transaction_blocks(self):
        reasons, flags = rules.check_ledger(dispute(["T-1", "T-9"], ["30.00", "5.00"]), LEDGER, CONFIG)
        self.assertEqual(reasons, ["TXN_NOT_FOUND:T-9"])
        self.assertEqual(flags, [])

    def test_one_cent_difference_passes(self):
        self.assertEqual(rules.check_ledger(dispute(["T-1"], ["30.01"]), LEDGER, CONFIG), ([], []))

    def test_two_cent_difference_flags(self):
        self.assertEqual(rules.check_ledger(dispute(["T-1"], ["30.02"]), LEDGER, CONFIG),
                         ([], ["AMOUNT_MISMATCH:T-1"]))

    def test_every_transaction_is_checked(self):
        ledger = {**LEDGER, "T-2": {"amount": "10.00", "posted_at": "2026-10-12T09:30"}}
        reasons, flags = rules.check_ledger(dispute(["T-1", "T-2"], ["30.00", "12.00"]), ledger, CONFIG)
        self.assertEqual(flags, ["AMOUNT_MISMATCH:T-2"])


class ReportedBeforeTests(unittest.TestCase):
    def test_reported_earlier_the_same_day(self):
        card = {"status": "LOST", "reported_at": "2026-10-03T09:00"}
        self.assertTrue(rules.reported_before(card, "2026-10-03T14:20"))

    def test_reported_after_the_charge(self):
        card = {"status": "STOLEN", "reported_at": "2026-10-20T09:00"}
        self.assertFalse(rules.reported_before(card, "2026-10-15T12:00"))

    def test_active_card(self):
        self.assertFalse(rules.reported_before({"status": "ACTIVE", "reported_at": ""}, "2026-10-15T12:00"))

    def test_no_card_record(self):
        self.assertFalse(rules.reported_before(None, "2026-10-15T12:00"))


if __name__ == "__main__":
    unittest.main()
