# finaccess

Exploring the FinAccess 2024 household survey (Kenya) to find where financial access and usage gaps are, for whom, and in which products.

> **Hypothetical case study.** This is an exercise in turning survey microdata into insight for fintech founders. The outputs are not market advice.

## Goal

Answer questions a fintech founder would ask when choosing where to build, using the latest FinAccess round (2024):

- Who is underserved, and where? (dimensions: county, sex, age group, education)
- Which products are used, and how does that vary across those dimensions? (savings, credit, insurance, pensions, mobile money, SACCOs, chamas)
- Where is the gap between awareness and usage?

The emphasis is on **gaps**: segments that lag the national picture, and how many adults that represents. A gap is only a niche if it is large enough to build for, so every gap is sized in adults.

## Pipeline

1. Download the raw xlsx (see below), which holds all 3,816 survey variables
2. `to_parquet.py` converts it to `finaccess_2024_optimized.parquet` (all columns stored as strings, label text for coded values)
3. `to_typed_parquet.py` builds `finaccess_2024_typed.parquet`: `#NULL!` becomes NULL and unlabelled numeric columns get real types (labelled and text columns stay strings); `finaccess_2024_typed_report.csv` lists every column's final type
4. Analyse the parquet with DuckDB (see `exp.py`)
5. `metrics.py` computes the weighted share of adults served by each product, overall and by segment; `gaps.py` ranks the lagging segments and products (results in `src/finaccess/results/`)
6. `create_ddl.py` and `values.py` use the data dictionary to produce Postgres DDL and processed value labels


## Finding the gaps

```sh
uv run python -m finaccess.metrics   # results/metrics_by_segment.csv
uv run python -m finaccess.gaps      # results/segment_gaps.csv, results/product_gaps.csv
uv run pytest
```

**Method.** Ten "served" metrics built on the survey's own derived indicators (any access, formal access, mobile money, bank, savings, loan, digital credit, insurance, pension, SACCO). Each is the share of adults (18+) served, weighted with `indWeight`, for all adults and for mobile money users, cut by county, sex, age group and education. `metrics.py` checks the national figures against the 2024 report (formal access 84.8%, excluded 9.9%, 14.8 million bank users) and fails if they drift.

- `gap_pp`: segment share minus national share
- `gap_adults`: adults who would be served if the segment matched the national share. This is the size of the opportunity.
- A segment is a gap if it lags by 5+ points or sits 25%+ below the national share (the relative rule covers low-prevalence products like digital credit). Segments with fewer than 30 sampled adults are flagged and never ranked.

**Product gaps** (adults 18+, 28.1M):

| Product | Served | Unserved adults | Unserved mobile money users |
|---|---|---|---|
| Digital credit | 2.4% | 27.5M | 24.5M |
| SACCO | 11.7% | 24.9M | 21.9M |
| Pension | 11.8% | 24.8M | 21.9M |
| Insurance (incl. NHIF) | 22.0% | 22.0M | 19.0M |
| Bank | 52.5% | 13.4M | 10.7M |
| Loan | 64.0% | 10.1M | 8.0M |
| Savings | 68.1% | 9.0M | 6.9M |
| Mobile money access | 89.2% | 3.0M | 0 |

Mobile money is close to universal, yet most mobile money users have no digital credit, insurance or pension. That is the adjacent gap: the rail exists, the product does not.

**Largest lagging segments** (all adults, by `gap_adults`):

- Ages 18-25: formal access 69.0% (about 1.2M adults short of the national share), loans 50.3%, insurance 10.6%
- Adults with no formal education: bank 18.5%, savings 38.3% (about 0.9M and 0.8M short)
- Women: bank 46.5%, insurance 16.1%, pension 7.7% (0.6-0.9M short each)
- Counties: formal access in West Pokot (48.5%) and Turkana (65.9%); insurance in Kitui (8.6%) and Kakamega (13.8%)

Read `segment_gaps.csv` for the full ranking, including the mobile-money-user cut.

**Limits.**
- Descriptive, not causal. Young adults lag on loans and insurance partly because of life stage, so a gap is not automatically an opportunity.
- No design-based standard errors: weights are applied but survey strata and clusters are not. County estimates rest on roughly 350-550 interviews each, so treat small differences between counties with caution.
- No urban/rural variable in the public data.
- One survey round, so no trends. The "served" definitions are the survey's derived indicators, not ours.

## Getting the data

The raw survey xlsx (294 MB) is not stored in the repo. Download it from Google Drive:

```sh
uv sync
uv run python scripts/download_data.py
```

This saves `src/finaccess/2024_Finaccess_Publicdata.xlsx`. Manual link: https://drive.google.com/file/d/1NGPFK6IGwDpLLQJnrBRyMHiXzUypuZHn/view?usp=sharing

## Notes

pandas was used to create the since llm cannot handle the large csv file

new code uses polars rather than pandas

1. preprocess values
2. use variables and preprocessed values to create sql


polars used insead of pandas

ask finaccess to release the data as a parquet file too


show the finaccess questionnaire too: paste the link

identify key metrics and key dimensions relevant to fintech startup founders. look at finaccess dashboard