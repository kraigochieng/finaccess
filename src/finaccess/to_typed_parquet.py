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
import polars as pl
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


def batches(items: list):
    for i in range(0, len(items), BATCH):
        yield items[i : i + BATCH]


def classify(var: dict) -> tuple[str, str]:
    """Initial status and target type of a column from its dictionary entry."""
    labelled = var["vallab"] is not None
    if var["isnumeric"] == 1 and not labelled and var["type"] in NUMERIC_TYPES:
        return "cast_candidate", NUMERIC_TYPES[var["type"]]
    if labelled:
        return "kept_string_labelled", "VARCHAR"
    if var["isnumeric"] == 1:
        return "kept_string_unsupported_type", "VARCHAR"
    return "kept_string_text", "VARCHAR"


def resolve(column: dict) -> None:
    """A candidate only becomes a cast when every non-sentinel value casts."""
    if column["status"] != "cast_candidate":
        return
    if column["cast_failures"] == 0:
        column["status"] = "cast"
    else:
        column["status"] = "kept_string_cast_failed"
        column["target_type"] = "VARCHAR"


def plan_columns(con: duckdb.DuckDBPyConnection) -> pl.DataFrame:
    """Decide the target type of every column and count its NULL markers."""
    names = pq.ParquetFile(SOURCE).schema.names
    variables = {row["name"]: row for row in pl.read_csv(VARIABLES).iter_rows(named=True)}

    missing = set(names) - set(variables)
    if missing:
        raise SystemExit(f"Columns missing from the dictionary: {sorted(missing)[:5]}")

    plan = []
    for name in names:
        status, target = classify(variables[name])
        plan.append(
            {
                "name": name,
                "dictionary_type": variables[name]["type"],
                "status": status,
                "target_type": target,
                "not_asked_count": 0,
                "cast_failures": 0,
            }
        )

    for batch in batches(plan):
        select = []
        for column in batch:
            col = quote(column["name"])
            select.append(f"COUNT(*) FILTER (WHERE {col} = '{NOT_ASKED}')")
            if column["status"] == "cast_candidate":
                select.append(
                    f"COUNT(*) FILTER (WHERE {col} <> '{NOT_ASKED}' "
                    f"AND TRY_CAST({col} AS {column['target_type']}) IS NULL)"
                )
        result = iter(con.execute(f"SELECT {','.join(select)} FROM '{SOURCE}'").fetchone())
        for column in batch:
            column["not_asked_count"] = next(result)
            if column["status"] == "cast_candidate":
                column["cast_failures"] = next(result)
        logger.info("Planned %s/%s columns", plan.index(batch[-1]) + 1, len(plan))

    for column in plan:
        resolve(column)
    return pl.DataFrame(plan)


def select_expression(column: dict) -> str:
    col = quote(column["name"])
    value = f"NULLIF({col}, '{NOT_ASKED}')"
    if column["status"] == "cast":
        value = f"TRY_CAST({value} AS {column['target_type']})"
    return f"{value} AS {col}"


def write_typed(con: duckdb.DuckDBPyConnection, plan: pl.DataFrame) -> None:
    select = ",\n    ".join(select_expression(column) for column in plan.iter_rows(named=True))
    if TARGET.exists():
        TARGET.unlink()
    con.execute(
        f"COPY (SELECT\n    {select}\nFROM '{SOURCE}') "
        f"TO '{TARGET}' (FORMAT PARQUET, COMPRESSION ZSTD)"
    )


def verify(con: duckdb.DuckDBPyConnection, plan: pl.DataFrame) -> None:
    """Check every value survived and NULLs match the sentinel exactly."""
    source_rows = con.execute(f"SELECT COUNT(*) FROM '{SOURCE}'").fetchone()[0]
    target_rows = con.execute(f"SELECT COUNT(*) FROM '{TARGET}'").fetchone()[0]
    if source_rows != target_rows:
        raise SystemExit(f"Row count changed: {source_rows} -> {target_rows}")
    if pq.ParquetFile(TARGET).schema.names != plan["name"].to_list():
        raise SystemExit("Column names or order changed")

    bad = {}
    for batch in batches(plan.to_dicts()):
        select = []
        for column in batch:
            col = quote(column["name"])
            if column["status"] == "cast":
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
        bad.update({column["name"]: n for column, n in zip(batch, result) if n})

    if bad:
        raise SystemExit(f"Verification failed for {len(bad)} columns: {list(bad)[:5]}")
    logger.info("Verified %s columns across %s rows", plan.height, target_rows)


def main() -> None:
    con = duckdb.connect()
    con.execute("SET threads=2; SET memory_limit='4GB'")

    plan = plan_columns(con)
    write_typed(con, plan)
    verify(con, plan)

    plan.write_csv(REPORT)
    logger.info("Status counts:\n%s", plan["status"].value_counts(sort=True))
    logger.info("Wrote %s (%.1f MB) and %s", TARGET.name, TARGET.stat().st_size / 1e6, REPORT.name)


if __name__ == "__main__":
    main()
