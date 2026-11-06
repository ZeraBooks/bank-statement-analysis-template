"""Write every file in samples/ from the transactions listed below.

Run from the repository root:  python3 scripts/generate_samples.py
Printed balances are worked out from the opening balance and the rows, so
every month ties by construction. Invalid samples each break one rule.
All businesses, payers and figures are fictional. Output is deterministic.
"""
import csv
import json
import os
import shutil
from decimal import Decimal

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
S = os.path.join(ROOT, "samples")
ROW_COLS = ["Account", "Date", "Description", "Type", "Amount", "Own transfer"]
BAL_COLS = ["Account", "Month", "Printed opening", "Printed closing"]

CHK, SAV = "Checking 6120", "Savings 6138"
# Orchard Row Physical Therapy, April to June 2026. Two accounts, one owner.
ORCHARD = [
    (CHK, "2026-04-01", "ACH DEBIT HOLLOWAY PROPERTIES RENT", "Withdrawal", "-4200.00", ""),
    (CHK, "2026-04-02", "ACH CREDIT MERIDIAN HEALTH PLAN", "Deposit", "8640.00", ""),
    (CHK, "2026-04-06", "CARD SETTLEMENT SQUARE", "Deposit", "3125.50", ""),
    (CHK, "2026-04-08", "PAYROLL ADP NET PAY", "Withdrawal", "-9850.00", ""),
    (CHK, "2026-04-10", "ONLINE TRANSFER TO SAVINGS 6138", "Transfer", "-4000.00", "Yes"),
    (SAV, "2026-04-10", "ONLINE TRANSFER FROM CHECKING 6120", "Transfer", "4000.00", "Yes"),
    (CHK, "2026-04-14", "ACH CREDIT STATE WORKERS COMP FUND", "Deposit", "2310.00", ""),
    (CHK, "2026-04-16", "ACH DEBIT PT EQUIPMENT LEASING", "Withdrawal", "-1180.00", ""),
    (CHK, "2026-04-20", "ACH CREDIT MERIDIAN HEALTH PLAN", "Deposit", "7915.00", ""),
    (CHK, "2026-04-22", "PAYROLL ADP NET PAY", "Withdrawal", "-9850.00", ""),
    (CHK, "2026-04-24", "CARD SETTLEMENT SQUARE", "Deposit", "2980.25", ""),
    (CHK, "2026-04-27", "ACH DEBIT CASCADE MEDICAL SUPPLY", "Withdrawal", "-1645.80", ""),
    (CHK, "2026-04-30", "MONTHLY SERVICE FEE", "Fee", "-25.00", ""),
    (SAV, "2026-04-30", "INTEREST PAYMENT", "Interest", "3.12", ""),
    (CHK, "2026-05-01", "ACH DEBIT HOLLOWAY PROPERTIES RENT", "Withdrawal", "-4200.00", ""),
    (CHK, "2026-05-04", "ACH CREDIT MERIDIAN HEALTH PLAN", "Deposit", "8210.00", ""),
    (CHK, "2026-05-06", "CARD SETTLEMENT SQUARE", "Deposit", "3340.75", ""),
    (CHK, "2026-05-06", "PAYROLL ADP NET PAY", "Withdrawal", "-9850.00", ""),
    (CHK, "2026-05-12", "ACH CREDIT STATE WORKERS COMP FUND", "Deposit", "1980.00", ""),
    (CHK, "2026-05-15", "ACH DEBIT PT EQUIPMENT LEASING", "Withdrawal", "-1180.00", ""),
    (CHK, "2026-05-18", "ACH CREDIT MERIDIAN HEALTH PLAN", "Deposit", "8475.00", ""),
    (SAV, "2026-05-20", "ONLINE TRANSFER TO CHECKING 6120", "Transfer", "-2500.00", "Yes"),
    (CHK, "2026-05-20", "ONLINE TRANSFER FROM SAVINGS 6138", "Transfer", "2500.00", "Yes"),
    (CHK, "2026-05-20", "PAYROLL ADP NET PAY", "Withdrawal", "-9850.00", ""),
    (CHK, "2026-05-22", "CARD SETTLEMENT SQUARE", "Deposit", "3105.40", ""),
    (CHK, "2026-05-26", "ACH DEBIT CASCADE MEDICAL SUPPLY", "Withdrawal", "-2210.35", ""),
    (CHK, "2026-05-28", "ACH DEBIT NORTHWIND INSURANCE", "Withdrawal", "-1420.00", ""),
    (CHK, "2026-05-29", "MONTHLY SERVICE FEE", "Fee", "-25.00", ""),
    (SAV, "2026-05-29", "INTEREST PAYMENT", "Interest", "3.27", ""),
    (CHK, "2026-06-01", "ACH DEBIT HOLLOWAY PROPERTIES RENT", "Withdrawal", "-4200.00", ""),
    (SAV, "2026-06-02", "ONLINE TRANSFER TO CHECKING 6120", "Transfer", "-9000.00", "Yes"),
    (CHK, "2026-06-03", "ONLINE TRANSFER FROM SAVINGS 6138", "Transfer", "9000.00", "Yes"),
    (CHK, "2026-06-03", "PAYROLL ADP NET PAY", "Withdrawal", "-9850.00", ""),
    (CHK, "2026-06-05", "ACH CREDIT MERIDIAN HEALTH PLAN", "Deposit", "8590.00", ""),
    (CHK, "2026-06-08", "CARD SETTLEMENT SQUARE", "Deposit", "3260.10", ""),
    (CHK, "2026-06-11", "ACH CREDIT STATE WORKERS COMP FUND", "Deposit", "2145.00", ""),
    (CHK, "2026-06-15", "ONLINE TRANSFER FROM XX4471", "Transfer", "1800.00", ""),
    (CHK, "2026-06-15", "ACH DEBIT PT EQUIPMENT LEASING", "Withdrawal", "-1180.00", ""),
    (CHK, "2026-06-17", "PAYROLL ADP NET PAY", "Withdrawal", "-9850.00", ""),
    (CHK, "2026-06-19", "ACH CREDIT LAKEVIEW SCHOOL DIST", "Deposit", "11200.00", ""),
    (CHK, "2026-06-22", "ACH CREDIT MERIDIAN HEALTH PLAN", "Deposit", "8320.00", ""),
    (CHK, "2026-06-24", "CARD SETTLEMENT SQUARE", "Deposit", "2875.90", ""),
    (CHK, "2026-06-26", "ACH DEBIT CASCADE MEDICAL SUPPLY", "Withdrawal", "-1930.60", ""),
    (CHK, "2026-06-30", "MONTHLY SERVICE FEE", "Fee", "-25.00", ""),
    (SAV, "2026-06-30", "INTEREST PAYMENT", "Interest", "3.05", ""),
]
OPENING = {CHK: Decimal("12450.00"), SAV: Decimal("30000.00")}


