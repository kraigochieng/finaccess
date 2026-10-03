# finaccess

Hypothetical case study: analysing the FinAccess 2024 (Kenya) household survey to surface financial access and usage gaps for fintech founders. See `README.md` for the goal.

## Data flow

raw xlsx (Google Drive, git-ignored) → `to_parquet.py` → `src/finaccess/finaccess_2024_optimized.parquet` (tracked) → DuckDB queries.

`to_typed_parquet.py` then builds `finaccess_2024_typed.parquet` (real NULLs, numeric columns cast) and `finaccess_2024_typed_report.csv` (per-column type and status). Prefer the typed file for analysis; the all-strings file is the reference copy.

- Download the xlsx with `uv run python scripts/download_data.py`.
- `metrics.py` and `gaps.py` produce weighted shares and ranked gaps in `src/finaccess/results/`. Adults are 18+ (the survey also interviewed 16-17 year olds) and weights are `indWeight`; `metrics.py` fails if national figures drift from the 2024 report. Without the 18+ filter figures are about 6 points off.
- Use polars, not pandas (pandas is not a dependency). Run tests with `uv run pytest`.
- `None` is a real education segment; avoid readers that parse it as a missing value (pandas does by default, polars does not).
- Data file paths come from `finaccess.paths.DATA_DIR`; run modules from the repo root, e.g. `uv run python -m finaccess.exp`.
- `*_variables.csv` is the data dictionary (3,816 variables); `*_values.txt` holds value labels.
- `niches.py` picks one niche per product by rule (largest `gap_adults` segment) and attaches the top two barriers; segments overlap, so niche sizes must not be summed.
- `barriers.py` analyses reasons for non-use. The reason flags are 0/1 and asked only of non-users, so the base is non-null rows. `share_of_mentions` (the report's measure) differs from `share_citing` (share of people, multi-response).

## Data gotchas

- Every parquet column is a string. Coded answers are stored as label text (`Male`, `Meru`), not numeric codes, even where the dictionary says the variable is numeric.
- `#NULL!` (not asked / not applicable) appears in 3,025 columns of the all-strings parquet as a literal string, not a real NULL. `None` is a genuine answer label in labelled columns (e.g. `A22i`), not a sentinel.
- Empty strings occur only in text columns (never in the same column as `#NULL!`).
- In the all-strings file, cast with `TRY_CAST` before aggregating numeric columns. Do not cast labelled columns to the dictionary types, they would become NULL; the typed file keeps them as strings.
- The csv export of the survey is truncated at 1,024 of 3,816 columns; always use the xlsx or the parquet.
- Git history still contains the old LFS-tracked xlsx and csv; it was deliberately not rewritten.

## Workflow

Issue per task, branch `<type>/<issue>-<description>`, conventional commits, PR with `Closes #N`. Do not merge unless asked.
