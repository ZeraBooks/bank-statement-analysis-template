# Bank statement analysis template

Bank statement analysis turns months of statement rows into the figures a lender, court or auditor asks for: deposits after taking out transfers between your own accounts, withdrawals, month-end, lowest and average daily balances, NSF and overdraft items, large deposits and the payers who come back every month. It starts with every statement in one spreadsheet, which [ZeraBooks Convert](https://www.zerabooks.com/bank-statement-analysis) produces and checks against each printed balance. This repo defines the layout and builds the analysis from it.

What's here:

- A spec for the input rows, the printed balances and every metric, with JSON Schemas ([`SPEC.md`](SPEC.md), [`schema/`](schema/))
- Eleven rules with IDs ([`rules/analysis-rules.csv`](rules/analysis-rules.csv))
- A checker that proves every month against its printed balances, matches own-account transfers across accounts, and only then builds the analysis per account and for all accounts together ([`cli/analysis_check.py`](cli/analysis_check.py))
- Two fictional businesses and nine broken samples that each fail one rule ([`samples/`](samples/))
- The summary template and the original single-account `analyze_statements.py`, unchanged

Python 3.8+, standard library only. Download everything from the [latest release](https://github.com/ZeraBooks/bank-statement-analysis-template/releases/latest).

## Why analyze every account, not just the main one?

Because money moved between the owner's own accounts looks like income on one statement and like spending on the other. With only the checking account, you can't tell a transfer from savings apart from a customer payment. With every account in the file, each transfer has to show up twice, once out and once in, and both sides drop out of the totals.

```bash
python3 cli/analysis_check.py samples/orchard-row-physio/rows.csv samples/orchard-row-physio/balances.csv
```

```
WARNING BSA-011 Checking 6120 2026-06-15: Transfer 1800.00 (ONLINE TRANSFER FROM XX4471) isn't tagged, so it counts as business money. ...

All accounts together (own transfers drop out of both sides):
  2026-04  business deposits 24,973.87, business withdrawals 26,750.80, closing 40,673.07, NSF/OD 0
  2026-05  business deposits 25,114.42, business withdrawals 28,735.35, closing 37,052.14, NSF/OD 0
  2026-06  business deposits 38,194.05, business withdrawals 27,035.60, closing 48,210.59, NSF/OD 0

Business deposits 88,282.34 over 3 months: 29,427.45 a month.
Counting own-account transfers as income would overstate deposits by 17.6%.

Own-account transfers matched across accounts:
  4,000.00 Checking 6120 -> Savings 6138 (2026-04-10)
  2,500.00 Savings 6138 -> Checking 6120 (2026-05-20)
  9,000.00 Savings 6138 -> Checking 6120 (2026-06-02, 2026-06-03)
```

## Example 1: two accounts, April to June 2026

Orchard Row Physical Therapy is a fictional clinic with a checking account and a savings account. A lender asked for three months of statements for every account. Checking:

| Month | Opening | Deposits | Own transfers in | Business deposits | Withdrawals | Closing |
|---|---|---|---|---|---|---|
| April | 12,450.00 | 24,970.75 | 0.00 | 24,970.75 | 30,750.80 | 6,669.95 |
| May | 6,669.95 | 27,611.15 | 2,500.00 | 25,111.15 | 28,735.35 | 5,545.75 |
| June | 5,545.75 | 47,191.00 | 9,000.00 | 38,191.00 | 27,035.60 | 25,701.15 |

Each month ties: 12,450.00 + 24,970.75 - 30,750.80 = 6,669.95, then 6,669.95 + 27,611.15 - 28,735.35 = 5,545.75, then 5,545.75 + 47,191.00 - 27,035.60 = 25,701.15. April's withdrawals include the 4,000.00 moved to savings.

What the analysis shows that the checking statement alone doesn't:

- **15,500.00 of deposits were the owner's own money moving.** 4,000.00 went to savings in April, 2,500.00 came back in May and 9,000.00 in June. Each one is matched to its other side on the savings statement. Counted as income, they would overstate deposits by 15,500.00 / 88,282.34 = 17.6%.
- **June's lowest balance was 495.75, and only because of savings.** June 3 started at 1,345.75 after rent. Payroll of 9,850.00 went out the same day the 9,000.00 came in from savings. Without that move, checking would have hit 1,345.75 - 9,850.00 = -8,504.25. A lender reads that as a business leaning on its reserves.
- **One large deposit.** The average business deposit is 88,282.34 / 20 = 4,414.12, so anything from 8,828.24 up is flagged. That catches the 11,200.00 from Lakeview School District on June 19 and nothing else. Expect a request for the contract behind it.
- **One transfer nobody tagged.** 1,800.00 came in on June 15 from an account ending 4471 that isn't in the file. It counts as business money for now. If it's the owner's personal account, business deposits drop to 88,282.34 - 1,800.00 = 86,482.34.
- **Repeat payers.** Meridian Health Plan, Square card settlements and the State Workers Comp Fund deposited in every one of the three months. Savings interest is income but doesn't count as a repeat payer.

All accounts together, the clinic closed June with 25,701.15 + 22,509.44 = 48,210.59.

## Example 2: the original single account

Fernhill Landscaping is a fictional company applying for an equipment loan with its July to September 2026 checking statements. July opens at 8,530.00.

| Month | All deposits | Own-account transfers in | Business deposits | Withdrawals | Closing balance | NSF or overdraft items |
|---|---|---|---|---|---|---|
| July | 48,300.00 | 5,000.00 | 43,300.00 | 46,950.00 | 9,880.00 | 0 |
| August | 41,750.00 | 0.00 | 41,750.00 | 47,210.00 | 4,420.00 | 2 |
| September | 52,600.00 | 8,000.00 | 44,600.00 | 50,135.40 | 6,884.60 | 1 |
| **Three months** | **142,650.00** | **13,000.00** | **129,650.00** | **144,295.40** | | **3** |

Average monthly business deposits are 43,216.67. Each closing follows from the one before: 8,530.00 + 48,300.00 - 46,950.00 = 9,880.00, then 4,420.00 and 6,884.60, matching the printed statements. The 13,000.00 moved from savings would overstate deposits by 10.0%. August has a returned check (NSF fee on August 10) and an overdraft fee on August 21. September has one overdraft fee on September 9. The lowest daily balances were -2,510.00 in August and -1,705.00 in September. One large deposit: 14,500.00 from Westbrook School District on September 18.

Here the savings account wasn't converted, so the checker can't match the two transfers. It still runs, with a BSA-010 warning for each: convert the savings statements too.

## What the checker refuses to do

It won't print an analysis from rows that don't add up. If any month's opening plus its rows misses the printed closing, the output stops at the error:

```bash
python3 cli/analysis_check.py samples/invalid/row-dropped/rows.csv samples/invalid/row-dropped/balances.csv
```

```
WARNING BSA-011 Checking 6120 2026-06-15: Transfer 1800.00 (ONLINE TRANSFER FROM XX4471) isn't tagged, ...
ERROR   BSA-007 Checking 6120 2026-04: opening 12450.00 + rows -4134.25 = 8315.75, but the statement prints 6669.95 (off by +1645.80). A row is missing, doubled or has the wrong sign
Fix the rows before anyone relies on an analysis. Nothing else was calculated.
```

The 1,645.80 is the April medical supply payment, dropped at a page break. An analysis built without it would show April's withdrawals 1,645.80 too low and every daily balance after April 27 too high.

## The input layout

`rows.csv`, one row per transaction, any number of accounts of the same owner:

| Column | Format |
|---|---|
| Account | Name and last four digits, e.g. `Checking 6120` |
| Date | `YYYY-MM-DD` |
| Description | As printed |
| Type | `Deposit`, `Withdrawal`, `Fee`, `Check`, `Interest` or `Transfer` |
| Amount | Signed: money in positive, money out negative, two decimals |
| Own transfer | `Yes` for money moved between the owner's accounts, else blank |

`balances.csv`, one row per account per month: `Account, Month, Printed opening, Printed closing`, copied from each statement.

Every metric (business deposits, lowest daily balance, the large-deposit threshold, repeat payers) is defined in [`SPEC.md`](SPEC.md).

## Run it

```bash
python3 cli/analysis_check.py rows.csv balances.csv                       # report
python3 cli/analysis_check.py rows.csv balances.csv --summary summary.csv # monthly CSV
python3 cli/analysis_check.py rows.csv balances.csv --json                # for scripts
```

Exit codes: 0 no errors, 1 errors, 2 a file can't be read.

## Getting the rows from PDF statements

![ZeraBooks Convert with two accounts from one statement proven against their printed balances, and a Type column marking a transfer](https://zerabooks.github.io/images/app/convert-two-accounts-proven.png)

Download every statement the reader asked for as a PDF, for every account. Upload them to ZeraBooks Convert. Each account is checked against its printed opening and closing balances, the Type column comes from the section each row was printed in (including Transfer and Fee), and you can download all the statements together in one file with an Account column. That file is this repo's `rows.csv` once you tag the own transfers.

ZeraBooks Convert converts and proves statements. It doesn't score applicants or flag NSF items for you; that's what this repo's checker and your own review are for. Convert comes with the ZeraBooks subscription: 1,000 pages a month for $79 a month billed annually or $149 month to month, after a 7-day trial. There is no bank connection. The statements are uploaded as PDFs.

## FAQ

### Why take out transfers between your own accounts?

Money moved from savings to checking is not new income. Counted as a deposit, it makes the business look bigger than it is, and an underwriter will find it anyway by matching it to the savings statement.

### Why check the printed balances before analyzing?

An analysis is only as good as its rows. When every month adds up from its printed opening balance to its printed closing balance, nobody can say a page or a transaction was left out.

### How is the lowest daily balance worked out?

From the rows: each day's balance is the balance after its last transaction, carried forward through days with none. If the statement prints a daily balance section, check against it.

### How many months of statements does a lender want?

It depends on the loan or the case. Ask for the list in writing before you download anything, and include every account, not just the main one.

## Run the tests

```bash
python3 scripts/generate_samples.py
python3 scripts/build_manifest.py
python3 -m unittest discover -s tests -v
```

`MANIFEST.json` lists every sample, schema and rules file with its size, row count and SHA-256. Check them with `shasum -a 256 -c checksums.txt`.

## Learn more

Full guide: [Bank statement analysis](https://www.zerabooks.com/bank-statement-analysis). Related: [ZeraBooks bank statement converter](https://www.zerabooks.com/bank-statement-converter) and [proof of cash](https://www.zerabooks.com/proof-of-cash).

## License and citation

The content and data in this repository are licensed under [CC BY 4.0](LICENSE). The code (`*.py`) is licensed under [MIT](LICENSE-CODE). Cite it with [`CITATION.cff`](CITATION.cff) or as: ZeraBooks, *Bank Statement Analysis Template*, v1.1.0, 2026, https://github.com/ZeraBooks/bank-statement-analysis-template.

ZeraBooks is an AI-native general ledger, bank statement converter and done-for-you bookkeeping service for small businesses and accounting firms. Maintained by [ZeraBooks](https://www.zerabooks.com).
