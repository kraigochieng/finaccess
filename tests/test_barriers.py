import polars as pl
import pytest

from finaccess import barriers, metrics
from finaccess.paths import DATA_DIR

TINY = {
    "toy": (
        "Toy",
        {"affordability": ["F1"], "awareness": ["F2"], "relevance": ["F3", "F4"]},
    )
}


def person(weight, age, flags, county="A", sex="Male", education="Primary"):
    f1, f2, f3, f4 = flags
    return {
        "indWeight": weight,
        "Age": age,
        "county": county,
        "Sex": sex,
        "A20": education,
        "F1": f1,
        "F2": f2,
        "F3": f3,
        "F4": f4,
    }


@pytest.fixture
def synthetic(tmp_path, monkeypatch):
    rows = [
        person(100.0, "18-25", (1, 0, 0, 0)),
        person(300.0, "26-35", (1, 1, 0, 0)),
        person(100.0, "26-35", (0, 0, 1, 1)),  # cites two relevance reasons
        person(100.0, "26-35", (0, 0, 0, 1)),  # cites only the second relevance reason
        # not an adult
        person(600.0, "16-17", (1, 1, 1, 1)),
        # not asked the question (flags are null), so not in the base
        person(200.0, "18-25", (None, None, None, None)),
    ]
    path = tmp_path / "typed.parquet"
    pl.DataFrame(rows, schema_overrides={f: pl.Int8 for f in ["F1", "F2", "F3", "F4"]}).write_parquet(path)
    monkeypatch.setattr(metrics, "SOURCE", path)
    monkeypatch.setattr(barriers, "BARRIERS", TINY)
    return barriers.compute()


def row(result, barrier, dimension="all", segment="All"):
    return result.filter(
        (pl.col("barrier") == barrier)
        & (pl.col("dimension") == dimension)
        & (pl.col("segment") == segment)
    ).row(0, named=True)


def test_base_is_adults_who_were_asked(synthetic):
    national = row(synthetic, "affordability")
    # not the child, not the adult who was not asked
    assert national["n_asked"] == 4
    assert national["adults_asked"] == 600.0


def test_share_citing_is_weighted_and_counts_people_once(synthetic):
    assert row(synthetic, "affordability")["share_citing"] == pytest.approx(400 / 600)
    assert row(synthetic, "awareness")["share_citing"] == pytest.approx(300 / 600)
    # one person ticking both relevance reasons is still one person, and a person who
    # only ticks the second reason still counts: 100 + 100
    assert row(synthetic, "relevance")["adults_citing"] == 200.0
    assert row(synthetic, "relevance")["share_citing"] == pytest.approx(200 / 600)


def test_share_of_mentions_counts_every_reason_given(synthetic):
    # mentions: affordability 400, awareness 300, relevance 2 x 100 + 100 = 300 -> 1000 in total
    assert row(synthetic, "affordability")["share_of_mentions"] == pytest.approx(400 / 1000)
    assert row(synthetic, "relevance")["share_of_mentions"] == pytest.approx(300 / 1000)
    total = synthetic.filter(pl.col("dimension") == "all")["share_of_mentions"].sum()
    assert total == pytest.approx(1.0)


def test_segments_are_compared_with_the_national_share(synthetic):
    segment = row(synthetic, "affordability", "age_group", "26-35")
    assert segment["share_citing"] == pytest.approx(300 / 500)
    assert segment["gap_pp"] == pytest.approx((300 / 500 - 400 / 600) * 100)


def test_small_segments_are_flagged(synthetic):
    assert row(synthetic, "affordability", "age_group", "18-25")["low_confidence"] is True


def report_frame(affordability, awareness):
    base = {"product": "insurance", "dimension": "all"}
    return pl.DataFrame(
        [
            {**base, "barrier": "affordability", "share_of_mentions": affordability},
            {**base, "barrier": "awareness", "share_of_mentions": awareness},
        ]
    )


def test_report_check_passes_on_matching_figures():
    barriers.check_against_report(report_frame(0.632, 0.194))


def test_report_check_fails_when_figures_drift():
    with pytest.raises(SystemExit):
        barriers.check_against_report(report_frame(0.50, 0.194))


def test_every_mapped_column_is_a_flag_in_the_dictionary():
    variables = {
        row["name"]: row for row in pl.read_csv(DATA_DIR / "2024_Finaccess_Publicdata_variables.csv").iter_rows(named=True)
    }
    for product, (_, reasons) in barriers.BARRIERS.items():
        assert set(reasons) <= set(barriers.CATEGORIES), product
        for columns in reasons.values():
            for column in columns:
                assert column in variables, f"{column} ({product}) not in the dictionary"
                assert variables[column]["type"] == "byte", column


def test_no_column_is_mapped_twice():
    mapped = [c for _, reasons in barriers.BARRIERS.values() for cols in reasons.values() for c in cols]
    assert len(mapped) == len(set(mapped))
