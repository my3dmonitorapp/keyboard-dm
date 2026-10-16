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
    w: int = 1
    h: int = 1
    assignment: str = "NONE"
    label: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible representation of this key."""
        return {
            "key_id": self.key_id,
            "x": self.x,
            "y": self.y,
            "w": self.w,
            "h": self.h,
            "assignment": self.assignment,
            "label": self.label,
        }

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
