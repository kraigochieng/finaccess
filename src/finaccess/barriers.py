"""Why adults do not use each product, from the survey's reasons-for-non-use questions.

Each question is a multi-response list of 0/1 flags that is only asked of adults who do
not use the product, so the base is "adults who were asked", not a derived non-usage flag.
Reasons are grouped into the six categories the 2024 report uses in Figure 3.9
(affordability, awareness, relevance, trust, eligibility, physical access) plus "other".
The grouping of individual reasons into categories is a judgement call.

Two measures are written:
- share_citing: weighted share of the adults asked who gave at least one reason in the
  category (multi-response, so shares do not sum to 100)
- share_of_mentions: the category's share of all reasons given, which is how the report
  draws Figure 3.9
"""

import logging

import duckdb
import polars as pl

from finaccess import metrics
from finaccess.logging_config import setup_logging

setup_logging()

logger = logging.getLogger(__name__)

BARRIERS_CSV = metrics.RESULTS_DIR / "barriers.csv"

CATEGORIES = [
    "affordability",
    "awareness",
    "relevance",
    "trust",
    "eligibility",
    "physical_access",
    "other",
]

# product -> (label, {category: reason columns}). Reasons "don't know" and "refused" are left out.
BARRIERS = {
    "insurance": (
        "Insurance",
        {
            "affordability": ["D3__1"],
            "awareness": ["D3__2"],
            "relevance": ["D3__3", "D3__4"],  # no need; belief that it brings bad luck
            "trust": ["D3__5"],
            "eligibility": ["D3__6"],
            "other": ["D3__96"],
        },
    ),
    "credit": (
        "Credit",
        {
            "affordability": ["E4__1"],
            "awareness": ["E4__2"],
            "relevance": ["E4__3", "E4__4", "E4__8"],  # dislike, too risky, religion
            "trust": ["E4__5"],
            "eligibility": ["E4__6", "E4__7", "E4__9"],  # ID, collateral, does not qualify
            "other": ["E4__96"],
        },
    ),
    "savings": (
        "Savings",
        {
            "affordability": ["F2__1"],
            "awareness": ["F2__2"],
            "relevance": ["F2__3", "F2__4"],  # no suitable option; no need
            "trust": ["F2__5"],
            "eligibility": ["F2__6"],
            "other": ["F2__7", "F2__96"],
        },
    ),
    "bank": (
        "Bank account",
        {
            "affordability": ["H2__1", "H2__2"],  # no income; minimum balance
            "awareness": ["H2__3"],
            "relevance": ["H2__4"],
            "trust": ["H2__6"],
            "eligibility": ["H2__7"],
            "physical_access": ["H2__5", "H2__8"],
            "other": ["H2__9", "H2__96"],
        },
    ),
    "mobile_money": (
        "Mobile money",
        {
            "affordability": ["K2i__1"],
            "awareness": ["K2i__3"],
            "relevance": ["K2i__4"],
            "trust": ["K2i__6"],
            "eligibility": ["K2i__7"],
            "physical_access": ["K2i__2", "K2i__5", "K2i__8"],  # phone, network, line blocked
            "other": ["K2i__9"],
        },
    ),
    "mobile_banking": (
        "Mobile banking",
        {
            "affordability": ["M2i__1"],
            "awareness": ["M2i__3"],
            "relevance": ["M2i__4", "M2i__5"],  # no need; will not link bank to phone
            "trust": ["M2i__6"],
            "eligibility": ["M2i__7"],
            "physical_access": ["M2i__2", "M2i__8"],  # phone, line blocked
            "other": ["M2i__96"],
        },
    ),
}

# Insurance figures from Figure 3.9 of the 2024 report (share of reasons, percent). Bank is
# close but not exact (up to ~4 points) so it is not asserted.
REPORT_INSURANCE_SHARES = {"affordability": 63.2, "awareness": 19.4}
TOLERANCE_PP = 1.0


