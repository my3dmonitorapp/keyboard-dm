"""Keyboard layout data model.

The physical arrangement represented here is explicitly PROVISIONAL. Stable key
IDs are independent of the positions that may be chosen for a later layout.
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

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible representation of this key."""
        return {
            "key_id": self.key_id,
            "x": self.x,
            "y": self.y,
            "w": self.w,
            "h": self.h,
            "assignment": self.assignment,
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
        )


@dataclass
class Layout:
    """A labeled collection of keys."""

    label: str
    keys: list[Key]

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible representation of this layout."""
        return {
            "label": self.label,
            "keys": [key.to_dict() for key in self.keys],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Layout:
        """Create a layout from its serialized representation."""
        return cls(
            label=data["label"],
            keys=[Key.from_dict(key_data) for key_data in data["keys"]],
        )


PROVISIONAL_75_LAYOUT = Layout(
    label="PROVISIONAL",
    keys=[
        Key(key_id=f"K{row * 15 + column + 1:02d}", x=column, y=row)
        for row in range(5)
        for column in range(15)
    ],
)
"""PROVISIONAL 5x15 layout; this is not the final physical arrangement."""
