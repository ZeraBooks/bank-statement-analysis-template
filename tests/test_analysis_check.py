import csv
import glob
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from decimal import Decimal

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "cli"))
import analysis_check as ac  # noqa: E402

S = os.path.join(ROOT, "samples")
CLI = os.path.join(ROOT, "cli", "analysis_check.py")


def sample(name):
    return os.path.join(S, name, "rows.csv"), os.path.join(S, name, "balances.csv")


def errors(issues):
    return [i for i in issues if i.severity == "error"]


class Fernhill(unittest.TestCase):
    """The original single-account example must give the same figures as the guide."""

    def setUp(self):
        self.issues, self.r = ac.analyze(*sample("fernhill-landscaping"))

    def test_no_errors_and_two_unmatched_transfer_warnings(self):
        self.assertEqual(errors(self.issues), [])
        self.assertEqual([i.rule for i in self.issues], ["BSA-010", "BSA-010"])

    def test_matches_the_committed_summary(self):
        with open(os.path.join(ROOT, "summary-jul-sep-2026.csv"), encoding="utf-8") as fh:
            old = [r for r in csv.DictReader(fh) if r["Month"] != "Total"]
        for o, n in zip(old, self.r["per_account"]):
            self.assertEqual(o["All deposits"], str(n["all_deposits"]))
            self.assertEqual(o["Business deposits"], str(n["business_deposits"]))
            self.assertEqual(o["Withdrawals"], str(n["all_withdrawals"]))
            self.assertEqual(o["Closing balance"], str(n["closing_balance"]))
            self.assertEqual(o["Lowest daily balance"], str(n["lowest_daily_balance"]))
            self.assertEqual(o["Average daily balance"], str(n["average_daily_balance"]))
            self.assertEqual(int(o["NSF or overdraft items"]), n["nsf_overdraft_items"])

    def test_headline_figures(self):
        t = self.r["totals"]
        self.assertEqual(t["business_deposits"], Decimal("129650.00"))
        self.assertEqual(t["average_monthly_business_deposits"], Decimal("43216.67"))
        self.assertEqual(str(t["overstatement_if_transfers_counted_percent"]), "10.0")
        self.assertEqual([i["amount"] for i in self.r["large_deposits"]["items"]], [Decimal("14500.00")])

    def test_root_files_are_the_sample(self):
        self.assertEqual(open(os.path.join(ROOT, "converted-statements-jul-sep-2026.csv")).read(),
                         open(sample("fernhill-landscaping")[0]).read())


class Orchard(unittest.TestCase):
    """Two accounts, transfers matched both ways, one untagged transfer."""

    def setUp(self):
        self.issues, self.r = ac.analyze(*sample("orchard-row-physio"))

    def test_only_the_untagged_transfer_is_flagged(self):
        self.assertEqual([(i.rule, i.where) for i in self.issues], [("BSA-011", "Checking 6120 2026-06-15")])

    def test_all_three_transfers_match(self):
        got = [(m["from_account"], m["to_account"], m["amount"]) for m in self.r["matched_transfers"]]
        self.assertEqual(got, [("Checking 6120", "Savings 6138", Decimal("4000.00")),
                               ("Savings 6138", "Checking 6120", Decimal("2500.00")),
                               ("Savings 6138", "Checking 6120", Decimal("9000.00"))])

    def test_months_add_up_by_hand(self):
        chk = [s for s in self.r["per_account"] if s["account"] == "Checking 6120"]
        self.assertEqual(Decimal("12450.00") + Decimal("24970.75") - Decimal("30750.80"), chk[0]["closing_balance"])
        self.assertEqual(chk[0]["closing_balance"] + Decimal("27611.15") - Decimal("28735.35"), chk[1]["closing_balance"])
        self.assertEqual(chk[1]["closing_balance"] + Decimal("47191.00") - Decimal("27035.60"), chk[2]["closing_balance"])
        self.assertEqual(chk[2]["closing_balance"], Decimal("25701.15"))

    def test_combined_view_drops_transfers_from_both_sides(self):
        c = self.r["combined"]
        for m in c:
            self.assertEqual(m["own_transfers_in"], m["own_transfers_out"], m["month"])
            self.assertEqual(m["all_deposits"] - m["own_transfers_in"], m["business_deposits"])
        self.assertEqual(c[-1]["closing_balance"], Decimal("25701.15") + Decimal("22509.44"))

    def test_totals(self):
        t = self.r["totals"]
        self.assertEqual(t["business_deposits"], Decimal("88282.34"))
        self.assertEqual(t["own_transfers_in"], Decimal("15500.00"))
        self.assertEqual(str(t["overstatement_if_transfers_counted_percent"]), "17.6")
        self.assertEqual(t["average_monthly_business_deposits"], Decimal("29427.45"))

    def test_june_lowest_balance_and_large_deposit(self):
        june = [s for s in self.r["per_account"] if s["account"] == "Checking 6120"][2]
        self.assertEqual(june["lowest_daily_balance"], Decimal("495.75"))
        ld = self.r["large_deposits"]
        self.assertEqual(ld["threshold"], Decimal("8828.24"))
        self.assertEqual([i["description"] for i in ld["items"]], ["ACH CREDIT LAKEVIEW SCHOOL DIST"])

    def test_repeat_payers_skip_interest(self):
        self.assertEqual(self.r["repeat_payers"], ["MERIDIAN HEALTH PLAN", "SQUARE", "STATE WORKERS COMP FUND"])


