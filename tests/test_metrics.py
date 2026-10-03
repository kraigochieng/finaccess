import polars as pl
import pytest

from finaccess import metrics

SERVED = {
    "Overall_Access_fnl": "formal only",
    "formal_access_fnl": "Yes",
    "mobile_money_access": "Yes",
    "bank_usage_overall": "Usage",
    "Savings_usage": "Usage",
    "Loan_usage": "Usage",
    "Digital_credit_usage": "Usage",
    "Digital_credit_2": "Usage",
    "All_Insurance_including_NHIF": "Usage",
    "Pension_usage": "Usage",
    "Sacco_usage": "Usage",
}
NOT_SERVED = {
    "Overall_Access_fnl": "excluded",
    "formal_access_fnl": "No",
    "mobile_money_access": "No",
    "bank_usage_overall": "Non-usage",
    "Savings_usage": "Non-usage",
    "Loan_usage": "Non-usage",
    "Digital_credit_usage": "Non-usage",
    "Digital_credit_2": "Non-usage",
    "All_Insurance_including_NHIF": "Non-usage",
    "Pension_usage": "Non-usage",
    "Sacco_usage": "Non-usage",
}


def person(weight, age, county, sex, education, indicators, **overrides):
    return {
        "indWeight": weight,
        "Age": age,
        "county": county,
        "Sex": sex,
        "A20": education,
        **indicators,
        **overrides,
    }


@pytest.fixture
def synthetic(tmp_path, monkeypatch):
    rows = [
        person(100.0, "18-25", "A", "Male", '"None "', SERVED),
        person(300.0, "26-35", "A", "Female", "Primary", NOT_SERVED),
        # 16-17 year olds are not adults and must be ignored
        person(600.0, "16-17", "A", "Male", "Primary", NOT_SERVED),
        # informal-only counts as served for any_access; bank is unknown
        person(
            100.0, "18-25", "B", "Female", "Primary", SERVED,
            Overall_Access_fnl="informal only", bank_usage_overall=None,
        ),
    ]
    path = tmp_path / "typed.parquet"
    pl.DataFrame(rows).write_parquet(path)
    monkeypatch.setattr(metrics, "SOURCE", path)
    return metrics.compute()


def row(result, universe, metric, dimension, segment):
    return result.filter(
        (pl.col("universe") == universe)
        & (pl.col("metric") == metric)
        & (pl.col("dimension") == dimension)
        & (pl.col("segment") == segment)
    ).row(0, named=True)


def test_broad_and_narrow_digital_credit_are_separate_indicators(tmp_path, monkeypatch):
    rows = [
        # uses a Hustler-type loan but no lending app
        person(100.0, "18-25", "A", "Male", "Primary", SERVED, Digital_credit_usage="Non-usage"),
        person(100.0, "18-25", "A", "Male", "Primary", NOT_SERVED),
    ]
    path = tmp_path / "typed.parquet"
    pl.DataFrame(rows).write_parquet(path)
    monkeypatch.setattr(metrics, "SOURCE", path)
    result = metrics.compute()

    assert row(result, "all_adults", "digital_credit", "all", "All")["share_served"] == pytest.approx(0.5)
    assert row(result, "all_adults", "digital_apps", "all", "All")["share_served"] == 0.0


def test_output_order_is_stable(synthetic):
    keys = ["universe", "metric", "dimension", "segment"]
    assert synthetic.equals(synthetic.sort(keys))


def test_children_are_excluded_from_adults(synthetic):
    national = row(synthetic, "all_adults", "any_access", "all", "All")
    assert national["n"] == 3
    assert national["adults"] == 500.0


def test_share_is_weighted_not_a_head_count(synthetic):
    # served: 100 (formal only) + 100 (informal only) of 500 weighted adults
    national = row(synthetic, "all_adults", "any_access", "all", "All")
    assert national["adults_served"] == 200.0
    assert national["share_served"] == pytest.approx(0.4)
    assert national["unserved_adults"] == pytest.approx(300.0)


def test_rows_with_a_null_indicator_are_left_out_of_that_metric(synthetic):
    bank = row(synthetic, "all_adults", "bank", "all", "All")
    assert bank["adults"] == 400.0
    assert bank["share_served"] == pytest.approx(0.25)


def test_mobile_money_users_universe(synthetic):
    users = row(synthetic, "mobile_money_users", "savings", "all", "All")
    assert users["adults"] == 200.0
    assert users["share_served"] == pytest.approx(1.0)


def test_gap_is_measured_against_the_national_share(synthetic):
    male = row(synthetic, "all_adults", "any_access", "sex", "Male")
    # the only adult man is served: 100% vs a 40% national share
    assert male["share_served"] == pytest.approx(1.0)
    assert male["gap_pp"] == pytest.approx(60.0)


def test_education_labels_are_cleaned_and_none_survives(synthetic):
    segments = synthetic.filter(pl.col("dimension") == "education")["segment"].to_list()
    assert "None" in segments
    assert not any('"' in segment for segment in segments)


def test_small_segments_are_flagged(synthetic):
    small = row(synthetic, "all_adults", "any_access", "county", "B")
    assert small["n"] == 1
    assert small["low_confidence"] is True


def test_report_check_passes_on_matching_figures():
    metrics.check_against_report(report_frame(formal=0.848, any_access=0.901))


def test_report_check_fails_when_figures_drift():
    with pytest.raises(SystemExit):
        metrics.check_against_report(report_frame(formal=0.786, any_access=0.901))


def report_frame(formal, any_access, bank_users=14.8e6):
    national = {"universe": "all_adults", "dimension": "all"}
    return pl.DataFrame(
        [
            {**national, "metric": "formal_access", "share_served": formal, "adults_served": 0.0},
            {**national, "metric": "any_access", "share_served": any_access, "adults_served": 0.0},
            {**national, "metric": "bank", "share_served": 0.5, "adults_served": bank_users},
        ]
    )
