import polars as pl
import pytest

from finaccess import niches


def gap(metric, dimension, segment, gap_adults, universe="all_adults"):
    return {
        "universe": universe,
        "metric": metric,
        "dimension": dimension,
        "segment": segment,
        "n": 100,
        "share_served": 0.2,
        "national_share": 0.5,
        "gap_pp": -30.0,
        "gap_adults": gap_adults,
    }


def barrier(product, barrier, share, dimension="all", segment="All", n_asked=100, low=False):
    return {
        "product": product,
        "barrier": barrier,
        "dimension": dimension,
        "segment": segment,
        "share_citing": share,
        "n_asked": n_asked,
        "low_confidence": low,
    }


@pytest.fixture
def segment_gaps():
    return pl.DataFrame(
        [
            gap("bank", "education", "None", 900.0),
            gap("bank", "sex", "Female", 300.0),  # smaller gap for the same product
            gap("loan", "age_group", "18-25", 700.0),
            gap("insurance", "county", "Kitui", 500.0),
            gap("pension", "sex", "Female", 400.0),  # no barrier data for pensions
            gap("formal_access", "age_group", "18-25", 9_999.0),  # aggregate, not a product
            gap("savings", "age_group", "18-25", 8_888.0, universe="mobile_money_users"),
        ]
    )


@pytest.fixture
def barriers():
    return pl.DataFrame(
        [
            # bank, adults with no education: the segment base is fine
            barrier("bank", "affordability", 0.8, "education", "None"),
            barrier("bank", "awareness", 0.2, "education", "None"),
            barrier("bank", "other", 0.9, "education", "None"),  # ignored even though largest
            # credit for 18-25: a different mix from the national one
            barrier("credit", "affordability", 0.5, "age_group", "18-25"),
            barrier("credit", "relevance", 0.6, "age_group", "18-25"),
            barrier("credit", "affordability", 0.55),
            barrier("credit", "relevance", 0.4),
            # insurance in Kitui was asked too few people, so fall back to the national mix
            barrier("insurance", "trust", 0.9, "county", "Kitui", n_asked=10, low=True),
            barrier("insurance", "affordability", 0.7),
            barrier("insurance", "awareness", 0.3),
        ]
    )


def pick(segment_gaps, barriers):
    return niches.pick_niches(segment_gaps, barriers)


def row(result, metric):
    return result.filter(pl.col("product_metric") == metric).row(0, named=True)


def test_one_niche_per_product_using_the_largest_gap(segment_gaps, barriers):
    result = pick(segment_gaps, barriers)
    assert sorted(result["product_metric"].to_list()) == ["bank", "insurance", "loan", "pension"]
    bank = row(result, "bank")
    assert (bank["dimension"], bank["segment"], bank["gap_adults"]) == ("education", "None", 900.0)


def test_aggregates_and_other_universes_are_not_niches(segment_gaps, barriers):
    result = pick(segment_gaps, barriers)
    assert "formal_access" not in result["product_metric"].to_list()
    assert "savings" not in result["product_metric"].to_list()


def test_ranked_by_gap_size_starting_at_one(segment_gaps, barriers):
    result = pick(segment_gaps, barriers)
    assert result["rank"].to_list() == [1, 2, 3, 4]
    assert result["product_metric"].to_list() == ["bank", "loan", "insurance", "pension"]


def test_segment_barriers_are_used_and_other_is_ignored(segment_gaps, barriers):
    bank = row(pick(segment_gaps, barriers), "bank")
    assert bank["barrier_basis"] == "segment"
    assert bank["dominant_barrier"] == "affordability"
    assert bank["dominant_share"] == pytest.approx(0.8)
    assert bank["second_barrier"] == "awareness"
    assert bank["awareness_share"] == pytest.approx(0.2)
    assert bank["implication"] == niches.IMPLICATION["affordability"]


def test_loans_use_the_credit_barriers_and_can_be_led_by_relevance(segment_gaps, barriers):
    loan = row(pick(segment_gaps, barriers), "loan")
    assert loan["dominant_barrier"] == "relevance"
    assert loan["second_barrier"] == "affordability"
    assert loan["implication"] == niches.IMPLICATION["relevance"]


def test_small_segment_bases_fall_back_to_the_national_barrier(segment_gaps, barriers):
    insurance = row(pick(segment_gaps, barriers), "insurance")
    assert insurance["barrier_basis"] == "national"
    assert insurance["dominant_barrier"] == "affordability"  # not the segment's trust at 0.9
    assert insurance["awareness_share"] == pytest.approx(0.3)


def test_products_without_reasons_for_non_use_are_flagged(segment_gaps, barriers):
    pension = row(pick(segment_gaps, barriers), "pension")
    assert pension["barrier_basis"] == "not measured"
    assert pension["dominant_barrier"] is None
    assert pension["implication"] == niches.NOT_MEASURED


def test_every_implication_matches_a_real_barrier_category():
    from finaccess.barriers import CATEGORIES

    assert set(niches.IMPLICATION) <= set(CATEGORIES)
    assert "other" not in niches.IMPLICATION


def test_niche_metrics_are_real_metric_ids():
    from finaccess.metrics import METRICS

    ids = {m.id for m in METRICS}
    assert set(niches.NICHE_METRICS) <= ids
