#!/usr/bin/env python3
"""Check converted bank statement rows, then build the analysis a lender or auditor reads.

    python3 cli/analysis_check.py ROWS.csv BALANCES.csv
    python3 cli/analysis_check.py ROWS.csv BALANCES.csv --summary summary.csv
    python3 cli/analysis_check.py ROWS.csv BALANCES.csv --json

ROWS.csv holds every transaction for one or more accounts of the same owner
(Account, Date, Description, Type, Amount, Own transfer). BALANCES.csv holds the
opening and closing balance printed on each account's monthly statement.

The rows are checked first (rules BSA-001 to BSA-011 in rules/analysis-rules.csv).
The analysis is only printed when every month of every account reaches its
printed closing balance, because an analysis built on incomplete rows is wrong
in a way nobody can see.

Exit code 0 when there are no errors (warnings may remain), 1 when there are,
2 when a file can't be read. Python 3.8+, standard library only.
Part of https://github.com/ZeraBooks/bank-statement-analysis-template
(ZeraBooks, https://www.zerabooks.com/bank-statement-analysis).
"""
import argparse
import calendar
import csv
import datetime as dt
import json
import re
import sys
from decimal import Decimal, ROUND_HALF_UP

ROW_COLS = ["Account", "Date", "Description", "Type", "Amount", "Own transfer"]
BAL_COLS = ["Account", "Month", "Printed opening", "Printed closing"]
TYPES = {"deposit": 1, "interest": 1, "withdrawal": -1, "fee": -1, "check": -1, "transfer": 0}
AMOUNT_RE = re.compile(r"^-?(0|[1-9][0-9]*)\.[0-9]{2}$")
MONTH_RE = re.compile(r"^[0-9]{4}-(0[1-9]|1[0-2])$")
NSF_WORDS = ("NSF", "RETURNED ITEM", "OVERDRAFT")
PAYER_PREFIXES = ("MOBILE DEPOSIT ", "ACH CREDIT ", "CARD SETTLEMENT ", "DEPOSIT ")
LARGE_MULTIPLE = Decimal("2")
MATCH_DAYS = 3
CENT = Decimal("0.01")
ZERO = Decimal("0.00")


class Issue:
    def __init__(self, rule, severity, where, message):
        self.rule, self.severity, self.where, self.message = rule, severity, where, message

    def as_dict(self):
        return {"rule": self.rule, "severity": self.severity, "where": self.where, "message": self.message}

    def __str__(self):
        return f"{self.severity.upper():7} {self.rule} {self.where}: {self.message}"


class ReadError(Exception):
    pass


def read(path, cols, rule):
    try:
        with open(path, newline="", encoding="utf-8-sig") as fh:
            reader = csv.DictReader(fh)
            header = reader.fieldnames or []
            rows = list(reader)
    except (OSError, UnicodeDecodeError) as exc:
        raise ReadError(f"can't read {path}: {exc}")
    if header != cols:
        return rows, [Issue(rule, "error", path, f"columns must be exactly: {', '.join(cols)} (found: {', '.join(header)})")]
    return rows, []


def payer(desc):
    up = desc.upper()
    for p in PAYER_PREFIXES:
        if up.startswith(p):
            return desc[len(p):].strip()
    return desc.strip()


def load_rows(path):
    raw, issues = read(path, ROW_COLS, "BSA-001")
    if issues:
        return [], issues
    rows = []
    for i, r in enumerate(raw, start=2):
        where = f"rows line {i}"
        try:
            when = dt.date.fromisoformat(r["Date"].strip())
        except ValueError:
            issues.append(Issue("BSA-002", "error", where, f"date '{r['Date']}' must be YYYY-MM-DD"))
            continue
        typ = r["Type"].strip().lower()
        if typ not in TYPES:
            issues.append(Issue("BSA-003", "error", where, f"Type '{r['Type']}' must be one of Deposit, Withdrawal, Fee, Check, Interest, Transfer"))
            continue
        amt_text = r["Amount"].strip()
        if not AMOUNT_RE.match(amt_text):
            issues.append(Issue("BSA-004", "error", where, f"amount '{amt_text}' must be a plain signed number like -1850.00"))
            continue
        amt = Decimal(amt_text)
        if amt == 0 or (TYPES[typ] and (amt > 0) != (TYPES[typ] > 0)):
            issues.append(Issue("BSA-005", "error", where,
                                f"a {r['Type']} of {amt} has the wrong sign: money in is positive, money out negative"))
            continue
        own = r["Own transfer"].strip()
        if own.lower() not in ("yes", ""):
            issues.append(Issue("BSA-006", "error", where, f"Own transfer is '{own}'; use Yes or leave it blank"))
            continue
        rows.append({"line": i, "account": r["Account"].strip(), "date": when, "description": r["Description"].strip(),
                     "type": typ, "amount": amt, "own": own.lower() == "yes"})
    return rows, issues


