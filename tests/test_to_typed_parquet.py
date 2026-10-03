import duckdb
import polars as pl
import pytest

from finaccess import to_typed_parquet as typed


def var(type_="byte", isnumeric=1, vallab=None):
    return {"type": type_, "isnumeric": isnumeric, "vallab": vallab}


def test_unlabelled_numeric_columns_are_cast_candidates():
    assert typed.classify(var("byte")) == ("cast_candidate", "TINYINT")
    assert typed.classify(var("int")) == ("cast_candidate", "SMALLINT")
    assert typed.classify(var("long")) == ("cast_candidate", "INTEGER")
    assert typed.classify(var("double")) == ("cast_candidate", "DOUBLE")


def test_labelled_columns_stay_strings_even_when_numeric():
    assert typed.classify(var("byte", vallab="county")) == ("kept_string_labelled", "VARCHAR")


def test_text_and_unsupported_columns_stay_strings():
    assert typed.classify(var("strL", isnumeric=0)) == ("kept_string_text", "VARCHAR")
    assert typed.classify(var("float")) == ("kept_string_unsupported_type", "VARCHAR")


def test_a_candidate_becomes_a_cast_only_if_every_value_casts():
    clean = {"status": "cast_candidate", "target_type": "TINYINT", "cast_failures": 0}
    typed.resolve(clean)
    assert (clean["status"], clean["target_type"]) == ("cast", "TINYINT")

    dirty = {"status": "cast_candidate", "target_type": "TINYINT", "cast_failures": 3}
    typed.resolve(dirty)
    assert (dirty["status"], dirty["target_type"]) == ("kept_string_cast_failed", "VARCHAR")

    text = {"status": "kept_string_text", "target_type": "VARCHAR", "cast_failures": 0}
    typed.resolve(text)
    assert text["status"] == "kept_string_text"


def test_select_expression_nulls_the_sentinel_and_casts_only_when_told():
    kept = {"name": "note", "status": "kept_string_text", "target_type": "VARCHAR"}
    assert typed.select_expression(kept) == "NULLIF(\"note\", '#NULL!') AS \"note\""

    cast = {"name": "flag", "status": "cast", "target_type": "TINYINT"}
    assert typed.select_expression(cast) == (
        "TRY_CAST(NULLIF(\"flag\", '#NULL!') AS TINYINT) AS \"flag\""
    )


def test_quote_escapes_double_quotes():
    assert typed.quote('we"ird') == '"we""ird"'


def test_batches_split_a_list():
    assert list(typed.batches(list(range(250)))) == [
        list(range(100)),
        list(range(100, 200)),
        list(range(200, 250)),
    ]


@pytest.fixture
def paths(tmp_path, monkeypatch):
    source = tmp_path / "source.parquet"
    variables = tmp_path / "variables.csv"
    target = tmp_path / "typed.parquet"
    monkeypatch.setattr(typed, "SOURCE", source)
    monkeypatch.setattr(typed, "VARIABLES", variables)
    monkeypatch.setattr(typed, "TARGET", target)

    pl.DataFrame(
        {
            "interview__id": ["a", "b", "c", "d"],
            "flag": ["1", "0", "#NULL!", "1"],
            "amount": ["1.5", "#NULL!", "2", "3.25"],
            "bad_numeric": ["1", "x", "2", "3"],
            "sex": ["Male", "Female", "#NULL!", "Male"],
            "note": ["hello", "", "#NULL!", ""],
        }
    ).write_parquet(source)
    pl.DataFrame(
        {
            "name": ["interview__id", "flag", "amount", "bad_numeric", "sex", "note"],
            "type": ["str32", "byte", "double", "byte", "byte", "strL"],
            "isnumeric": [0, 1, 1, 1, 1, 0],
            "vallab": [None, None, None, None, "sex", None],
        }
    ).write_csv(variables)
    return target


@pytest.fixture
def built(paths):
    con = duckdb.connect()
    plan = typed.plan_columns(con)
    typed.write_typed(con, plan)
    return con, plan, paths


def test_plan_assigns_the_expected_status_to_each_column(built):
    _, plan, _ = built
    status = dict(zip(plan["name"], plan["status"]))
    assert status == {
        "interview__id": "kept_string_text",
        "flag": "cast",
        "amount": "cast",
        "bad_numeric": "kept_string_cast_failed",
        "sex": "kept_string_labelled",
        "note": "kept_string_text",
    }
    counts = dict(zip(plan["name"], plan["not_asked_count"]))
    assert counts["flag"] == 1 and counts["sex"] == 1 and counts["interview__id"] == 0


def test_typed_file_has_real_types_and_nulls(built):
    con, _, target = built
    types = {row[0]: row[1] for row in con.execute(f"DESCRIBE SELECT * FROM '{target}'").fetchall()}
    assert types["flag"] == "TINYINT"
    assert types["amount"] == "DOUBLE"
    assert types["bad_numeric"] == "VARCHAR"
    assert types["sex"] == "VARCHAR"

    flags = [r[0] for r in con.execute(f"SELECT flag FROM '{target}' ORDER BY interview__id").fetchall()]
    assert flags == [1, 0, None, 1]


def test_empty_text_stays_empty_while_the_sentinel_becomes_null(built):
    con, _, target = built
    notes = [r[0] for r in con.execute(f"SELECT note FROM '{target}' ORDER BY interview__id").fetchall()]
    assert notes == ["hello", "", None, ""]


def test_verify_passes_on_a_correct_build(built):
    con, plan, _ = built
    typed.verify(con, plan)


def test_verify_fails_when_a_value_is_changed(built):
    con, plan, target = built
    tampered = con.execute(f"SELECT * FROM '{target}'").pl()
    tampered = tampered.with_columns(
        pl.when(pl.col("interview__id") == "a").then(0).otherwise(pl.col("flag")).alias("flag")
    )
    tampered.write_parquet(target)
    with pytest.raises(SystemExit):
        typed.verify(con, plan)


def test_plan_fails_when_a_column_is_missing_from_the_dictionary(paths):
    pl.DataFrame({"name": ["interview__id"], "type": ["str32"], "isnumeric": [0], "vallab": [None]}).write_csv(
        typed.VARIABLES
    )
    with pytest.raises(SystemExit):
        typed.plan_columns(duckdb.connect())