def barrier_query(product: str, segment_sql: str) -> str:
    _, reasons = BARRIERS[product]
    base = next(iter(reasons.values()))[0]  # all reasons of a question are null together
    select = []
    for category, columns in reasons.items():
        cited = " OR ".join(f"{c} = 1" for c in columns)
        count = " + ".join(f"COALESCE({c}, 0)" for c in columns)
        select.append(f'SUM({metrics.WEIGHT}) FILTER (WHERE {cited}) AS "{category}__citing"')
        select.append(f'SUM({metrics.WEIGHT} * ({count})) AS "{category}__mentions"')
    return f"""
        SELECT
            {segment_sql} AS segment,
            COUNT(*) AS n_asked,
            SUM({metrics.WEIGHT}) AS adults_asked,
            {", ".join(select)}
        FROM '{metrics.SOURCE}'
        WHERE {base} IS NOT NULL
          AND {metrics.WEIGHT} IS NOT NULL
          AND {metrics.ADULTS}
        GROUP BY 1
    """


def compute() -> pl.DataFrame:
    con = duckdb.connect()
    frames = []
    for product, (_, reasons) in BARRIERS.items():
        cuts = {"all": "'All'", **metrics.DIMENSIONS}
        for dimension, segment_sql in cuts.items():
            df = con.execute(barrier_query(product, segment_sql)).pl()
            df = df.filter(pl.col("segment").is_not_null())
            for category in reasons:
                frames.append(
                    df.select(
                        pl.lit(product).alias("product"),
                        pl.lit(category).alias("barrier"),
                        pl.lit(dimension).alias("dimension"),
                        "segment",
                        "n_asked",
                        "adults_asked",
                        pl.col(f"{category}__citing").fill_null(0).alias("adults_citing"),
                        pl.col(f"{category}__mentions").fill_null(0).alias("mentions"),
                    )
                )

    keys = ["product", "dimension", "segment"]
    result = pl.concat(frames).with_columns(
        (pl.col("adults_citing") / pl.col("adults_asked")).alias("share_citing"),
        (pl.col("mentions") / pl.col("mentions").sum().over(keys)).alias("share_of_mentions"),
    )
    national = result.filter(pl.col("dimension") == "all").select(
        "product", "barrier", pl.col("share_citing").alias("national_share_citing")
    )
    return (
        result.join(national, on=["product", "barrier"], how="left")
        .with_columns(
            ((pl.col("share_citing") - pl.col("national_share_citing")) * 100).alias("gap_pp"),
            (pl.col("n_asked") < metrics.MIN_SEGMENT_N).alias("low_confidence"),
        )
        .sort("product", "dimension", "segment", "barrier")
    )


def check_against_report(result: pl.DataFrame) -> None:
    """Fail if insurance barriers drift from Figure 3.9 of the 2024 report."""
    national = result.filter(
        (pl.col("product") == "insurance") & (pl.col("dimension") == "all")
    )
    for category, expected in REPORT_INSURANCE_SHARES.items():
        actual = national.filter(pl.col("barrier") == category)["share_of_mentions"][0] * 100
        if abs(actual - expected) > TOLERANCE_PP:
            raise SystemExit(f"insurance {category}: {actual:.1f}% vs report {expected}%")
    logger.info("Insurance barriers match the 2024 report")


def main() -> None:
    metrics.RESULTS_DIR.mkdir(exist_ok=True)
    result = compute()
    check_against_report(result)

    result.with_columns(pl.col(pl.Float64).round(4)).write_csv(BARRIERS_CSV)
    logger.info("Wrote %s rows to %s", result.height, BARRIERS_CSV.name)

    national = (
        result.filter(pl.col("dimension") == "all")
        .select("product", "barrier", (pl.col("share_citing") * 100).round(1).alias("pct_citing"))
        .pivot(on="barrier", index="product", values="pct_citing")
    )
    logger.info("Share of adults asked who cite each barrier:\n%s", national)


if __name__ == "__main__":
    main()
