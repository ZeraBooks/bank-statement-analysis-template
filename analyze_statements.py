"""Summarize converted bank statement rows the way a lender or auditor reads them.

Input is one CSV of statement rows for one account (Account, Date, Description,
Type, Amount, Own transfer) plus the printed opening and closing balance of
each month. For each month it prints:

  - all deposits, transfers in from your own accounts, and business deposits
  - withdrawals
  - closing balance worked out from the rows, checked against the printed one
  - lowest and average daily balance, from end-of-day balances
  - NSF and overdraft items (Fee rows or words like NSF, returned item, overdraft)

Then it lists transfers between your own accounts, Transfer rows you haven't
tagged yet, large deposits (at least 2 times the average business deposit),
and payers who deposited in every month.

Usage:
  python3 analyze_statements.py converted-statements-jul-sep-2026.csv statement-balances.csv [summary.csv]
Python 3, standard library only.
"""
import calendar
import csv
import sys
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

LARGE_MULTIPLE = Decimal("2")
NSF_WORDS = ("NSF", "RETURNED ITEM", "OVERDRAFT")
CENT = Decimal("0.01")


def d(cell):
    return Decimal(cell.strip().replace(",", "")) if cell and cell.strip() else Decimal("0")


def payer(desc):
    # Drop the bank's prefix so "ACH CREDIT CEDAR RIDGE APTS" groups as one payer.
    for p in ("MOBILE DEPOSIT ", "ACH CREDIT ", "CARD SETTLEMENT ", "DEPOSIT "):
        if desc.upper().startswith(p):
            return desc[len(p):].strip()
    return desc.strip()


