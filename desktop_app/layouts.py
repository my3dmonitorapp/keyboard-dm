"""Built-in and custom keyboard layouts for the desktop application."""

from __future__ import annotations

from math import ceil, sqrt

from .layout_model import Key, Layout, PROVISIONAL_75_LAYOUT


BUILT_IN_LABEL = "built-in"


def _make_grid_layout(
    name: str,
    count: int,
    cols: int,
    rows: int,
    label: str,
) -> Layout:
    return Layout(
        name=name,
        label=label,
        cols=cols,
        rows=rows,
        keys=[
            Key(key_id=f"K{index + 1:02d}", x=index % cols, y=index // cols)
            for index in range(count)
        ],
    )


L06 = _make_grid_layout("L06", 6, 3, 2, BUILT_IN_LABEL)
L09 = _make_grid_layout("L09", 9, 3, 3, BUILT_IN_LABEL)
L12 = _make_grid_layout("L12", 12, 4, 3, BUILT_IN_LABEL)
L75 = PROVISIONAL_75_LAYOUT

BUILT_IN_LAYOUTS = (L06, L09, L12, L75)
BUILT_IN_LAYOUTS_BY_NAME = {layout.name: layout for layout in BUILT_IN_LAYOUTS}


def _validate_dimension(value: int | None, name: str) -> None:
    if value is not None and (type(value) is not int or value < 1):
        raise ValueError(f"Custom layout {name} must be a positive integer")


def make_custom_layout(
    count: int, cols: int | None = None, rows: int | None = None
) -> Layout:
    """Create a row-major custom grid containing ``K01`` through ``KN``.

    A missing dimension is derived from the supplied dimension and key count.
    When both dimensions are omitted, a compact, approximately square grid is
    selected. Explicit dimensions must provide enough cells for every key.
    """
    if type(count) is not int:
        raise ValueError("Custom layout key count must be an integer from 2 to 500")
    if not 2 <= count <= 500:
        raise ValueError("Custom layout key count must be from 2 to 500")
    _validate_dimension(cols, "column count")
    _validate_dimension(rows, "row count")

    if cols is None and rows is None:
        cols = ceil(sqrt(count))
        rows = ceil(count / cols)
    elif cols is None:
        assert rows is not None
        cols = ceil(count / rows)
    elif rows is None:
        rows = ceil(count / cols)
    elif cols * rows < count:
        raise ValueError(
            f"Custom layout grid {cols}x{rows} has only {cols * rows} cells "
            f"for {count} keys"
        )

    return _make_grid_layout("Custom", count, cols, rows, "custom")
