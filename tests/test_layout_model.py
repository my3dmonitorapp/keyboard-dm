"""Tests for the provisional Keyboard75 layout model."""

from desktop_app.layout_model import Layout, PROVISIONAL_75_LAYOUT


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

    assert serialized["label"] == "PROVISIONAL"
    assert Layout.from_dict(serialized) == PROVISIONAL_75_LAYOUT
