# Changelog

## 1.1.0 (2026-11-06)

- `SPEC.md`: input layouts, the checks that must pass before any figure, and the definition of every figure.
- JSON Schemas for the rows, the printed balances and the `--json` output in `schema/`.
- Eleven rules with IDs in `rules/analysis-rules.csv`.
- `cli/analysis_check.py`: any number of accounts, own-account transfers matched across accounts, per-account and all-accounts figures, refuses to analyze rows that don't tie, `--summary`, `--json`.
- Samples: Orchard Row Physical Therapy (two accounts, three matched transfers, one untagged), Fernhill Landscaping (the original example) and nine invalid samples with `expected.json`.
- `scripts/generate_samples.py`, tests, CI, `MANIFEST.json`, `checksums.txt` and a release zip.
- The template, root sample files and `analyze_statements.py` are unchanged.

## 1.0.0 (2026-11-04)

- Summary template, the Fernhill Landscaping sample and `analyze_statements.py`.
