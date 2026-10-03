"""Rank the gaps in the weighted metrics so niches stand out.

Two views:
- segment gaps: segments (county, sex, age group, education) whose share served
  lags the national share, ranked by how many adults that lag represents
- product gaps: how many adults each product leaves unserved, for all adults and
  for mobile money users (they have the rail but not the product)
"""

import logging

import polars as pl

from finaccess.logging_config import setup_logging
from finaccess.metrics import METRICS, METRICS_CSV, MIN_SEGMENT_N, RESULTS_DIR

setup_logging()

logger = logging.getLogger(__name__)

SEGMENT_GAPS_CSV = RESULTS_DIR / "segment_gaps.csv"
PRODUCT_GAPS_CSV = RESULTS_DIR / "product_gaps.csv"

# A segment counts as a gap when it lags the national share by at least this many
# points, or sits at least this far below it in relative terms. The relative rule
# catches low-prevalence products (e.g. digital credit at ~2%) where a fixed
# point gap could never trigger.
MIN_GAP_PP = 5.0
MIN_RELATIVE_LAG = 0.25


def segment_gaps(metrics: pl.DataFrame) -> pl.DataFrame:
    lags = (pl.col("gap_pp") <= -MIN_GAP_PP) | (
        pl.col("share_served") <= pl.col("national_share") * (1 - MIN_RELATIVE_LAG)
    )
    return (
        metrics.filter(
            (pl.col("dimension") != "all") & (pl.col("n") >= MIN_SEGMENT_N) & lags
        )
        .with_columns(
            (1 - pl.col("share_served") / pl.col("national_share")).alias("relative_lag"),
            # Adults who would be served if the segment matched the national share
            (pl.col("adults") * (pl.col("national_share") - pl.col("share_served"))).alias(
                "gap_adults"
            ),
        )
        .sort(["universe", "metric", "gap_adults"], descending=[False, False, True])
    )


def product_gaps(metrics: pl.DataFrame) -> pl.DataFrame:
    labels = {m.id: m.label for m in METRICS}
    return (
        metrics.filter(pl.col("dimension") == "all")
        .with_columns(pl.col("metric").replace_strict(labels).alias("product"))
        .select(
            "universe",
            "metric",
            "product",
            "adults",
            "adults_served",
            "share_served",
            "unserved_adults",
        )
        .sort(["universe", "unserved_adults"], descending=[False, True])
    )


def rounded(df: pl.DataFrame) -> pl.DataFrame:
    return df.with_columns(pl.col(pl.Float64).round(4))


def main() -> None:
    metrics = pl.read_csv(METRICS_CSV)

    segments = segment_gaps(metrics)
    rounded(segments).write_csv(SEGMENT_GAPS_CSV)
    products = product_gaps(metrics)
    rounded(products).write_csv(PRODUCT_GAPS_CSV)
    logger.info("Wrote %s segment gaps and %s product gaps", segments.height, products.height)

    top = (
        segments.filter(pl.col("universe") == "all_adults")
        .group_by("metric", maintain_order=True)
        .head(1)
        .select("metric", "dimension", "segment", "share_served", "gap_pp", "gap_adults")
    )
    logger.info("Largest lagging segment per product (all adults):\n%s", top.with_columns(pl.col(pl.Float64).round(3)))


if __name__ == "__main__":
    main()
