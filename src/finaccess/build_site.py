"""Build the data story page (site/index.html) from the results csvs.

Every number on the page comes from the payload built here, so the page cannot drift
from the analysis. The template holds only structure, styling and chart code.
"""

import json
import logging

import polars as pl

from finaccess import metrics
from finaccess.barriers import BARRIERS, BARRIERS_CSV, CATEGORIES, REPORT_INSURANCE_SHARES
from finaccess.gaps import PRODUCT_GAPS_CSV, SEGMENT_GAPS_CSV
from finaccess.logging_config import setup_logging
from finaccess.niches import NICHES_CSV
from finaccess.paths import DATA_DIR, REPO_ROOT

setup_logging()

logger = logging.getLogger(__name__)

TEMPLATE = DATA_DIR / "site_template.html"
OUTPUT = REPO_ROOT / "site" / "index.html"
PLACEHOLDER = "/*__DATA__*/null"

# Short names for charts (the metric labels in metrics.py are written for the code)
PRODUCT_LABELS = {
    "any_access": "Any access",
    "formal_access": "Formal access",
    "mobile_money": "Mobile money",
    "bank": "Bank account",
    "savings": "Savings",
    "loan": "Loans",
    "digital_credit": "Digital credit",
    "digital_apps": "App-based digital loans",
    "insurance": "Insurance",
    "pension": "Pension",
    "sacco": "SACCO",
}
BARRIER_PRODUCT_LABELS = {
    "insurance": "Insurance",
    "credit": "Credit",
    "savings": "Savings",
    "bank": "Bank account",
    "mobile_money": "Mobile money",
    "mobile_banking": "Mobile banking",
}
BARRIER_LABELS = {
    "affordability": "Affordability",
    "awareness": "Awareness",
    "relevance": "Relevance",
    "trust": "Trust",
    "eligibility": "Eligibility (ID, qualifying)",
    "physical_access": "Physical access (phone, network, distance)",
    "other": "Other",
}
DIMENSION_LABELS = {
    "age_group": "Age group",
    "sex": "Sex",
    "education": "Education",
    "county": "County",
}
UNIVERSE_LABELS = {"all_adults": "All adults", "mobile_money_users": "Mobile money users"}
SEGMENT_LABELS = {("education", "None"): "No formal education", ("age_group", "Above 55"): "Over 55"}


def pretty_segment(dimension: str, segment: str) -> str:
    return SEGMENT_LABELS.get((dimension, segment), segment)


def records(df: pl.DataFrame) -> list[dict]:
    return df.with_columns(pl.col(pl.Float64).round(4)).to_dicts()


def prepare() -> dict:
    """Everything the page needs, as plain JSON-able data."""
    products = pl.read_csv(PRODUCT_GAPS_CSV)
    segments = pl.read_csv(SEGMENT_GAPS_CSV).with_columns(
        pl.struct("dimension", "segment")
        .map_elements(lambda r: pretty_segment(r["dimension"], r["segment"]), return_dtype=pl.String)
        .alias("segment_label")
    )
    barriers = pl.read_csv(BARRIERS_CSV)
    niches = pl.read_csv(NICHES_CSV).with_columns(
        pl.struct("dimension", "segment")
        .map_elements(lambda r: pretty_segment(r["dimension"], r["segment"]), return_dtype=pl.String)
        .alias("segment_label")
    )

    national = barriers.filter(pl.col("dimension") == "all").select(
        "product", "barrier", "share_citing", "share_of_mentions", "adults_citing", "adults_asked"
    )

    return {
        "products": records(
            products.select("universe", "metric", "adults", "adults_served", "share_served", "unserved_adults")
        ),
        "segments": records(
            segments.select(
                "universe", "metric", "dimension", "segment_label", "n",
                "share_served", "national_share", "gap_pp", "gap_adults",
            )
        ),
        "barriers": records(national),
        "niches": records(niches),
        "checks": checks(products, national),
        "labels": {
            "products": PRODUCT_LABELS,
            "barrierProducts": BARRIER_PRODUCT_LABELS,
            "barriers": BARRIER_LABELS,
            "dimensions": DIMENSION_LABELS,
            "universes": UNIVERSE_LABELS,
        },
        "barrierOrder": [c for c in CATEGORIES],
        "barrierProductOrder": list(BARRIERS),
        "minSegmentN": metrics.MIN_SEGMENT_N,
    }


def checks(products: pl.DataFrame, barriers: pl.DataFrame) -> list[dict]:
    """Our figures next to the ones published in the 2024 report."""
    adults = products.filter(pl.col("universe") == "all_adults")

    def served(metric: str) -> float:
        return adults.filter(pl.col("metric") == metric)["share_served"][0] * 100

    insurance = barriers.filter(pl.col("product") == "insurance")

    def mentions(category: str) -> float:
        return insurance.filter(pl.col("barrier") == category)["share_of_mentions"][0] * 100

    rows = [
        (name, ours, report, unit, source)
        for name, ours, report, unit, source in [
            ("Formal access", served("formal_access"), metrics.REPORT_SHARES["formal_access"][0], "%", "Figure 2.1"),
            ("Financially excluded", 100 - served("any_access"), 100 - metrics.REPORT_SHARES["any_access"][0], "%", "Figure 2.1"),
            ("Credit usage", served("loan"), metrics.REPORT_SHARES["loan"][0], "%", "Section 3.4.4"),
            ("Savings usage", served("savings"), metrics.REPORT_SHARES["savings"][0], "%", "Section 3.4.4"),
            (
                "Bank users",
                adults.filter(pl.col("metric") == "bank")["adults_served"][0] / 1e6,
                metrics.REPORT_BANK_USERS_MILLIONS,
                "M",
                "Section 3.4.1",
            ),
            ("Insurance non-use: affordability", mentions("affordability"), REPORT_INSURANCE_SHARES["affordability"], "%", "Figure 3.9"),
            ("Insurance non-use: awareness", mentions("awareness"), REPORT_INSURANCE_SHARES["awareness"], "%", "Figure 3.9"),
        ]
    ]
    return [
        {"name": name, "ours": round(ours, 1), "report": round(report, 1), "unit": unit, "source": source}
        for name, ours, report, unit, source in rows
    ]


def render(template: str, data: dict) -> str:
    if PLACEHOLDER not in template:
        raise SystemExit(f"Template has no {PLACEHOLDER} placeholder")
    # "<" is escaped so labels can never close the script tag
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    return template.replace(PLACEHOLDER, payload)


def main() -> None:
    page = render(TEMPLATE.read_text(encoding="utf-8"), prepare())
    OUTPUT.parent.mkdir(exist_ok=True)
    OUTPUT.write_text(page, encoding="utf-8")
    logger.info("Wrote %s (%.0f KB)", OUTPUT.relative_to(REPO_ROOT), len(page) / 1024)


if __name__ == "__main__":
    main()
