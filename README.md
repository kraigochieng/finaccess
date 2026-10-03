# finaccess (in development, this readme will be a braindump and will be organised as the proect continues)

## Getting the data

The raw survey csv (142 MB) is not stored in the repo. Download it from Google Drive:

```sh
uv sync
uv run python scripts/download_data.py
```

This saves `src/finaccess/2024_Finaccess_Publicdata.csv`. Manual link: https://drive.google.com/file/d/1f0lc2OBkJpWX3FUJr21xn6CLbbY7Pk_k/view?usp=sharing

## Notes

pandas was used to create the since llm cannot handle the large csv file

1. preprocess values
2. use variables and preprocessed values to create sql


polars used insead of pandas

ask finaccess to release the data as a parquet file too


show the finaccess questionnaire too: paste the link

identify key metrics and key dimensions relevant to fintech startup founders. look at finaccess dashboard