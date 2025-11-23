import pandas as pd

from finaccess.csv_to_postgres_types import STATA_TO_POSTGRESQL

variables_csv_file = "2024_Finaccess_Publicdata_variables.csv"
# values_csv_file = "2024_Finaccess_Publicdata_values_processed.csv"
output_sql = "create_finaccess_2024_postgresql.sql"


# Read only header (fast)
variables_df = pd.read_csv(variables_csv_file)




column_name_and_types = []
for index, row in variables_df.iterrows():
    column_name_and_types.append(
        f"{row['name']} {STATA_TO_POSTGRESQL.get(row['type'])}"
    )


sql = f"CREATE TABLE IF NOT EXISTS finaccess_2024 ({','.join(column_name_and_types)});"
# Save
with open(output_sql, "w", encoding="utf-8") as f:
    f.write(sql)

print("PostgreSQL script generated successfully!")
print(f"File saved: {output_sql}")
# print(f"Columns: {len(variables_df.columns)}")
# print("100% compatible with Python 3.11")