def load_balances(path):
    raw, issues = read(path, BAL_COLS, "BSA-001")
    out = {}
    for i, r in enumerate(raw, start=2):
        where = f"balances line {i}"
        m = r["Month"].strip()
        if not MONTH_RE.match(m):
            issues.append(Issue("BSA-002", "error", where, f"Month '{m}' must be YYYY-MM"))
            continue
        vals = []
        for c in ("Printed opening", "Printed closing"):
            if not AMOUNT_RE.match(r[c].strip()):
                issues.append(Issue("BSA-004", "error", where, f"{c} '{r[c]}' must be a plain number"))
                break
            vals.append(Decimal(r[c].strip()))
        if len(vals) == 2:
            out.setdefault(r["Account"].strip(), {})[m] = tuple(vals)
    return out, issues


def match_transfers(rows):
    """BSA-010 and BSA-011: pair own-account transfers across accounts, flag untagged ones."""
    issues = []
    accounts = {r["account"] for r in rows}
    used = set()
    pairs = []
    for r in rows:
        if not r["own"] or r["line"] in used:
            continue
        others = [o for o in rows if o["own"] and o["account"] != r["account"] and o["line"] not in used
                  and o["amount"] == -r["amount"] and abs((o["date"] - r["date"]).days) <= MATCH_DAYS]
        if others:
            o = min(others, key=lambda x: abs((x["date"] - r["date"]).days))
            used.update({r["line"], o["line"]})
            pairs.append((r, o))
        elif len(accounts) == 1:
            issues.append(Issue("BSA-010", "warning", f"{r['account']} {r['date']}",
                                f"own transfer {r['amount']} ({r['description']}): the other account isn't in the file. "
                                "Convert its statements too so this can be matched"))
        else:
            issues.append(Issue("BSA-010", "error", f"{r['account']} {r['date']}",
                                f"own transfer {r['amount']} ({r['description']}) has no opposite entry within {MATCH_DAYS} days "
                                "in the other accounts. Either it isn't an own transfer, or a row is missing"))
    for r in rows:
        if r["type"] == "transfer" and not r["own"]:
            issues.append(Issue("BSA-011", "warning", f"{r['account']} {r['date']}",
                                f"Transfer {r['amount']} ({r['description']}) isn't tagged, so it counts as business money. If it came "
                                "from another account the owner holds, tag it Yes and add that account's statements so both sides match"))
    return pairs, issues


def month_list(first, last):
    out, y, m = [], int(first[:4]), int(first[5:7])
    while f"{y}-{m:02d}" <= last:
        out.append(f"{y}-{m:02d}")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def summarize_account(name, rows, printed):
    """BSA-007 to BSA-009 for one account, plus its monthly figures."""
    issues, months = [], []
    have = sorted(printed)
    row_months = sorted({r["date"].strftime("%Y-%m") for r in rows})
    for m in row_months:
        if m not in printed:
            issues.append(Issue("BSA-009", "error", f"{name} {m}", "rows for a month with no printed balances. Add the statement's opening and closing"))
    span = month_list(have[0], have[-1]) if have else []
    for m in span:
        if m not in printed:
            issues.append(Issue("BSA-009", "error", f"{name} {m}", "statement missing between the first and last month"))
    prev_close = None
    for m in span:
        if m not in printed:
            prev_close = None
            continue
        opening, closing = printed[m]
        if prev_close is not None and opening != prev_close:
            issues.append(Issue("BSA-008", "error", f"{name} {m}",
                                f"printed opening {opening} doesn't equal last month's printed closing {prev_close} ({opening - prev_close:+})"))
        prev_close = closing
        y, mo = int(m[:4]), int(m[5:7])
        mrows = sorted([r for r in rows if r["date"].strftime("%Y-%m") == m], key=lambda r: (r["date"], r["line"]))
        s = {"account": name, "month": m, "printed_opening": opening, "printed_closing": closing,
             "all_deposits": ZERO, "own_transfers_in": ZERO, "business_deposits": ZERO,
             "all_withdrawals": ZERO, "own_transfers_out": ZERO, "business_withdrawals": ZERO, "nsf_overdraft_items": 0,
             "deposit_count": 0}
        bal, eod = opening, {}
        for r in mrows:
            a = r["amount"]
            bal += a
            eod[r["date"]] = bal
            if a > 0:
                s["all_deposits"] += a
                if r["own"]:
                    s["own_transfers_in"] += a
                else:
                    s["business_deposits"] += a
                    s["deposit_count"] += 1
            else:
                s["all_withdrawals"] -= a
                if r["own"]:
                    s["own_transfers_out"] -= a
                else:
                    s["business_withdrawals"] -= a
            if r["type"] == "fee" and any(w in r["description"].upper() for w in NSF_WORDS):
                s["nsf_overdraft_items"] += 1
        if bal != closing:
            issues.append(Issue("BSA-007", "error", f"{name} {m}",
                                f"opening {opening} + rows {bal - opening} = {bal}, but the statement prints {closing} "
                                f"(off by {bal - closing:+}). A row is missing, doubled or has the wrong sign"))
        days = calendar.monthrange(y, mo)[1]
        running, total, low = opening, ZERO, None
        for d in range(1, days + 1):
            running = eod.get(dt.date(y, mo, d), running)
            total += running
            low = running if low is None or running < low else low
        s["closing_balance"] = bal
        s["lowest_daily_balance"] = low
        s["average_daily_balance"] = (total / days).quantize(CENT, ROUND_HALF_UP)
        months.append(s)
    return months, issues