class Invalid(unittest.TestCase):
    def test_each_invalid_sample_fails_only_its_rule(self):
        expected = json.load(open(os.path.join(S, "invalid", "expected.json"), encoding="utf-8"))
        dirs = sorted(os.path.basename(os.path.dirname(p)) for p in glob.glob(os.path.join(S, "invalid", "*", "rows.csv")))
        self.assertEqual(sorted(expected), dirs)
        for name, rule in expected.items():
            out = subprocess.run([sys.executable, CLI, "--json", *sample(os.path.join("invalid", name))],
                                 capture_output=True, text=True)
            self.assertEqual(out.returncode, 1, name)
            j = json.loads(out.stdout)
            self.assertEqual({i["rule"] for i in j["issues"] if i["severity"] == "error"}, {rule}, name)
            self.assertIsNone(j["analysis"], name)

    def test_unreadable_file_exits_2(self):
        out = subprocess.run([sys.executable, CLI, "nope.csv", "nope.csv"], capture_output=True)
        self.assertEqual(out.returncode, 2)


class Output(unittest.TestCase):
    def test_json_matches_summary_schema(self):
        schema = json.load(open(os.path.join(ROOT, "schema", "analysis-summary.schema.json"), encoding="utf-8"))
        out = subprocess.run([sys.executable, CLI, "--json", *sample("orchard-row-physio")], capture_output=True, text=True)
        a = json.loads(out.stdout)["analysis"]
        for k in schema["required"]:
            self.assertIn(k, a)
        money = re.compile(schema["properties"]["per_account"]["items"]["properties"]["all_deposits"]["pattern"])
        for s in a["per_account"] + a["combined"]:
            for k, v in s.items():
                if k not in ("account", "month", "nsf_overdraft_items", "deposit_count"):
                    self.assertRegex(v, money, k)

    def test_summary_csv_has_combined_rows(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "s.csv")
            subprocess.run([sys.executable, CLI, *sample("orchard-row-physio"), "--summary", p], check=True, capture_output=True)
            rows = list(csv.DictReader(open(p, encoding="utf-8")))
        self.assertEqual(len(rows), 9)
        self.assertEqual(rows[-1]["Account"], "All accounts")

    def test_input_samples_match_input_schemas(self):
        rs = json.load(open(os.path.join(ROOT, "schema", "statement-row.schema.json"), encoding="utf-8"))
        for name in ("fernhill-landscaping", "orchard-row-physio"):
            for row in csv.DictReader(open(sample(name)[0], encoding="utf-8")):
                self.assertIn(row["Type"], rs["properties"]["Type"]["enum"])
                self.assertRegex(row["Amount"], rs["properties"]["Amount"]["pattern"])


if __name__ == "__main__":
    unittest.main()