def write(rel, header, rows):
    path = os.path.join(S, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)


def balances(rows, opening):
    out, bal = [], dict(opening)
    for acct in sorted(opening):
        for m in ("2026-04", "2026-05", "2026-06"):
            start = bal[acct]
            bal[acct] += sum(Decimal(r[4]) for r in rows if r[0] == acct and r[1].startswith(m))
            out.append([acct, m, f"{start:.2f}", f"{bal[acct]:.2f}"])
    return out


def main():
    # Fernhill Landscaping: the original single-account example, same files as the root.
    os.makedirs(os.path.join(S, "fernhill-landscaping"), exist_ok=True)
    shutil.copyfile(os.path.join(ROOT, "converted-statements-jul-sep-2026.csv"),
                    os.path.join(S, "fernhill-landscaping", "rows.csv"))
    shutil.copyfile(os.path.join(ROOT, "statement-balances.csv"),
                    os.path.join(S, "fernhill-landscaping", "balances.csv"))

    rows = [list(r) for r in ORCHARD]
    bals = balances(rows, OPENING)
    write("orchard-row-physio/rows.csv", ROW_COLS, rows)
    write("orchard-row-physio/balances.csv", BAL_COLS, bals)

    expected = {}

    def bad(name, rows_, bals_, rule):
        write(f"invalid/{name}/rows.csv", ROW_COLS, rows_)
        write(f"invalid/{name}/balances.csv", BAL_COLS, bals_)
        expected[name] = rule

    def edit(i, col, val):
        r = [list(x) for x in rows]
        r[i][col] = val
        return r

    bad("date-not-iso", edit(1, 1, "04/02/2026"), bals, "BSA-002")
    bad("unknown-type", edit(2, 3, "Credit"), bals, "BSA-003")
    bad("dollar-sign-in-amount", edit(3, 4, "-$9,850.00"), bals, "BSA-004")
    bad("deposit-with-minus-sign", edit(6, 4, "-2310.00"), bals, "BSA-005")
    bad("own-transfer-typo", edit(4, 5, "Y"), bals, "BSA-006")
    r = [list(x) for x in rows]
    del r[11]  # the 1,645.80 supply payment dropped at a page break
    bad("row-dropped", r, bals, "BSA-007")
    b = [list(x) for x in bals]
    b[1][2] = "6696.95"  # May opening mistyped, 27.00 off April's closing
    b[1][3] = f"{Decimal(b[1][3]) + Decimal('27.00'):.2f}"
    bad("opening-does-not-follow", rows, b, "BSA-008")
    bad("month-without-balances", rows, [x for x in bals if x[1] != "2026-05" or x[0] != SAV], "BSA-009")
    r = [list(x) for x in rows if not (x[0] == SAV and x[1] == "2026-06-02")]
    b = balances(r, OPENING)
    bad("transfer-other-side-missing", r, b, "BSA-010")
    with open(os.path.join(S, "invalid", "expected.json"), "w", encoding="utf-8") as fh:
        json.dump(expected, fh, indent=2, sort_keys=True)
        fh.write("\n")
    print("samples written")


if __name__ == "__main__":
    main()