def analyze(rows_path, balances_path):
    rows, issues = load_rows(rows_path)
    printed, bal_issues = load_balances(balances_path)
    issues += bal_issues
    if any(i.severity == "error" for i in issues):
        return issues, None
    pairs, t_issues = match_transfers(rows)
    issues += t_issues
    per_account = []
    accounts = sorted({r["account"] for r in rows} | set(printed))
    for a in accounts:
        if a not in printed:
            issues.append(Issue("BSA-009", "error", a, "rows for an account with no printed balances"))
            continue
        m, i = summarize_account(a, [r for r in rows if r["account"] == a], printed[a])
        per_account += m
        issues += i
    if any(i.severity == "error" for i in issues):
        return issues, None

    months = sorted({s["month"] for s in per_account})
    combined = []
    sum_keys = ["all_deposits", "own_transfers_in", "business_deposits", "all_withdrawals", "own_transfers_out",
                "business_withdrawals", "closing_balance", "nsf_overdraft_items", "deposit_count"]
    for m in months:
        ss = [s for s in per_account if s["month"] == m]
        c = {"month": m}
        for k in sum_keys:
            c[k] = sum((s[k] for s in ss), 0 if k in ("nsf_overdraft_items", "deposit_count") else ZERO)
        combined.append(c)
    business = [r for r in rows if r["amount"] > 0 and not r["own"]]
    tot_business = sum((r["amount"] for r in business), ZERO)
    avg_item = (tot_business / len(business)).quantize(CENT, ROUND_HALF_UP) if business else ZERO
    limit = (avg_item * LARGE_MULTIPLE).quantize(CENT, ROUND_HALF_UP)
    large = [r for r in business if r["amount"] >= limit]
    payer_months = {}
    for r in business:
        if r["type"] in ("deposit",):
            payer_months.setdefault(payer(r["description"]), set()).add(r["date"].strftime("%Y-%m"))
    repeat = sorted(p for p, ms in payer_months.items() if len(ms) == len(months))
    tot_own = sum((c["own_transfers_in"] for c in combined), ZERO)
    result = {
        "accounts": accounts,
        "months": months,
        "per_account": per_account,
        "combined": combined,
        "totals": {
            "all_deposits": sum((c["all_deposits"] for c in combined), ZERO),
            "own_transfers_in": tot_own,
            "business_deposits": tot_business,
            "business_withdrawals": sum((c["business_withdrawals"] for c in combined), ZERO),
            "nsf_overdraft_items": sum(c["nsf_overdraft_items"] for c in combined),
            "average_monthly_business_deposits": (tot_business / len(months)).quantize(CENT, ROUND_HALF_UP),
            "overstatement_if_transfers_counted_percent": ((tot_own / tot_business * 100).quantize(Decimal("0.1"), ROUND_HALF_UP)
                                                           if tot_business else ZERO),
        },
        "matched_transfers": [{"from_account": a["account"] if a["amount"] < 0 else b["account"],
                               "to_account": b["account"] if a["amount"] < 0 else a["account"],
                               "amount": abs(a["amount"]), "dates": sorted({a["date"].isoformat(), b["date"].isoformat()})}
                              for a, b in pairs],
        "large_deposits": {"average_business_deposit": avg_item, "threshold": limit,
                           "items": [{"account": r["account"], "date": r["date"].isoformat(), "description": r["description"],
                                      "amount": r["amount"]} for r in large]},
        "repeat_payers": repeat,
    }
    return issues, result


