# Bank statement analysis template

Bank statement analysis turns months of statement rows into the figures a
lender, court or auditor asks for: deposits after taking out transfers between
your own accounts, withdrawals, month-end, lowest and average daily balances,
NSF and overdraft items, large deposits and the payers who come back every
month. This repo has a summary template, a fictional three-month sample, and a
script that builds the summary from converted statement rows and checks each
month against the printed balances first.

## Files

| File | What it is |
|---|---|
| `analysis-summary-template.csv` | The summary layout, one row per month plus a total. Fill it by hand or let the script write it. |
| `converted-statements-jul-sep-2026.csv` | A fictional landscaping company's checking account, July to September 2026, one row per transaction. Columns: Account, Date, Description, Type, Amount, Own transfer. |
| `statement-balances.csv` | The opening and closing balance printed on each month's statement. |
| `analyze_statements.py` | Checks the rows against the printed balances, then prints the monthly summary, own-account transfers, untagged transfers, large deposits and repeat payers. |
| `summary-jul-sep-2026.csv` | What the script writes for the sample. |

The script is Python 3, standard library only.

## How to use it

1. Download every statement the reader asked for as PDF, for every account.
   The PDF carries the printed opening and closing balance that proves no page
   or month is missing.
2. Convert the statements to rows in the shape of
   `converted-statements-jul-sep-2026.csv`, and put each month's printed
   opening and closing in `statement-balances.csv`.
3. Tag transfers between the same owner's accounts with `Yes` in the Own
   transfer column. Convert the other account's statements too, so each
   transfer can be matched to its other side.
4. Run:

   ```
   python3 analyze_statements.py converted-statements-jul-sep-2026.csv statement-balances.csv summary.csv
   ```

   If a month's rows don't reach the printed closing balance, the script says
   so. Fix that before anyone relies on the summary.

Lowest and average daily balances are worked out from the rows and the
opening balance, using each day's end-of-day balance. If the statement has a
daily balance section, check them against it.

## The worked example

Fernhill Landscaping is a fictional company applying for an equipment loan
with its July to September 2026 checking statements. July opens at 8,530.00.

| Month | All deposits | Own-account transfers in | Business deposits | Withdrawals | Closing balance | NSF or overdraft items |
|---|---|---|---|---|---|---|
| July | 48,300.00 | 5,000.00 | 43,300.00 | 46,950.00 | 9,880.00 | 0 |
| August | 41,750.00 | 0.00 | 41,750.00 | 47,210.00 | 4,420.00 | 2 |
| September | 52,600.00 | 8,000.00 | 44,600.00 | 50,135.40 | 6,884.60 | 1 |
| **Three months** | **142,650.00** | **13,000.00** | **129,650.00** | **144,295.40** | | **3** |

Average monthly business deposits are 43,216.67. Each closing follows from the
one before: 8,530.00 + 48,300.00 - 46,950.00 = 9,880.00, then 4,420.00 and
6,884.60, matching the printed statements.

What the script also finds:

- The 13,000.00 moved from savings would overstate deposits by 10.0% if it
  were counted as income.
- August has a returned check (NSF fee on August 10) and an overdraft fee on
  August 21. September has one overdraft fee on September 9. The lowest daily
  balances were -2,510.00 in August and -1,705.00 in September.
- One large deposit: 14,500.00 from Westbrook School District on September 18,
  about twice the average business deposit of 7,202.78. A lender will ask for
  the contract or invoice behind it.
- Cedar Ridge Apartments, Hartley HOA and the card settlements came in every
  month. That steady repeat income reads very differently from one big job.

The company, payers and figures are fictional.

## FAQ

### Why take out transfers between your own accounts?

Money moved from savings to checking is not new income. Counted as a deposit,
it makes the business look bigger than it is, and an underwriter will find it
anyway by matching it to the savings statement.

### Why check the printed balances before analyzing?

An analysis is only as good as its rows. When every month adds up from its
printed opening balance to its printed closing balance, nobody can say a page
or a transaction was left out.

### How many months of statements does a lender want?

It depends on the loan or the case. Ask for the list in writing before you
download anything, and include every account, not just the main one.

## Learn more

Full guide: [Bank statement analysis](https://www.zerabooks.com/bank-statement-analysis). Related: [ZeraBooks bank statement converter](https://www.zerabooks.com/bank-statement-converter).

## License

The content and data in this repository are licensed under
[CC BY 4.0](LICENSE). Free to use and adapt with credit to ZeraBooks.
The code (`*.py`) is licensed under [MIT](LICENSE-CODE).

Maintained by [ZeraBooks](https://www.zerabooks.com).
