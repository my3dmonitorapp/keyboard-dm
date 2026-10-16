"""Keyboard layout data model.

Stable key IDs are independent of the physical positions represented by a
layout.  The 75-key arrangement remains explicitly provisional.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class Key:
    """One key in a keyboard layout, measured in keyboard units."""

    key_id: str
    x: int
    y: int
    w: int | float = 1
    h: int = 1
    assignment: str = "NONE"
    label: str = ""
    # Matrix-only visual offsets, stored in integer half-unit increments.  The
    # electrical x/y coordinates remain untouched.
    dx: int = 0
    dy: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible representation of this key."""
        data = {
            "key_id": self.key_id,
            "x": self.x,
            "y": self.y,
            "w": self.w,
            "h": self.h,
            "assignment": self.assignment,
            "label": self.label,
        }
        if self.dx or self.dy:
            data["dx"] = self.dx
            data["dy"] = self.dy
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Key:
        """Create a key from its serialized representation."""
        return cls(
            key_id=data["key_id"],
            x=data["x"],
            y=data["y"],
            w=data["w"],
            h=data["h"],
            assignment=data["assignment"],
            label=data.get("label", ""),
            dx=data.get("dx", 0),
            dy=data.get("dy", 0),
        )


@dataclass
class Layout:
    """A labeled collection of keys."""

    label: str
    keys: list[Key]
    name: str = ""
    cols: int = 0
    rows: int = 0

    @property
    def key_count(self) -> int:
        """Return the number of keys in this layout."""
        return len(self.keys)

    def render_keys(self) -> list[Key]:
        """Return visible keys after resolving matrix-key occlusion.

        Wider and explicitly positioned caps take precedence.  A lower-priority
        cap that intersects one of them is omitted from the render plan, while
        remaining keys and their stable electrical IDs stay in ``keys``.
        """
        if self.label != "matrix":
            return list(self.keys)

        indexed = list(enumerate(self.keys))
        priority = sorted(
            indexed,
            key=lambda item: (
                bool(item[1].dx or item[1].dy),
                item[1].w,
                item[1].w * item[1].h,
                item[0],
            ),
            reverse=True,
        )
        visible: list[tuple[int, Key]] = []
        occupied: list[tuple[int, int, int, int]] = []
        for index, key in priority:
            rectangle = (
                key.x * 4 + key.dx * 2,
                key.y * 2 + key.dy,
                round(key.w * 2),
                key.h * 2,
            )
            left, top, width, height = rectangle
            intersects = any(
                left < other_left + other_width
                and other_left < left + width
                and top < other_top + other_height
                and other_top < top + height
                for other_left, other_top, other_width, other_height in occupied
            )
            if not intersects:
                visible.append((index, key))
                occupied.append(rectangle)
        return [key for _index, key in sorted(visible)]

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible representation of this layout."""
        return {
            "name": self.name,
            "key_count": self.key_count,
            "cols": self.cols,
            "rows": self.rows,
            "label": self.label,
            "keys": [key.to_dict() for key in self.keys],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Layout:
        """Create a layout from its serialized representation."""
        return cls(
            label=data["label"],
            keys=[Key.from_dict(key_data) for key_data in data["keys"]],
            name=data.get("name", ""),
            cols=data.get("cols", 0),
            rows=data.get("rows", 0),
        )


PROVISIONAL_75_LAYOUT = Layout(
    name="L75",
    cols=15,
    rows=5,
    label="PROVISIONAL — physical key arrangement is not final",
    keys=[
        Key(key_id=f"K{row * 15 + column + 1:02d}", x=column, y=row)
        for row in range(5)
        for column in range(15)
    ],
)
"""PROVISIONAL 5x15 layout; this is not the final physical arrangement."""
