# finaccess

Exploring the FinAccess 2024 household survey (Kenya) to find where financial access and usage gaps are, for whom, and in which products.

> **Hypothetical case study.** This is an exercise in turning survey microdata into insight for fintech founders. The outputs are not market advice.

## Goal

Answer questions a fintech founder would ask when choosing where to build, using the latest FinAccess round (2024):

- Who is underserved, and where? (candidate dimensions: county, sex, age group)
- Which products are used, and how does that vary across those dimensions? (savings, credit, insurance, pensions, mobile money, SACCOs, chamas)
- Where is the gap between awareness and usage?

Key metrics and dimensions are still to be chosen; the FinAccess dashboard is the reference for what the survey authors consider headline indicators.

## Pipeline

1. Download the raw xlsx (see below), which holds all 3,816 survey variables
2. `to_parquet.py` converts it to `finaccess_2024_optimized.parquet` (all columns stored as strings, label text for coded values)
3. Analyse the parquet with DuckDB (see `exp.py`)
4. `create_ddl.py` and `values.py` use the data dictionary to produce Postgres DDL and processed value labels


## Getting the data

The raw survey xlsx (294 MB) is not stored in the repo. Download it from Google Drive:

```sh
uv sync
uv run python scripts/download_data.py
```

This saves `src/finaccess/2024_Finaccess_Publicdata.xlsx`. Manual link: https://drive.google.com/file/d/1NGPFK6IGwDpLLQJnrBRyMHiXzUypuZHn/view?usp=sharing

## Notes

pandas was used to create the since llm cannot handle the large csv file

1. preprocess values
2. use variables and preprocessed values to create sql


polars used insead of pandas

ask finaccess to release the data as a parquet file too


show the finaccess questionnaire too: paste the link

identify key metrics and key dimensions relevant to fintech startup founders. look at finaccess dashboard