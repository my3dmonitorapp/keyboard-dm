"""Tests for built-in and custom keyboard layouts."""

import pytest

from desktop_app.layout_model import Layout, PROVISIONAL_75_LAYOUT
from desktop_app.layouts import L06, L09, L12, L75, make_custom_layout


def _assert_layout(layout: Layout, count: int, cols: int, rows: int) -> None:
    assert layout.key_count == count
    assert layout.cols == cols
    assert layout.rows == rows
    assert [key.key_id for key in layout.keys] == [
        f"K{number:02d}" for number in range(1, count + 1)
    ]


def test_l06_has_six_stable_row_major_keys() -> None:
    _assert_layout(L06, 6, 3, 2)


def test_l09_has_nine_stable_row_major_keys() -> None:
    _assert_layout(L09, 9, 3, 3)


def test_l12_has_twelve_stable_row_major_keys() -> None:
    _assert_layout(L12, 12, 4, 3)


def test_l75_has_seventy_five_stable_row_major_keys() -> None:
    _assert_layout(L75, 75, 15, 5)
    assert L75 is PROVISIONAL_75_LAYOUT
    assert "PROVISIONAL" in L75.label


def test_provisional_layout_has_exactly_75_keys() -> None:
    assert len(PROVISIONAL_75_LAYOUT.keys) == 75
    assert all(key.assignment == "NONE" for key in PROVISIONAL_75_LAYOUT.keys)


def test_key_ids_are_unique_and_complete() -> None:
    key_ids = [key.key_id for key in PROVISIONAL_75_LAYOUT.keys]

    assert len(key_ids) == len(set(key_ids))
    assert key_ids == [f"K{number:02d}" for number in range(1, 76)]


def test_provisional_grid_geometry_is_valid() -> None:
    for index, key in enumerate(PROVISIONAL_75_LAYOUT.keys):
        expected_row, expected_column = divmod(index, 15)
        assert (key.x, key.y) == (expected_column, expected_row)
        assert (key.w, key.h) == (1, 1)


def test_layout_serialization_round_trip() -> None:
    serialized = PROVISIONAL_75_LAYOUT.to_dict()

    assert serialized["label"].startswith("PROVISIONAL")
    assert Layout.from_dict(serialized) == PROVISIONAL_75_LAYOUT


def test_custom_layout_derives_grid_and_stable_ids() -> None:
    layout = make_custom_layout(10)

    _assert_layout(layout, 10, 4, 3)
    assert [(key.x, key.y) for key in layout.keys] == [
        (index % 4, index // 4) for index in range(10)
    ]


def test_custom_layout_derives_missing_dimension() -> None:
    three_columns = make_custom_layout(11, cols=3)
    two_rows = make_custom_layout(11, rows=2)

    assert (three_columns.cols, three_columns.rows) == (3, 4)
    assert (two_rows.cols, two_rows.rows) == (6, 2)


@pytest.mark.parametrize("count", [1, 501, True, 2.5])
def test_custom_layout_rejects_invalid_key_count(count: object) -> None:
    with pytest.raises(ValueError, match="key count"):
        make_custom_layout(count)  # type: ignore[arg-type]


def test_custom_layout_rejects_grid_that_is_too_small() -> None:
    with pytest.raises(ValueError, match="has only 9 cells for 10 keys"):
        make_custom_layout(10, cols=3, rows=3)
