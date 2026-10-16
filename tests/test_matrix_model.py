"""Tests for sparse electrical matrix configuration."""

import pytest

from desktop_app.matrix_model import (
    WIDTH_PRESETS_HALF_UNITS,
    MatrixConfig,
    MatrixDataError,
    matrix_layout,
)


def test_valid_config_has_stable_row_major_keys_and_geometry() -> None:
    config = MatrixConfig(
        rows=2,
        cols=3,
        switches={(1, 2), (0, 0), (0, 2)},
        row_pins=[1, 2],
        column_pins=[3, 4, 5],
    )

    assert config.validate() == (True, [])
    assert config.keys() == ["MX-00-00", "MX-00-02", "MX-01-02"]
    assert config.cell_to_key_id() == {
        (0, 0): "MX-00-00",
        (0, 2): "MX-00-02",
        (1, 2): "MX-01-02",
    }
    layout = matrix_layout(config)
    assert [(key.key_id, key.x, key.y, key.w) for key in layout.keys] == [
        ("MX-00-00", 0, 0, 2),
        ("MX-00-02", 2, 0, 2),
        ("MX-01-02", 2, 1, 2),
    ]


def test_sparse_matrix_allows_empty_rows() -> None:
    config = MatrixConfig(rows=4, cols=3, switches={(0, 1), (3, 2)})

    assert config.validate() == (True, [])
    assert config.keys() == ["MX-00-01", "MX-03-02"]


def test_per_key_width_and_label_edits() -> None:
    config = MatrixConfig(rows=1, cols=2, switches={(0, 0), (0, 1)})
    config.key_widths[(0, 1)] = 5
    config.key_labels[(0, 1)] = "Space"

    assert config.width_for((0, 0)) == 2
    assert config.width_for((0, 1)) == 5
    assert config.label_for((0, 0)) == ""
    assert config.label_for((0, 1)) == "Space"
    assert config.to_layout().keys[1].w == 5
    assert config.validate() == (True, [])


def test_width_presets_include_full_required_set() -> None:
    widths_u = {half_units / 2 for half_units in WIDTH_PRESETS_HALF_UNITS}

    assert {1, 1.25, 1.5, 1.75, 2, 2.25, 2.5, 2.75, 6.25} <= widths_u


def test_spacebar_render_plan_occludes_all_six_underlying_cells() -> None:
    config = MatrixConfig(
        rows=1,
        cols=6,
        switches={(0, column) for column in range(6)},
        key_widths={(0, 0): 12.5},
        key_labels={(0, 0): "Space"},
    )

    layout = config.to_layout()

    assert [key.key_id for key in layout.render_keys()] == ["MX-00-00"]
    assert layout.render_keys()[0].label == "Space"
    assert layout.key_count == 6


def test_visual_offset_does_not_change_key_id_or_electrical_mapping() -> None:
    cell = (1, 2)
    config = MatrixConfig(
        rows=2,
        cols=3,
        switches={cell},
        key_visual_offsets={cell: (-1, 3)},
    )

    key = config.to_layout().keys[0]

    assert (key.key_id, key.x, key.y) == ("MX-01-02", 2, 1)
    assert (key.dx, key.dy) == (-1, 3)
    assert config.cell_to_key_id() == {cell: "MX-01-02"}


@pytest.mark.parametrize(
    ("row_pins", "column_pins"),
    [([7, 7], [None]), ([7, None], [7])],
)
def test_duplicate_gpio_pin_is_rejected(row_pins, column_pins) -> None:
    config = MatrixConfig(
        rows=2,
        cols=1,
        switches={(0, 0)},
        row_pins=row_pins,
        column_pins=column_pins,
    )

    ok, errors = config.validate()

    assert not ok
    assert any("GPIO pin 7 is assigned more than once" in error for error in errors)


def test_out_of_range_gpio_pin_is_rejected() -> None:
    config = MatrixConfig(rows=1, cols=1, row_pins=[40])

    ok, errors = config.validate()

    assert not ok
    assert any("outside allowed range 0..39" in error for error in errors)


@pytest.mark.parametrize(
    ("rows", "cols"),
    [(0, 1), (33, 1), (1, 0), (1, 129), (True, 2)],
)
def test_out_of_range_matrix_size_is_rejected(rows, cols) -> None:
    ok, errors = MatrixConfig(rows=rows, cols=cols).validate()

    assert not ok
    assert errors


def test_serialization_round_trip() -> None:
    config = MatrixConfig(
        rows=2,
        cols=3,
        switches={(0, 0), (1, 2)},
        key_widths={(1, 2): 5},
        key_labels={(0, 0): "Esc", (1, 2): "Space"},
        key_visual_offsets={(0, 0): (1, -2)},
        row_pins=[10, 11],
        column_pins=[20, 21, 22],
    )

    serialized = config.to_dict()

    assert serialized["matrix_schema_version"] == 1
    assert MatrixConfig.from_dict(serialized) == config


def test_from_dict_defaults_missing_optional_fields() -> None:
    config = MatrixConfig.from_dict({"rows": 2, "cols": 3, "switches": [[1, 2]]})

    assert config.key_widths == {}
    assert config.key_labels == {}
    assert config.key_visual_offsets == {}
    assert config.row_pins == [None, None]
    assert config.column_pins == [None, None, None]
    assert config.width_for((1, 2)) == 2
    assert config.label_for((1, 2)) == ""
    assert config.visual_offset_for((1, 2)) == (0, 0)


def test_from_dict_reports_bad_data_clearly() -> None:
    with pytest.raises(MatrixDataError, match="outside 2x2 bounds"):
        MatrixConfig.from_dict({"rows": 2, "cols": 2, "switches": [[2, 0]]})


def test_validation_does_not_raise_for_malformed_user_values() -> None:
    config = MatrixConfig(rows="two", cols=2)  # type: ignore[arg-type]
    config.row_pins = "GPIO1"  # type: ignore[assignment]

    ok, errors = config.validate()

    assert not ok
    assert len(errors) >= 2
