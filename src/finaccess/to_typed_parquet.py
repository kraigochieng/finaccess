"""Build a typed parquet from the all-strings parquet.

Rules, applied per column:
- "#NULL!" (not asked / not applicable) becomes a real NULL in every column.
  Empty strings are left alone: they only occur in text columns, never in the
  same column as "#NULL!", so the two kinds of missing stay distinguishable.
- Unlabelled numeric columns are cast to their dictionary type when every
  non-sentinel value casts; otherwise they stay strings.
- Labelled columns hold label text, not codes, so they stay strings.
- Text columns stay strings.
"""

import logging

import duckdb
import pandas as pd
import pyarrow.parquet as pq

from finaccess.logging_config import setup_logging
from finaccess.paths import DATA_DIR

setup_logging()

logger = logging.getLogger(__name__)

SOURCE = DATA_DIR / "finaccess_2024_optimized.parquet"
VARIABLES = DATA_DIR / "2024_Finaccess_Publicdata_variables.csv"
TARGET = DATA_DIR / "finaccess_2024_typed.parquet"
REPORT = DATA_DIR / "finaccess_2024_typed_report.csv"

NOT_ASKED = "#NULL!"
KEY = "interview__id"
BATCH = 100

# Stata type -> DuckDB type
NUMERIC_TYPES = {
    "byte": "TINYINT",
    "int": "SMALLINT",
    "long": "INTEGER",
    "double": "DOUBLE",
}


def quote(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def batches(items: list[str]):
    for i in range(0, len(items), BATCH):
        yield items[i : i + BATCH]


def plan_columns(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Decide the target type of every column and count its NULL markers."""
    columns = pq.ParquetFile(SOURCE).schema.names
    variables = pd.read_csv(VARIABLES).set_index("name")

    missing = set(columns) - set(variables.index)
    if missing:
        raise SystemExit(f"Columns missing from the dictionary: {sorted(missing)[:5]}")

    rows = []
    for name in columns:
        var = variables.loc[name]
        labelled = pd.notna(var["vallab"])
        if var["isnumeric"] == 1 and not labelled and var["type"] in NUMERIC_TYPES:
            status, target = "cast_candidate", NUMERIC_TYPES[var["type"]]
        elif labelled:
            status, target = "kept_string_labelled", "VARCHAR"
        elif var["isnumeric"] == 1:
            status, target = "kept_string_unsupported_type", "VARCHAR"
        else:
            status, target = "kept_string_text", "VARCHAR"
        rows.append(
            {
                "name": name,
                "dictionary_type": var["type"],
                "status": status,
                "target_type": target,
            }
        )
    plan = pd.DataFrame(rows).set_index("name")
    plan["not_asked_count"] = 0
    plan["cast_failures"] = 0

    for batch in batches(columns):
        select = []
        for name in batch:
            col = quote(name)
            select.append(f"COUNT(*) FILTER (WHERE {col} = '{NOT_ASKED}')")
            if plan.at[name, "status"] == "cast_candidate":
                target = plan.at[name, "target_type"]
                select.append(
                    f"COUNT(*) FILTER (WHERE {col} <> '{NOT_ASKED}' "
                    f"AND TRY_CAST({col} AS {target}) IS NULL)"
                )
        result = iter(con.execute(f"SELECT {','.join(select)} FROM '{SOURCE}'").fetchone())
        for name in batch:
            plan.at[name, "not_asked_count"] = next(result)
            if plan.at[name, "status"] == "cast_candidate":
                plan.at[name, "cast_failures"] = next(result)
        logger.info("Planned %s/%s columns", batch_end(batch, columns), len(columns))

    # A candidate only becomes a cast when every non-sentinel value casts
    is_candidate = plan["status"] == "cast_candidate"
    plan.loc[is_candidate & (plan["cast_failures"] == 0), "status"] = "cast"
    failed = is_candidate & (plan["cast_failures"] > 0)
    plan.loc[failed, "status"] = "kept_string_cast_failed"
    plan.loc[failed, "target_type"] = "VARCHAR"
    return plan


def batch_end(batch: list[str], columns: list[str]) -> int:
    return columns.index(batch[-1]) + 1


def select_expression(name: str, plan: pd.DataFrame) -> str:
    col = quote(name)
    value = f"NULLIF({col}, '{NOT_ASKED}')"
    if plan.at[name, "status"] == "cast":
        value = f"TRY_CAST({value} AS {plan.at[name, 'target_type']})"
    return f"{value} AS {col}"


def write_typed(con: duckdb.DuckDBPyConnection, plan: pd.DataFrame) -> None:
    select = ",\n    ".join(select_expression(name, plan) for name in plan.index)
    if TARGET.exists():
        TARGET.unlink()
    con.execute(
        f"COPY (SELECT\n    {select}\nFROM '{SOURCE}') "
        f"TO '{TARGET}' (FORMAT PARQUET, COMPRESSION ZSTD)"
    )


def verify(con: duckdb.DuckDBPyConnection, plan: pd.DataFrame) -> None:
    """Check every value survived and NULLs match the sentinel exactly."""
    source_rows = con.execute(f"SELECT COUNT(*) FROM '{SOURCE}'").fetchone()[0]
    target_rows = con.execute(f"SELECT COUNT(*) FROM '{TARGET}'").fetchone()[0]
    if source_rows != target_rows:
        raise SystemExit(f"Row count changed: {source_rows} -> {target_rows}")
    if pq.ParquetFile(TARGET).schema.names != list(plan.index):
        raise SystemExit("Column names or order changed")

    bad = {}
    for batch in batches(list(plan.index)):
        select = []
        for name in batch:
            col = quote(name)
            if plan.at[name, "status"] == "cast":
                same = f"CAST(t.{col} AS DOUBLE) = TRY_CAST(s.{col} AS DOUBLE)"
            else:
                same = f"t.{col} = s.{col}"
            select.append(
                f"COUNT(*) FILTER (WHERE NOT (CASE WHEN s.{col} = '{NOT_ASKED}' "
                f"THEN t.{col} IS NULL ELSE (t.{col} IS NOT NULL AND {same}) END))"
            )
        result = con.execute(
            f"SELECT {','.join(select)} FROM '{SOURCE}' s "
            f"JOIN '{TARGET}' t USING ({quote(KEY)})"
        ).fetchone()
        bad.update({name: n for name, n in zip(batch, result) if n})

    if bad:
        raise SystemExit(f"Verification failed for {len(bad)} columns: {list(bad)[:5]}")
    logger.info("Verified %s columns across %s rows", len(plan), target_rows)


def main() -> None:
    con = duckdb.connect()
    con.execute("SET threads=2; SET memory_limit='4GB'")

    plan = plan_columns(con)
    write_typed(con, plan)
    verify(con, plan)

    plan.reset_index().to_csv(REPORT, index=False)
    logger.info("Status counts:\n%s", plan["status"].value_counts().to_string())
    logger.info("Wrote %s (%.1f MB) and %s", TARGET.name, TARGET.stat().st_size / 1e6, REPORT.name)


if __name__ == "__main__":
    main()
