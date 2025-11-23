# import pandas as pd
import polars as pl

# df = pd.read_excel("2024_Finaccess_Publicdata.xlsx", engine="calamine", sheet_name=0,nrows=0)
# df = pl.read_excel(
#     source="2024_Finaccess_Publicdata.xlsx", sheet_id=1,
# )

reader = pl.read_csv_batched(
    source="2024_Finaccess_Publicdata.csv", n_rows=1_000_000, null_values=["#NULL!"]
)

batches = reader.next_batches(50)

for i, df_batch in enumerate(batches):
    print(f"Batch {i + 1} data:")
    print(df_batch)
    print("-" * 30)

# # TODO: batch read
# print(df.head(2))
