import polars as pl

from finaccess.csv_to_postgres_types import STATA_TO_POSTGRESQL
from finaccess.paths import DATA_DIR

variables_csv_file = DATA_DIR / "2024_Finaccess_Publicdata_variables.csv"
# values_csv_file = "2024_Finaccess_Publicdata_values_processed.csv"
output_sql = DATA_DIR / "create_finaccess_2024_postgresql.sql"


# Read only header (fast)
variables_df = pl.read_csv(variables_csv_file)




column_name_and_types = []
for name, stata_type in variables_df.select("name", "type").iter_rows():
    column_name_and_types.append(f"{name} {STATA_TO_POSTGRESQL.get(stata_type)}")


sql = f"CREATE TABLE IF NOT EXISTS finaccess_2024 ({','.join(column_name_and_types)});"
# Save
with open(output_sql, "w", encoding="utf-8") as f:
    f.write(sql)

print("PostgreSQL script generated successfully!")
print(f"File saved: {output_sql}")
# print(f"Columns: {len(variables_df.columns)}")
# print("100% compatible with Python 3.11")
