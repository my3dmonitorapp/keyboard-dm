"""Electrical matrix configuration and layout conversion.

Matrix cells are zero-indexed ``(row, column)`` tuples.  Key widths are stored
as integer half-units so that the model never needs floating-point geometry.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .layout_model import Key, Layout


MATRIX_SCHEMA_VERSION = 1
DEFAULT_MIN_PIN = 0
DEFAULT_MAX_PIN = 39
DEFAULT_WIDTH_HALF_UNITS = 2
MIN_WIDTH_HALF_UNITS = 1
MAX_WIDTH_HALF_UNITS = 25

Cell = tuple[int, int]


class MatrixDataError(ValueError):
    """Raised when serialized matrix data cannot be decoded or validated."""


def _default_pins(count: Any) -> list[None]:
    if type(count) is int and count > 0:
        return [None] * count
    return []


def _is_cell(value: Any) -> bool:
    return (
        isinstance(value, tuple)
        and len(value) == 2
        and type(value[0]) is int
        and type(value[1]) is int
    )


def _cell_key_id(cell: Cell) -> str:
    row, column = cell
    return f"MX-{row:02d}-{column:02d}"


@dataclass
class MatrixConfig:
    """Sparse keyboard matrix, per-key presentation, and GPIO assignments."""

    rows: int
    cols: int
    switches: set[Cell] = field(default_factory=set)
    key_widths: dict[Cell, int] = field(default_factory=dict)
    key_labels: dict[Cell, str] = field(default_factory=dict)
    row_pins: list[int | None] = field(default_factory=list)
    column_pins: list[int | None] = field(default_factory=list)
    min_pin: int = DEFAULT_MIN_PIN
    max_pin: int = DEFAULT_MAX_PIN

    def __post_init__(self) -> None:
        if not self.row_pins:
            self.row_pins = _default_pins(self.rows)
        if not self.column_pins:
            self.column_pins = _default_pins(self.cols)

    def keys(self) -> list[str]:
        """Return stable key IDs for valid populated cells in row-major order."""
        return [_cell_key_id(cell) for cell in self._ordered_cells()]

    def cell_to_key_id(self) -> dict[Cell, str]:
        """Return the populated-cell to stable-key-ID mapping."""
        return {cell: _cell_key_id(cell) for cell in self._ordered_cells()}

    def key_id_for_cell(self, cell: Cell) -> str | None:
        """Return the key ID for a populated cell, or ``None`` if it is empty."""
        return _cell_key_id(cell) if cell in self.switches and _is_cell(cell) else None

    def width_for(self, cell: Cell) -> int:
        """Return a cell's half-unit width, including the 1u default."""
        return self.key_widths.get(cell, DEFAULT_WIDTH_HALF_UNITS)

    def label_for(self, cell: Cell) -> str:
        """Return a cell's display label, including the empty default."""
        return self.key_labels.get(cell, "")

    def _ordered_cells(self) -> list[Cell]:
        if not isinstance(self.switches, (set, frozenset)):
            return []
        return sorted(cell for cell in self.switches if _is_cell(cell))

    def validate(self) -> tuple[bool, list[str]]:
        """Validate all user-controlled values without raising exceptions."""
        errors: list[str] = []
        rows_ok = type(self.rows) is int and 1 <= self.rows <= 32
        cols_ok = type(self.cols) is int and 1 <= self.cols <= 128
        if not rows_ok:
            errors.append("Matrix rows must be an integer from 1 to 32")
        if not cols_ok:
            errors.append("Matrix columns must be an integer from 1 to 128")

        if not isinstance(self.switches, (set, frozenset)):
            errors.append("Matrix switches must be a set of (row, column) cells")
            cells: list[Cell] = []
        else:
            cells = []
            for cell in self.switches:
                if not _is_cell(cell):
                    errors.append(f"Invalid matrix cell {cell!r}; expected (row, column)")
                    continue
                cells.append(cell)
                row, column = cell
                if rows_ok and cols_ok and not (
                    0 <= row < self.rows and 0 <= column < self.cols
                ):
                    errors.append(
                        f"Matrix cell ({row}, {column}) is outside "
                        f"{self.rows}x{self.cols} bounds"
                    )

        cell_set = set(cells)
        self._validate_key_values(self.key_widths, self.key_labels, cell_set, errors)
        self._validate_pin_range(errors)
        self._validate_pin_list("row", self.row_pins, self.rows, errors)
        self._validate_pin_list("column", self.column_pins, self.cols, errors)
        self._validate_unique_pins(errors)
        return not errors, errors

    def _validate_key_values(
        self,
        widths: Any,
        labels: Any,
        cells: set[Cell],
        errors: list[str],
    ) -> None:
        if not isinstance(widths, dict):
            errors.append("Matrix key widths must be a cell-to-width mapping")
        else:
            for cell, width in widths.items():
                if not _is_cell(cell) or cell not in cells:
                    errors.append(f"Width is assigned to non-populated cell {cell!r}")
                if type(width) is not int or not (
                    MIN_WIDTH_HALF_UNITS <= width <= MAX_WIDTH_HALF_UNITS
                ):
                    errors.append(
                        f"Width for cell {cell!r} must be an integer from 1 to 25 "
                        "half-units"
                    )
        if not isinstance(labels, dict):
            errors.append("Matrix key labels must be a cell-to-label mapping")
        else:
            for cell, label in labels.items():
                if not _is_cell(cell) or cell not in cells:
                    errors.append(f"Label is assigned to non-populated cell {cell!r}")
                if not isinstance(label, str):
                    errors.append(f"Label for cell {cell!r} must be a string")

    def _validate_pin_range(self, errors: list[str]) -> None:
        if (
            type(self.min_pin) is not int
            or type(self.max_pin) is not int
            or self.min_pin > self.max_pin
        ):
            errors.append("Matrix pin range must contain integer min/max values in order")

    def _validate_pin_list(
        self, name: str, pins: Any, expected_count: Any, errors: list[str]
    ) -> None:
        if not isinstance(pins, list):
            errors.append(f"Matrix {name} pins must be a list")
            return
        if type(expected_count) is int and len(pins) != expected_count:
            errors.append(
                f"Matrix {name} pins must contain {expected_count} entries; "
                f"found {len(pins)}"
            )
        range_ok = type(self.min_pin) is int and type(self.max_pin) is int
        for index, pin in enumerate(pins):
            if pin is None:
                continue
            if type(pin) is not int:
                errors.append(f"Matrix {name} pin {index} must be an integer or null")
            elif range_ok and not self.min_pin <= pin <= self.max_pin:
                errors.append(
                    f"Matrix {name} pin {index} ({pin}) is outside allowed range "
                    f"{self.min_pin}..{self.max_pin}"
                )

    def _validate_unique_pins(self, errors: list[str]) -> None:
        seen: dict[int, str] = {}
        for name, pins in (("row", self.row_pins), ("column", self.column_pins)):
            if not isinstance(pins, list):
                continue
            for index, pin in enumerate(pins):
                if type(pin) is not int:
                    continue
                location = f"{name} {index}"
                if pin in seen:
                    errors.append(
                        f"GPIO pin {pin} is assigned more than once "
                        f"({seen[pin]} and {location})"
                    )
                else:
                    seen[pin] = location

    def to_dict(self) -> dict[str, Any]:
        """Return a stable, JSON-compatible matrix representation."""
        return {
            "matrix_schema_version": MATRIX_SCHEMA_VERSION,
            "rows": self.rows,
            "cols": self.cols,
            "switches": [list(cell) for cell in self._ordered_cells()],
            "key_widths": {
                _cell_key_id(cell): self.key_widths[cell]
                for cell in self._ordered_cells()
                if cell in self.key_widths
            },
            "key_labels": {
                _cell_key_id(cell): self.key_labels[cell]
                for cell in self._ordered_cells()
                if cell in self.key_labels
            },
            "row_pins": list(self.row_pins) if isinstance(self.row_pins, list) else [],
            "column_pins": (
                list(self.column_pins) if isinstance(self.column_pins, list) else []
            ),
            "min_pin": self.min_pin,
            "max_pin": self.max_pin,
        }

    @classmethod
    def from_dict(cls, data: Any) -> MatrixConfig:
        """Decode matrix data, defaulting fields added within schema version 1."""
        if not isinstance(data, dict):
            raise MatrixDataError("Matrix data must be a JSON object")
        version = data.get("matrix_schema_version", MATRIX_SCHEMA_VERSION)
        if type(version) is not int or version != MATRIX_SCHEMA_VERSION:
            raise MatrixDataError(
                f"Unsupported matrix_schema_version {version!r}; "
                f"expected {MATRIX_SCHEMA_VERSION}"
            )
        rows = data.get("rows")
        cols = data.get("cols")
        raw_switches = data.get("switches", [])
        if not isinstance(raw_switches, list):
            raise MatrixDataError("Matrix field 'switches' must be a list")
        switches: set[Cell] = set()
        for item in raw_switches:
            if (
                not isinstance(item, (list, tuple))
                or len(item) != 2
                or type(item[0]) is not int
                or type(item[1]) is not int
            ):
                raise MatrixDataError(
                    f"Invalid serialized matrix cell {item!r}; expected [row, column]"
                )
            switches.add((item[0], item[1]))

        widths = cls._decode_key_mapping(data.get("key_widths", {}), "key_widths")
        labels = cls._decode_key_mapping(data.get("key_labels", {}), "key_labels")
        config = cls(
            rows=rows,
            cols=cols,
            switches=switches,
            key_widths=widths,
            key_labels=labels,
            row_pins=data.get("row_pins", _default_pins(rows)),
            column_pins=data.get("column_pins", _default_pins(cols)),
            min_pin=data.get("min_pin", DEFAULT_MIN_PIN),
            max_pin=data.get("max_pin", DEFAULT_MAX_PIN),
        )
        ok, errors = config.validate()
        if not ok:
            raise MatrixDataError("Invalid matrix data: " + "; ".join(errors))
        return config

    @staticmethod
    def _decode_key_mapping(data: Any, field_name: str) -> dict[Cell, Any]:
        if not isinstance(data, dict):
            raise MatrixDataError(f"Matrix field {field_name!r} must be an object")
        result: dict[Cell, Any] = {}
        for key_id, value in data.items():
            if not isinstance(key_id, str):
                raise MatrixDataError(f"Matrix {field_name} keys must be strings")
            parts = key_id.split("-")
            try:
                if len(parts) != 3 or parts[0] != "MX":
                    raise ValueError
                cell = (int(parts[1]), int(parts[2]))
            except ValueError as error:
                raise MatrixDataError(
                    f"Invalid matrix key ID {key_id!r} in {field_name}"
                ) from error
            if _cell_key_id(cell) != key_id:
                raise MatrixDataError(
                    f"Matrix key ID {key_id!r} is not in canonical form"
                )
            result[cell] = value
        return result

    def to_layout(self, name: str = "Matrix") -> Layout:
        """Build the existing layout geometry representation for this matrix."""
        return matrix_layout(self, name=name)


def matrix_layout(config: MatrixConfig, name: str = "Matrix") -> Layout:
    """Convert populated matrix cells to row-major ``Key`` geometry.

    Positions remain matrix grid coordinates.  ``Key.w`` contains integer
    half-units for matrix layouts; consumers can render it using a 0.5u scale.
    """
    return Layout(
        name=name,
        label="matrix",
        cols=config.cols,
        rows=config.rows,
        keys=[
            Key(
                key_id=_cell_key_id(cell),
                x=cell[1],
                y=cell[0],
                w=config.width_for(cell),
            )
            for cell in config._ordered_cells()
        ],
    )
