import pyarrow.parquet as pq
from finaccess.columns import columns, keys

parquet_file = pq.ParquetFile("finaccess_2024_optimized.parquet")

# See all column names


print(f"Metadata: {parquet_file.metadata}")

all_columns = parquet_file.schema
print(f"Total columns: {len(all_columns)}")


print(parquet_file.num_row_groups)
# print(keys + columns["A"])

df_A = parquet_file.read(columns=keys + columns["A"]).to_pandas()

# print(df_A.head())

# print(parquet_file.schema.names)

for name, column_names in columns.items():
    df = parquet_file.read(columns=keys + columns[name]).to_pandas()

    print(df.head())