def main(rows_path, balances_path, out_path=None):
    ok = True
    with open(balances_path, newline="", encoding="utf-8") as f:
        printed = {r["Month"]: (d(r["Printed opening"]), d(r["Printed closing"])) for r in csv.DictReader(f)}
    with open(rows_path, newline="", encoding="utf-8") as f:
        rows = sorted(csv.DictReader(f), key=lambda r: r["Date"])

    months = sorted(printed)
    summary = []
    transfers, untagged, business = [], [], []
    payers_by_month = {}
    balance = printed[months[0]][0]
    for m in months:
        opening, closing_printed = printed[m]
        if balance != opening:
            ok = False
            print(f"{m}: printed opening {opening:,.2f} doesn't follow last month's closing {balance:,.2f}. A month or rows are missing.")
            balance = opening
        mrows = [r for r in rows if r["Date"].startswith(m)]
        s = {"Month": m, "All deposits": Decimal("0"), "Own-account transfers in": Decimal("0"),
             "Business deposits": Decimal("0"), "Withdrawals": Decimal("0"), "NSF or overdraft items": 0}
        y, mo = int(m[:4]), int(m[5:7])
        days = calendar.monthrange(y, mo)[1]
        end_of_day = {}
        for r in mrows:
            amt = d(r["Amount"])
            own = r.get("Own transfer", "").strip().lower() == "yes"
            balance += amt
            end_of_day[r["Date"]] = balance
            if amt > 0:
                s["All deposits"] += amt
                if own:
                    s["Own-account transfers in"] += amt
                else:
                    s["Business deposits"] += amt
                    business.append(r)
                    payers_by_month.setdefault(payer(r["Description"]), set()).add(m)
            else:
                s["Withdrawals"] -= amt
            if own:
                transfers.append(r)
            elif r["Type"].strip().lower() == "transfer":
                untagged.append(r)
            if r["Type"].strip().lower() == "fee" and any(w in r["Description"].upper() for w in NSF_WORDS):
                s["NSF or overdraft items"] += 1
        # Daily balances: carry the last balance forward through days with no rows.
        running, total, low = opening, Decimal("0"), None
        for i in range(days):
            day = (date(y, mo, 1) + timedelta(days=i)).isoformat()
            running = end_of_day.get(day, running)
            total += running
            low = running if low is None or running < low else low
        s["Closing balance"] = balance
        s["Lowest daily balance"] = low
        s["Average daily balance"] = (total / days).quantize(CENT, ROUND_HALF_UP)
        if balance != closing_printed:
            ok = False
            print(f"{m}: rows give a closing of {balance:,.2f}, the statement prints {closing_printed:,.2f}. Fix the rows before using the summary.")
        summary.append(s)

    cols = ["Month", "All deposits", "Own-account transfers in", "Business deposits", "Withdrawals",
            "Closing balance", "Lowest daily balance", "Average daily balance", "NSF or overdraft items"]
    tot = {c: sum(s[c] for s in summary) for c in cols[1:5]}
    tot["NSF or overdraft items"] = sum(s["NSF or overdraft items"] for s in summary)
    avg_business = (tot["Business deposits"] / len(summary)).quantize(CENT, ROUND_HALF_UP)

    print(f"{'Month':<9}{'Deposits':>12}{'Own in':>11}{'Business':>12}{'Withdrawn':>12}{'Closing':>11}{'Lowest':>11}{'Avg daily':>11}{'NSF/OD':>7}")
    for s in summary:
        print(f"{s['Month']:<9}{s['All deposits']:>12,.2f}{s['Own-account transfers in']:>11,.2f}{s['Business deposits']:>12,.2f}"
              f"{s['Withdrawals']:>12,.2f}{s['Closing balance']:>11,.2f}{s['Lowest daily balance']:>11,.2f}"
              f"{s['Average daily balance']:>11,.2f}{s['NSF or overdraft items']:>7}")
    print(f"{'Total':<9}{tot['All deposits']:>12,.2f}{tot['Own-account transfers in']:>11,.2f}{tot['Business deposits']:>12,.2f}"
          f"{tot['Withdrawals']:>12,.2f}{'':>33}{tot['NSF or overdraft items']:>7}")
    print(f"Average monthly business deposits: {avg_business:,.2f}")
    share = tot["Own-account transfers in"] / tot["Business deposits"] * 100
    print(f"Counting own-account transfers as income would overstate deposits by {share:.1f}%.")

    print("\nTransfers between your own accounts (left out of business deposits):")
    for r in transfers:
        print(f"  {r['Date']}  {r['Description']}  {d(r['Amount']):,.2f}")
    if untagged:
        ok = False
        print("Transfer rows not tagged as own-account or business. Tag them and run again:")
        for r in untagged:
            print(f"  {r['Date']}  {r['Description']}  {d(r['Amount']):,.2f}")

    avg_item = tot["Business deposits"] / len(business)
    limit = (avg_item * LARGE_MULTIPLE).quantize(CENT, ROUND_HALF_UP)
    print(f"\nLarge deposits (at least {LARGE_MULTIPLE} x the average business deposit of {avg_item:,.2f}, so {limit:,.2f} or more):")
    large = [r for r in business if d(r["Amount"]) >= limit]
    for r in large:
        print(f"  {r['Date']}  {r['Description']}  {d(r['Amount']):,.2f}  (get the source document)")
    if not large:
        print("  none")

    print("\nPayers who deposited in every month:")
    for p, ms in sorted(payers_by_month.items()):
        if len(ms) == len(months):
            print(f"  {p}")

    if out_path:
        with open(out_path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f, lineterminator="\n")
            w.writerow(cols)
            for s in summary:
                w.writerow([s["Month"]] + [f"{s[c]:.2f}" for c in cols[1:8]] + [s["NSF or overdraft items"]])
            w.writerow(["Total"] + [f"{tot[c]:.2f}" for c in cols[1:5]] + ["", "", "", tot["NSF or overdraft items"]])
        print(f"\nSummary written to {out_path}")

    print("\nAll checks pass." if ok else "\nSome checks failed; see above.")
    return ok


if __name__ == "__main__":
    a = sys.argv[1:] + [None] * 3
    sys.exit(0 if main(a[0] or "converted-statements-jul-sep-2026.csv",
                       a[1] or "statement-balances.csv", a[2]) else 1)
