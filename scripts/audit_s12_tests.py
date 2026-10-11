#!/usr/bin/env python3
"""Count S1.2 verification test functions from test names and docstrings."""

from __future__ import annotations

import ast
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
TESTS = ROOT / "tests"

CATEGORIES = {
    "a single-key assignments": (r"single_key", r"required_single_key"),
    "b every modifier": (r"every_modifier", r"each_sided_modifier"),
    "c modifier down/up": (r"modifier_down_and_up",),
    "d shortcut serialization/restoration": (
        r"shortcut.*(?:serializ|restor)|(?:serializ|restor).*shortcut",
        r"shortcuts_serialize",
        r"typed_actions_save_and_reload",
    ),
    "e simultaneous modifiers": (r"simultaneous_modifiers",),
    "f all media actions": (r"media_actions", r"each_media_key"),
    "g lossless v1 migration": (r"legacy_v1", r"v1_.*migrat",),
    "h invalid action rejection": (r"invalid_serialized_actions", r"bad_action_payload"),
    "i GUI edit/save/reopen": (r"gui_.*save_and_reload", r"single_key_apply"),
    "j structured device round-trip": (r"structured_actions_round_trip",),
    "k S1/S1.1 regression guards": (
        r"layout_menu_selection_save_and_reopen",
        r"layout_switch_preserves",
        r"switching_projects_preserves",
        r"wrong_key_set",
        r"unsaved_changes|assignment_marks_dirty",
    ),
}


def test_functions() -> list[tuple[str, str, str]]:
    found: list[tuple[str, str, str]] = []
    for path in sorted(TESTS.glob("test_*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith(
                "test_"
            ):
                found.append(
                    (str(path.relative_to(ROOT)), node.name, ast.get_docstring(node) or "")
                )
    return found


def main() -> int:
    tests = test_functions()
    print("category | test functions | files")
    print("--- | ---: | ---")
    missing = False
    for category, patterns in CATEGORIES.items():
        matches = [
            item
            for item in tests
            if any(re.search(pattern, f"{item[1]} {item[2]}", re.IGNORECASE) for pattern in patterns)
        ]
        files = ", ".join(sorted({item[0] for item in matches})) or "—"
        print(f"{category} | {len(matches)} | {files}")
        missing |= not matches
    return int(missing)


if __name__ == "__main__":
    raise SystemExit(main())
