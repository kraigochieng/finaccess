import duckdb
import pyarrow.parquet as pq

from finaccess.columns import columns, keys
from finaccess.paths import DATA_DIR

parquet_file_path = DATA_DIR / "finaccess_2024_optimized.parquet"

# parquet_file = pq.ParquetFile("finaccess_2024_optimized.parquet")

# See all column names

# print(f"Metadata: {parquet_file.metadata}")

# all_columns = parquet_file.schema
# print(f"Total columns: {len(all_columns)}")


# print(parquet_file.num_row_groups)
# print(keys + columns["A"])

# df_A = parquet_file.read(columns=keys + columns["A"]).to_pandas()

# print(df_A.head())

# print(parquet_file.schema.names)

# for name, column_names in columns.items():
#     df = parquet_file.read(columns=keys + columns[name]).to_pandas()

#     print(df.head())


con = duckdb.connect(database=":memory:")

result_df = con.execute(
    f"""
    SELECT
        saving_for_education,
        COUNT(*)
    FROM '{parquet_file_path}'
    GROUP BY saving_for_education
    """
).pl()

print(result_df.head())
