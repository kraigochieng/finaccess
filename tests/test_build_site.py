import json
import re

import pytest

from finaccess import build_site


def test_segment_labels_are_made_readable():
    assert build_site.pretty_segment("education", "None") == "No formal education"
    assert build_site.pretty_segment("age_group", "Above 55") == "Over 55"
    # only the intended labels are rewritten
    assert build_site.pretty_segment("county", "Nairobi City") == "Nairobi City"
    assert build_site.pretty_segment("sex", "None") == "None"


def test_render_replaces_the_placeholder_with_parseable_json():
    template = "<script>const DATA = /*__DATA__*/null;</script>"
    page = build_site.render(template, {"a": [1, 2], "b": "x"})
    assert "__DATA__" not in page
    payload = re.search(r"const DATA = (.*);</script>", page).group(1)
    assert json.loads(payload) == {"a": [1, 2], "b": "x"}


def test_render_cannot_be_broken_out_of_by_a_label():
    page = build_site.render("<script>const DATA = /*__DATA__*/null;</script>", {"label": "</script><b>x"})
    # the only closing tag is the template's own
    assert page.count("</script>") == 1
    payload = re.search(r"const DATA = (.*);</script>", page).group(1)
    assert json.loads(payload)["label"] == "</script><b>x"


def test_render_fails_without_a_placeholder():
    with pytest.raises(SystemExit):
        build_site.render("<html></html>", {})


@pytest.fixture(scope="module")
def data():
    return build_site.prepare()


def test_payload_has_every_section_the_page_draws(data):
    assert {"products", "segments", "barriers", "niches", "checks", "labels"} <= set(data)
    assert len(data["niches"]) == 8
    assert {r["universe"] for r in data["products"]} == {"all_adults", "mobile_money_users"}
    assert set(data["barrierProductOrder"]) == set(build_site.BARRIER_PRODUCT_LABELS)


def test_every_metric_and_barrier_the_page_uses_has_a_label(data):
    labels = data["labels"]
    for row in data["products"]:
        assert row["metric"] in labels["products"], row["metric"]
    for row in data["niches"]:
        assert row["product_metric"] in labels["products"]
    for row in data["barriers"]:
        assert row["barrier"] in labels["barriers"]
        assert row["product"] in labels["barrierProducts"]
    for dimension in {r["dimension"] for r in data["segments"]}:
        assert dimension in labels["dimensions"], dimension


def test_no_segment_label_is_missing_or_raw(data):
    labels = {r["segment_label"] for r in data["segments"]} | {r["segment_label"] for r in data["niches"]}
    assert None not in labels
    assert "None" not in labels  # the education segment is shown as "No formal education"
    assert "No formal education" in labels


def test_shares_are_proportions_not_percentages(data):
    for row in data["products"]:
        assert 0 <= row["share_served"] <= 1
    for row in data["barriers"]:
        assert 0 <= row["share_citing"] <= 1


def test_validation_figures_agree_with_the_report(data):
    # these are the numbers the page shows in "How far to trust it"
    for check in data["checks"]:
        assert abs(check["ours"] - check["report"]) <= 1.0, check


def test_the_real_template_has_the_placeholder_exactly_once():
    template = build_site.TEMPLATE.read_text(encoding="utf-8")
    assert template.count(build_site.PLACEHOLDER) == 1
