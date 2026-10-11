"""Tests for named keyboard project persistence and validation."""

import json

import pytest

from desktop_app.layouts import L06, L12
from desktop_app.profile import create_profile
from desktop_app.project import (
    ProjectError,
    create_project,
    list_project_files,
    load_project,
    save_project,
)


def _assignments(layout, value="NONE") -> dict[str, str]:
    return {key.key_id: value for key in layout.keys}


def test_project_create_save_load_round_trip(tmp_path) -> None:
    assignments = _assignments(L06)
    assignments["K03"] = "Ctrl+X"
    document = create_project(
        "Six Pad", L06, assignments, profile_path="profiles/source.json"
    )

    path = save_project(tmp_path / "six-pad", document)
    loaded = load_project(path)

    assert path.name == "six-pad.kb75.json"
    assert loaded.name == "Six Pad"
    assert loaded.layout.name == "L06"
    assert loaded.layout.key_count == 6
    assert loaded.assignments["K03"] == "Ctrl+X"
    assert loaded.profile_path == "profiles/source.json"
    assert list_project_files(tmp_path) == [path]


def test_unknown_project_version_is_rejected(tmp_path) -> None:
    document = create_project("Future", L06, _assignments(L06))
    document["project_version"] = 99
    path = tmp_path / "future.kb75.json"
    path.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(ProjectError, match="Unsupported project_version 99"):
        load_project(path)


def test_corrupt_project_json_is_rejected_cleanly(tmp_path) -> None:
    path = tmp_path / "broken.kb75.json"
    path.write_text('{"type": "/project-project",', encoding="utf-8")

    with pytest.raises(ProjectError, match="Malformed JSON in project"):
        load_project(path)


def test_project_layout_key_count_must_match_profile(tmp_path) -> None:
    document = create_project("Stale", L06, _assignments(L06))
    document["layout"]["key_count"] = 12
    path = tmp_path / "stale.kb75.json"
    path.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(ProjectError, match="key_count does not match profile keys"):
        load_project(path)


def test_legacy_profile_without_layout_requires_matching_active_layout(tmp_path) -> None:
    path = tmp_path / "legacy.json"
    path.write_text(json.dumps(create_profile(_assignments(L06))), encoding="utf-8")

    loaded = load_project(path, fallback_layout=L06)
    assert loaded.layout.key_count == 6

    with pytest.raises(ProjectError, match="Profile key set mismatch"):
        load_project(path, fallback_layout=L12)
