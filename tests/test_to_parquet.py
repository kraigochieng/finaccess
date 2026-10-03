import pyarrow.parquet as pq
import pytest
from openpyxl import Workbook

from finaccess.to_parquet import convert_excel_to_parquet_optimized


def write_workbook(path, rows):
    workbook = Workbook()
    sheet = workbook.active
    for row in rows:
        sheet.append(row)
    workbook.save(path)


def test_converts_every_cell_to_a_string_and_cleans_the_header(tmp_path):
    xlsx = tmp_path / "data.xlsx"
    parquet = tmp_path / "data.parquet"
    write_workbook(
        xlsx,
        [
            ["interview id", "A07", None],
            ["a", 12, "x"],
            ["b", None, "y"],
            ["c", 3.5, None],
        ],
    )

    convert_excel_to_parquet_optimized(str(xlsx), str(parquet), chunk_size=2)

    table = pq.read_table(parquet)
    # spaces become underscores and an unnamed column gets a positional name
    assert table.column_names == ["interview_id", "A07", "col_2"]
    assert {str(t) for t in table.schema.types} == {"string"}
    # empty cells are empty strings, not nulls, and numbers keep their text form
    assert table.column("A07").to_pylist() == ["12", "", "3.5"]
    assert table.column("col_2").to_pylist() == ["x", "y", ""]
    assert table.num_rows == 3


def test_rejects_duplicate_header_names(tmp_path):
    xlsx = tmp_path / "data.xlsx"
    write_workbook(xlsx, [["a", "a"], [1, 2]])
    with pytest.raises(ValueError):
        convert_excel_to_parquet_optimized(str(xlsx), str(tmp_path / "out.parquet"))
