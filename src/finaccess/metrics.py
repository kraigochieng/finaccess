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
import pandas as pd

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


def compute() -> pd.DataFrame:
    con = duckdb.connect()
    frames = []
    for universe in UNIVERSES:
        for metric in METRICS:
            # "all" is the national baseline within this universe
            cuts = {"all": "'All'", **DIMENSIONS}
            for dimension, segment_sql in cuts.items():
                df = con.execute(segment_query(metric, universe, segment_sql)).fetchdf()
                df = df[df["segment"].notna()]
                df.insert(0, "dimension", dimension)
                df.insert(0, "metric", metric.id)
                df.insert(0, "universe", universe)
                frames.append(df)

    result = pd.concat(frames, ignore_index=True)
    result["adults_served"] = result["adults_served"].fillna(0)
    result["share_served"] = result["adults_served"] / result["adults"]
    result["unserved_adults"] = result["adults"] - result["adults_served"]

    national = (
        result[result["dimension"] == "all"]
        .set_index(["universe", "metric"])["share_served"]
        .rename("national_share")
    )
    result = result.join(national, on=["universe", "metric"])
    result["gap_pp"] = (result["share_served"] - result["national_share"]) * 100
    result["low_confidence"] = result["n"] < MIN_SEGMENT_N
    return result


def check_against_report(result: pd.DataFrame) -> None:
    """Fail if national figures drift from the published 2024 report."""
    national = result[(result["universe"] == "all_adults") & (result["dimension"] == "all")]
    national = national.set_index("metric")

    for metric, (expected, source) in REPORT_SHARES.items():
        actual = national.at[metric, "share_served"] * 100
        if abs(actual - expected) > TOLERANCE_PP:
            raise SystemExit(f"{metric}: {actual:.1f}% vs report {expected}% ({source})")

    bank_users = national.at["bank", "adults_served"] / 1e6
    if abs(bank_users - REPORT_BANK_USERS_MILLIONS) > 0.05:
        raise SystemExit(f"bank users: {bank_users:.2f}M vs report {REPORT_BANK_USERS_MILLIONS}M")
    logger.info("National figures match the 2024 report")


def main() -> None:
    RESULTS_DIR.mkdir(exist_ok=True)
    result = compute()
    check_against_report(result)
    result.round(4).to_csv(METRICS_CSV, index=False)
    logger.info("Wrote %s rows to %s", len(result), METRICS_CSV.name)

    headline = result[(result["universe"] == "all_adults") & (result["dimension"] == "all")]
    logger.info(
        "National shares:\n%s",
        headline.set_index("metric")["share_served"].mul(100).round(1).to_string(),
    )


if __name__ == "__main__":
    main()
