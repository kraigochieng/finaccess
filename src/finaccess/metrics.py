"""Weighted share of adults served by each financial product, by segment.

Every metric is a "served" share: the weighted share of adults for whom the
survey's derived indicator says they use / have access to the product. Weights
are individual weights (indWeight), so shares describe adults, not households.
Adults are 18 and over, as in the official report; the survey also interviewed
16-17 year olds, who are excluded.
"""

import logging
from dataclasses import dataclass

import duckdb
import polars as pl

from finaccess.logging_config import setup_logging
from finaccess.paths import DATA_DIR

setup_logging()

logger = logging.getLogger(__name__)

SOURCE = DATA_DIR / "finaccess_2024_typed.parquet"
RESULTS_DIR = DATA_DIR / "results"
METRICS_CSV = RESULTS_DIR / "metrics_by_segment.csv"

WEIGHT = "indWeight"
ADULTS = "Age <> '16-17'"

# Headline figures from the 2024 FinAccess report (adults 18+), used as a check:
# metric id -> (expected national share in percent, source)
REPORT_SHARES = {
    "formal_access": (84.8, "Figure 2.1, formal"),
    "any_access": (90.1, "Figure 2.1, 100 - excluded 9.9"),
}
# Bank users in millions of adults (section 3.2)
REPORT_BANK_USERS_MILLIONS = 14.8
TOLERANCE_PP = 0.1

# Segments with fewer sampled adults than this are flagged, not hidden
MIN_SEGMENT_N = 30


@dataclass(frozen=True)
class Metric:
    id: str
    label: str
    served: str  # SQL condition that is true for a served adult
    column: str  # indicator column; rows where it is NULL are excluded


METRICS = [
    Metric("any_access", "Any formal or informal access", "Overall_Access_fnl <> 'excluded'", "Overall_Access_fnl"),
    Metric("formal_access", "Formal access", "formal_access_fnl = 'Yes'", "formal_access_fnl"),
    Metric("mobile_money", "Mobile money access", "mobile_money_access = 'Yes'", "mobile_money_access"),
    Metric("bank", "Bank usage", "bank_usage_overall = 'Usage'", "bank_usage_overall"),
    Metric("savings", "Savings usage", "Savings_usage = 'Usage'", "Savings_usage"),
    Metric("loan", "Loan usage", "Loan_usage = 'Usage'", "Loan_usage"),
    Metric("digital_credit", "Digital credit usage", "Digital_credit_usage = 'Usage'", "Digital_credit_usage"),
    Metric("insurance", "Insurance usage (incl. NHIF)", "All_Insurance_including_NHIF = 'Usage'", "All_Insurance_including_NHIF"),
    Metric("pension", "Pension usage", "Pension_usage = 'Usage'", "Pension_usage"),
    Metric("sacco", "SACCO usage", "Sacco_usage = 'Usage'", "Sacco_usage"),
]

# dimension id -> SQL expression for the segment label
DIMENSIONS = {
    "county": "county",
    "sex": "Sex",
    "age_group": "Age",
    "education": "trim(replace(A20, '\"', ''))",  # labels carry stray quotes and spaces
}

# Groups of adults the shares are measured within
UNIVERSES = {
    "all_adults": "TRUE",
    "mobile_money_users": "mobile_money_access = 'Yes'",
}


def segment_query(metric: Metric, universe: str, segment_sql: str) -> str:
    return f"""
        SELECT
            {segment_sql} AS segment,
            COUNT(*) AS n,
            SUM({WEIGHT}) AS adults,
            SUM({WEIGHT}) FILTER (WHERE {metric.served}) AS adults_served
        FROM '{SOURCE}'
        WHERE {metric.column} IS NOT NULL
          AND {WEIGHT} IS NOT NULL
          AND {ADULTS}
          AND ({UNIVERSES[universe]})
        GROUP BY 1
    """


def compute() -> pl.DataFrame:
    con = duckdb.connect()
    frames = []
    for universe in UNIVERSES:
        for metric in METRICS:
            # "all" is the national baseline within this universe
            cuts = {"all": "'All'", **DIMENSIONS}
            for dimension, segment_sql in cuts.items():
                frames.append(
                    con.execute(segment_query(metric, universe, segment_sql))
                    .pl()
                    .filter(pl.col("segment").is_not_null())
                    .select(
                        pl.lit(universe).alias("universe"),
                        pl.lit(metric.id).alias("metric"),
                        pl.lit(dimension).alias("dimension"),
                        "segment",
                        "n",
                        "adults",
                        pl.col("adults_served").fill_null(0),
                    )
                )

    result = pl.concat(frames).with_columns(
        (pl.col("adults_served") / pl.col("adults")).alias("share_served"),
        (pl.col("adults") - pl.col("adults_served")).alias("unserved_adults"),
    )

    national = result.filter(pl.col("dimension") == "all").select(
        "universe", "metric", pl.col("share_served").alias("national_share")
    )
    return result.join(national, on=["universe", "metric"], how="left").with_columns(
        ((pl.col("share_served") - pl.col("national_share")) * 100).alias("gap_pp"),
        (pl.col("n") < MIN_SEGMENT_N).alias("low_confidence"),
    )


def national_row(result: pl.DataFrame, metric: str) -> dict:
    return result.filter(
        (pl.col("universe") == "all_adults")
        & (pl.col("dimension") == "all")
        & (pl.col("metric") == metric)
    ).row(0, named=True)


def check_against_report(result: pl.DataFrame) -> None:
    """Fail if national figures drift from the published 2024 report."""
    for metric, (expected, source) in REPORT_SHARES.items():
        actual = national_row(result, metric)["share_served"] * 100
        if abs(actual - expected) > TOLERANCE_PP:
            raise SystemExit(f"{metric}: {actual:.1f}% vs report {expected}% ({source})")

    bank_users = national_row(result, "bank")["adults_served"] / 1e6
    if abs(bank_users - REPORT_BANK_USERS_MILLIONS) > 0.05:
        raise SystemExit(f"bank users: {bank_users:.2f}M vs report {REPORT_BANK_USERS_MILLIONS}M")
    logger.info("National figures match the 2024 report")


def main() -> None:
    RESULTS_DIR.mkdir(exist_ok=True)
    result = compute()
    check_against_report(result)

    result.with_columns(pl.col(pl.Float64).round(4)).write_csv(METRICS_CSV)
    logger.info("Wrote %s rows to %s", result.height, METRICS_CSV.name)

    headline = result.filter(
        (pl.col("universe") == "all_adults") & (pl.col("dimension") == "all")
    ).select("metric", (pl.col("share_served") * 100).round(1).alias("share_pct"))
    logger.info("National shares:\n%s", headline)


if __name__ == "__main__":
    main()
