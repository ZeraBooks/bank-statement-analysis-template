# Bank statement analysis spec, v1.1.0

This spec defines the two input files for a bank statement analysis, the checks they must pass before any figure is trusted, and how each figure is worked out. `cli/analysis_check.py` implements it. Rule IDs are in `rules/analysis-rules.csv`. JSON Schemas: `schema/statement-row.schema.json`, `schema/statement-balances.schema.json` (inputs) and `schema/analysis-summary.schema.json` (the `--json` output).

## Inputs

Both files: UTF-8, comma separated, one header row with exactly these columns (BSA-001).

### rows.csv

One row per transaction. Any number of accounts, all held by the same owner.

| Column | Format | Rule |
|---|---|---|
| Account | Name and last four digits | |
| Date | `YYYY-MM-DD` | BSA-002 |
| Description | Text as printed | |
| Type | `Deposit`, `Withdrawal`, `Fee`, `Check`, `Interest`, `Transfer` | BSA-003 |
| Amount | Signed, two decimals, no `$` or thousands comma | BSA-004 |
| Own transfer | `Yes` or blank | BSA-006 |

Sign by type (BSA-005): Deposit and Interest are positive. Withdrawal, Fee and Check are negative. Transfer can be either. Zero amounts are not allowed.

### balances.csv

One row per account per statement month: `Account, Month (YYYY-MM), Printed opening, Printed closing`, copied from the statement.

## Checks before any figure (errors stop the analysis)

For each account and each month M:

```
BSA-007   printed opening(M) + sum(Amount of rows in M) = printed closing(M)
BSA-008   printed opening(M) = printed closing(M - 1)
BSA-009   balances exist for every month from the account's first to its last,
          and every row falls in a month that has balances
```

Own-account transfers (BSA-010). Each row with Own transfer = Yes is paired with a row in a different account that has the opposite amount, also tagged Yes, dated within 3 days. Each row is used in one pair at most. An unpaired row is an error when the file has more than one account. With a single account it is a warning, because the other side can't be in the file.

Untagged transfers (BSA-011, warning). A Transfer row without Own transfer = Yes counts as outside money.

## Figures

All amounts are exact to the cent. Rounding is half up, and only where a figure is a division.

Per account, per month:

| Figure | Definition |
|---|---|
| All deposits | Sum of positive amounts |
| Own transfers in | Sum of positive amounts tagged Own transfer |
| Business deposits | All deposits - own transfers in |
| All withdrawals | Sum of negative amounts, as a positive number |
| Own transfers out | Sum of negative amounts tagged Own transfer, as a positive number |
| Business withdrawals | All withdrawals - own transfers out |
| Closing balance | Printed opening + sum of amounts (equals the printed closing once BSA-007 passes) |
| Lowest daily balance | Lowest end-of-day balance in the month. A day with no rows carries the previous day's balance. Day 1 with no rows carries the opening |
| Average daily balance | Sum of end-of-day balances / days in the month |
| NSF or overdraft items | Count of Fee rows whose description contains NSF, RETURNED ITEM or OVERDRAFT |

All accounts together, per month: the sum of each figure across accounts. Own transfers in and out cancel, so business deposits and business withdrawals are what came from and went to the outside world.

Across the whole period:

| Figure | Definition |
|---|---|
| Average monthly business deposits | Total business deposits / number of months |
| Overstatement if transfers counted | Own transfers in / business deposits x 100, to one decimal |
| Average business deposit | Total business deposits / number of business deposit rows |
| Large deposit threshold | 2 x average business deposit. Every business deposit at or above it is listed |
| Repeat payers | Deposit rows (not Interest) grouped by payer, kept when the payer deposited in every month. The payer is the description minus a leading `ACH CREDIT`, `MOBILE DEPOSIT`, `CARD SETTLEMENT` or `DEPOSIT` |

## Output

Text by default. `--summary FILE` writes one CSV row per account per month, plus `All accounts` rows when there is more than one account. `--json` prints `{"ok", "issues", "analysis"}`, where `analysis` is null when there are errors and otherwise follows `schema/analysis-summary.schema.json`. Money in the JSON is a string with two decimals.

Exit codes: 0 no errors, 1 errors, 2 a file can't be read.

## Versioning

Semantic versioning. A new figure or a new warning is a minor version. A change that makes old valid files fail, or changes a figure's definition, is a major version. See `CHANGELOG.md`.