def to_json(obj):
    if isinstance(obj, Decimal):
        return str(obj)
    if isinstance(obj, dict):
        return {k: to_json(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [to_json(v) for v in obj]
    return obj


def write_summary(path, result):
    cols = ["Account", "Month", "All deposits", "Own-account transfers in", "Business deposits", "All withdrawals",
            "Own-account transfers out", "Business withdrawals", "Closing balance", "Lowest daily balance",
            "Average daily balance", "NSF or overdraft items"]
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(cols)
        for s in result["per_account"]:
            w.writerow([s["account"], s["month"]] + [f"{s[k]:.2f}" for k in (
                "all_deposits", "own_transfers_in", "business_deposits", "all_withdrawals", "own_transfers_out",
                "business_withdrawals", "closing_balance", "lowest_daily_balance", "average_daily_balance")] + [s["nsf_overdraft_items"]])
        if len(result["accounts"]) > 1:
            for c in result["combined"]:
                w.writerow(["All accounts", c["month"]] + [f"{c[k]:.2f}" for k in (
                    "all_deposits", "own_transfers_in", "business_deposits", "all_withdrawals", "own_transfers_out",
                    "business_withdrawals", "closing_balance")] + ["", "", c["nsf_overdraft_items"]])


def print_report(result):
    multi = len(result["accounts"]) > 1
    print(f"{'Account':<15}{'Month':<9}{'Deposits':>12}{'Own in':>10}{'Business':>12}{'Withdrawn':>12}{'Own out':>10}"
          f"{'Closing':>11}{'Lowest':>11}{'Avg daily':>11}{'NSF/OD':>7}")
    for s in result["per_account"]:
        print(f"{s['account']:<15}{s['month']:<9}{s['all_deposits']:>12,.2f}{s['own_transfers_in']:>10,.2f}{s['business_deposits']:>12,.2f}"
              f"{s['all_withdrawals']:>12,.2f}{s['own_transfers_out']:>10,.2f}{s['closing_balance']:>11,.2f}"
              f"{s['lowest_daily_balance']:>11,.2f}{s['average_daily_balance']:>11,.2f}{s['nsf_overdraft_items']:>7}")
    if multi:
        print("\nAll accounts together (own transfers drop out of both sides):")
        for c in result["combined"]:
            print(f"  {c['month']}  business deposits {c['business_deposits']:,.2f}, business withdrawals "
                  f"{c['business_withdrawals']:,.2f}, closing {c['closing_balance']:,.2f}, NSF/OD {c['nsf_overdraft_items']}")
    t = result["totals"]
    print(f"\nBusiness deposits {t['business_deposits']:,.2f} over {len(result['months'])} months: "
          f"{t['average_monthly_business_deposits']:,.2f} a month.")
    print(f"Counting own-account transfers as income would overstate deposits by {t['overstatement_if_transfers_counted_percent']}%.")
    if result["matched_transfers"]:
        print("\nOwn-account transfers matched across accounts:")
        for p in result["matched_transfers"]:
            print(f"  {p['amount']:,.2f} {p['from_account']} -> {p['to_account']} ({', '.join(p['dates'])})")
    ld = result["large_deposits"]
    print(f"\nLarge deposits (at least {LARGE_MULTIPLE} x the average business deposit of {ld['average_business_deposit']:,.2f}, "
          f"so {ld['threshold']:,.2f} or more):")
    for r in ld["items"] or [None]:
        print(f"  {r['date']}  {r['account']}  {r['description']}  {r['amount']:,.2f}  (get the source document)" if r else "  none")
    print("\nPayers who deposited every month:")
    for p in result["repeat_payers"] or ["none"]:
        print(f"  {p}")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Check converted statement rows and build a bank statement analysis.")
    ap.add_argument("rows")
    ap.add_argument("balances")
    ap.add_argument("--summary", metavar="CSV", help="write the monthly summary to this file")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    try:
        issues, result = analyze(args.rows, args.balances)
    except ReadError as exc:
        print(f"ERROR   {exc}", file=sys.stderr)
        return 2
    has_error = any(i.severity == "error" for i in issues)
    if result and args.summary:
        write_summary(args.summary, result)
    if args.json:
        print(json.dumps({"ok": not has_error, "issues": [i.as_dict() for i in issues], "analysis": to_json(result)}, indent=2))
    else:
        for i in issues:
            print(i)
        if has_error:
            print("Fix the rows before anyone relies on an analysis. Nothing else was calculated.")
        else:
            if issues:
                print()
            print_report(result)
            if args.summary:
                print(f"\nSummary written to {args.summary}")
    return 1 if has_error else 0


if __name__ == "__main__":
    sys.exit(main())
