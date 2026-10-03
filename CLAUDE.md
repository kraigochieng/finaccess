# finaccess

Hypothetical case study: analysing the FinAccess 2024 (Kenya) household survey to surface financial access and usage gaps for fintech founders. See `README.md` for the goal.

## Data flow

raw xlsx (Google Drive, git-ignored) → `to_parquet.py` → `src/finaccess/finaccess_2024_optimized.parquet` (tracked) → DuckDB queries.

- Download the xlsx with `uv run python scripts/download_data.py`.
- Data file paths come from `finaccess.paths.DATA_DIR`; run modules from the repo root, e.g. `uv run python -m finaccess.exp`.
- `*_variables.csv` is the data dictionary (3,816 variables); `*_values.txt` holds value labels.

## Data gotchas

- Every parquet column is a string. Coded answers are stored as label text (`Male`, `Meru`), not numeric codes, even where the dictionary says the variable is numeric.
- `#NULL!` (not asked / not applicable) appears in 3,025 columns of the all-strings parquet as a literal string, not a real NULL. `None` is a genuine answer label in labelled columns (e.g. `A22i`), not a sentinel.
- Empty strings occur only in text columns (never in the same column as `#NULL!`).
- Cast with `TRY_CAST` before aggregating numeric columns. Do not cast labelled columns to the dictionary types, they would become NULL.
- The csv export of the survey is truncated at 1,024 of 3,816 columns; always use the xlsx or the parquet.
- Git history still contains the old LFS-tracked xlsx and csv; it was deliberately not rewritten.

## Workflow

Issue per task, branch `<type>/<issue>-<description>`, conventional commits, PR with `Closes #N`. Do not merge unless asked.
