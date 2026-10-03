import polars as pl
import pytest

from finaccess import gaps


def segment(metric, name, share, national, n=100, adults=1_000.0, dimension="county"):
    return {
        "universe": "all_adults",
        "metric": metric,
        "dimension": dimension,
        "segment": name,
        "n": n,
        "adults": adults,
        "adults_served": adults * share,
        "share_served": share,
        "unserved_adults": adults * (1 - share),
        "national_share": national,
        "gap_pp": (share - national) * 100,
        "low_confidence": n < 30,
    }


@pytest.fixture
def metrics():
    return pl.DataFrame(
        [
            segment("bank", "National", 0.5, 0.5, dimension="all"),
            segment("bank", "Big lag", 0.4, 0.5, adults=2_000.0),
            segment("bank", "Small lag", 0.46, 0.5),
            segment("bank", "Tiny sample", 0.1, 0.5, n=10),
            segment("bank", "Medium lag", 0.4, 0.5),
            segment("digital_credit", "Relative lag", 0.01, 0.02),
            segment("digital_credit", "Slight lag", 0.019, 0.02),
        ]
    )


def names(df, metric):
    return df.filter(pl.col("metric") == metric)["segment"].to_list()


def test_point_gap_rule_picks_segments_lagging_by_five_points(metrics):
    result = gaps.segment_gaps(metrics)
    assert "Big lag" in names(result, "bank")
    # 4pp (8% relative) is below both thresholds
    assert "Small lag" not in names(result, "bank")


def test_relative_rule_catches_low_prevalence_products(metrics):
    result = gaps.segment_gaps(metrics)
    # 1pp behind, but half the national share
    assert names(result, "digital_credit") == ["Relative lag"]


def test_tiny_samples_and_national_rows_are_never_gaps(metrics):
    result = gaps.segment_gaps(metrics)
    assert "Tiny sample" not in names(result, "bank")
    assert "National" not in names(result, "bank")


def test_gap_adults_is_the_shortfall_against_the_national_share(metrics):
    result = gaps.segment_gaps(metrics)
    big = result.filter(pl.col("segment") == "Big lag").row(0, named=True)
    assert big["gap_adults"] == pytest.approx(2_000.0 * (0.5 - 0.4))
    assert big["relative_lag"] == pytest.approx(0.2)


def test_gaps_are_ranked_by_adults_not_percentage_points(metrics):
    result = gaps.segment_gaps(metrics)
    # same 10pp lag, but twice as many adults
    assert names(result, "bank") == ["Big lag", "Medium lag"]


def test_product_gaps_rank_by_unserved_adults():
    metrics = pl.DataFrame(
        [
            segment("bank", "All", 0.5, 0.5, adults=1_000.0, dimension="all"),
            segment("savings", "All", 0.9, 0.9, adults=1_000.0, dimension="all"),
            segment("bank", "A", 0.4, 0.5),
        ]
    )
    result = gaps.product_gaps(metrics)
    assert result["metric"].to_list() == ["bank", "savings"]
    assert result["product"].to_list() == ["Bank usage", "Savings usage"]
