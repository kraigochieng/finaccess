"""Pick niches with a stated rule: the biggest gap per product, and why it exists.

Rule, applied to the all-adults universe:
1. Consider products only (not the aggregate access metrics or the narrow app-lender metric).
2. For each product take the segment with the largest gap_adults (adults short of the
   national share) among segments that already pass the gap rules in gaps.py.
3. Attach the barrier non-users cite most for that product and segment. Where the segment
   was asked too few people, fall back to the national barrier for the product. Products
   whose reasons for non-use are not in the survey are flagged as not measured.
4. Rank the shortlist by gap_adults.
"""

import logging

import polars as pl

from finaccess import metrics
from finaccess.barriers import BARRIERS_CSV
from finaccess.gaps import SEGMENT_GAPS_CSV
from finaccess.logging_config import setup_logging

setup_logging()

logger = logging.getLogger(__name__)

NICHES_CSV = metrics.RESULTS_DIR / "niches.csv"

NICHE_METRICS = [
    "mobile_money",
    "bank",
    "savings",
    "loan",
    "digital_credit",
    "insurance",
    "pension",
    "sacco",
]

# metric id -> product id in the barriers analysis (only these have reasons for non-use)
BARRIER_PRODUCT = {
    "mobile_money": "mobile_money",
    "bank": "bank",
    "savings": "savings",
    "loan": "credit",
    "insurance": "insurance",
}

# What a product has to do about each barrier
IMPLICATION = {
    "affordability": "Price it low: no minimum balance, pay-as-you-go or income-linked pricing",
    "awareness": "Invest in reach and education: explain it simply through channels people already trust",
    "relevance": "Fit a real need: many do not see a use for the product as it is",
    "trust": "Earn trust: transparent terms, regulated providers, fast and visible payouts",
    "eligibility": "Lower the onboarding hurdle: ID-light checks and alternatives to collateral",
    "physical_access": "Work on basic phones and weak networks: USSD and agent-assisted onboarding",
}
NOT_MEASURED = "The survey does not ask why people do not use this product"

KEYS = ["product", "dimension", "segment"]
BARRIER_FIELDS = [
    "dominant_barrier",
    "dominant_share",
    "second_barrier",
    "second_share",
    "awareness_share",
]


def summarise_barriers(barriers: pl.DataFrame, keys: list[str]) -> pl.DataFrame:
    """Top two barriers (ignoring 'other') and the awareness share for each group."""
    dominant = (
        barriers.filter(pl.col("barrier") != "other")
        .sort("share_citing", descending=True)
        .group_by(keys, maintain_order=True)
        .agg(
            pl.col("barrier").first().alias("dominant_barrier"),
            pl.col("share_citing").first().alias("dominant_share"),
            pl.col("barrier").slice(1, 1).first().alias("second_barrier"),
            pl.col("share_citing").slice(1, 1).first().alias("second_share"),
            pl.col("n_asked").first(),
            pl.col("low_confidence").first(),
        )
    )
    awareness = barriers.filter(pl.col("barrier") == "awareness").select(
        *keys, pl.col("share_citing").alias("awareness_share")
    )
    return dominant.join(awareness, on=keys, how="left")


def pick_niches(segment_gaps: pl.DataFrame, barriers: pl.DataFrame) -> pl.DataFrame:
    top = (
        segment_gaps.filter(
            (pl.col("universe") == "all_adults") & pl.col("metric").is_in(NICHE_METRICS)
        )
        .sort("gap_adults", descending=True)
        .group_by("metric", maintain_order=True)
        .first()
        .with_columns(pl.col("metric").replace_strict(BARRIER_PRODUCT, default=None).alias("product"))
    )

    for_segment = summarise_barriers(
        barriers.filter(pl.col("dimension") != "all"), KEYS
    ).rename(lambda c: f"seg_{c}" if c not in KEYS else c)
    for_nation = summarise_barriers(
        barriers.filter(pl.col("dimension") == "all"), ["product"]
    ).rename(lambda c: f"nat_{c}" if c != "product" else c)

    niches = (
        top.join(for_segment, on=KEYS, how="left")
        .join(for_nation, on="product", how="left")
        .with_columns(
            pl.when(pl.col("product").is_null())
            .then(pl.lit("not measured"))
            .when(pl.col("seg_dominant_barrier").is_not_null() & ~pl.col("seg_low_confidence").fill_null(True))
            .then(pl.lit("segment"))
            .otherwise(pl.lit("national"))
            .alias("barrier_basis")
        )
        .with_columns(
            [
                pl.when(pl.col("barrier_basis") == "segment")
                .then(pl.col(f"seg_{field}"))
                .when(pl.col("barrier_basis") == "national")
                .then(pl.col(f"nat_{field}"))
                .alias(field)
                for field in BARRIER_FIELDS
            ]
        )
        .with_columns(
            pl.col("dominant_barrier")
            .replace_strict(IMPLICATION, default=NOT_MEASURED)
            .alias("implication")
        )
        .sort("gap_adults", descending=True)
        .with_row_index("rank", offset=1)
    )
    return niches.select(
        "rank",
        pl.col("metric").alias("product_metric"),
        "dimension",
        "segment",
        "n",
        "share_served",
        "national_share",
        "gap_pp",
        "gap_adults",
        "barrier_basis",
        *BARRIER_FIELDS,
        "implication",
    )


def main() -> None:
    segment_gaps = pl.read_csv(SEGMENT_GAPS_CSV)
    barriers = pl.read_csv(BARRIERS_CSV)

    niches = pick_niches(segment_gaps, barriers)
    niches.with_columns(pl.col(pl.Float64).round(4)).write_csv(NICHES_CSV)
    logger.info("Wrote %s niches to %s", niches.height, NICHES_CSV.name)
    logger.info(
        "Niche shortlist:\n%s",
        niches.select(
            "rank", "product_metric", "dimension", "segment",
            (pl.col("gap_adults") / 1e6).round(2).alias("short_m"),
            "dominant_barrier", "barrier_basis",
        ),
    )


if __name__ == "__main__":
    main()
