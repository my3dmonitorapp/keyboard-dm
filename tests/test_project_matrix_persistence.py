"""Lossless v3 persistence coverage for sparse matrix projects."""

import json
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from desktop_app.action import MediaAction, ModifierAction, ShortcutAction
from desktop_app.app import Keyboard75Window
from desktop_app.layouts import L06
from desktop_app.matrix_model import MatrixConfig
from desktop_app.project import (
    PROJECT_VERSION,
    ProjectError,
    create_project,
    load_project,
    save_project,
)


def _matrix_config() -> MatrixConfig:
    return MatrixConfig(
        rows=3,
        cols=4,
        switches={(0, 0), (0, 3), (1, 1), (2, 0), (2, 2)},
        key_widths={(0, 0): 3, (0, 3): 1, (1, 1): 5, (2, 2): 12},
        key_labels={(0, 0): "Esc", (1, 1): "Copy", (2, 2): "Space"},
        row_pins=[0, 4, 8],
        column_pins=[12, 16, 20, 24],
        min_pin=0,
        max_pin=39,
    )


def _matrix_document():
    config = _matrix_config()
    layout = config.to_layout("Sparse 3x4")
    assignments = {key_id: None for key_id in config.keys()}
    assignments["MX-00-00"] = ShortcutAction(("lctrl", "lshift"), "s")
    assignments["MX-01-01"] = ModifierAction("ralt", "up")
    assignments["MX-02-02"] = MediaAction("play_pause")
    return config, create_project(
        "Sparse Matrix", layout, assignments, matrix_config=config
    )


def test_matrix_project_round_trip_preserves_config_and_typed_actions(tmp_path):
    config, document = _matrix_document()

    path = save_project(tmp_path / "matrix", document)
    loaded = load_project(path)

    assert loaded.matrix_config == config
    assert loaded.matrix_config.to_dict() == config.to_dict()
    assert loaded.layout.to_dict() == {
        **config.to_layout("Sparse 3x4").to_dict(),
        "keys": [
            {
                **key.to_dict(),
                "assignment": loaded.assignments[key.key_id],
            }
            for key in config.to_layout("Sparse 3x4").keys
        ],
    }
    assert loaded.assignments["MX-00-00"] == ShortcutAction(
        ("lctrl", "lshift"), "s"
    ).to_json()
    assert loaded.assignments["MX-01-01"] == ModifierAction("ralt", "up").to_json()
    assert loaded.assignments["MX-02-02"] == MediaAction("play_pause").to_json()


def test_matrix_project_two_round_trips_are_idempotent(tmp_path):
    config, document = _matrix_document()
    first = load_project(save_project(tmp_path / "first", document))

    second_document = create_project(
        first.name,
        first.layout,
        first.assignments,
        first.profile_path,
        first.matrix_config,
    )
    second = load_project(save_project(tmp_path / "second", second_document))

    assert second.matrix_config == config == first.matrix_config
    assert second.layout.to_dict() == first.layout.to_dict()
    assert second.assignments == first.assignments


@pytest.mark.parametrize("legacy_version", [1, 2])
def test_preexisting_non_matrix_project_loads_without_field_loss(
    tmp_path, legacy_version
):
    assignments = {key.key_id: None for key in L06.keys}
    assignments["K03"] = ShortcutAction(("lctrl",), "x")
    document = create_project(
        "Legacy v2", L06, assignments, profile_path="profiles/source.json"
    )
    document["project_version"] = legacy_version
    path = tmp_path / f"legacy-v{legacy_version}.kb75.json"
    path.write_text(json.dumps(document), encoding="utf-8")

    loaded = load_project(path)

    assert loaded.name == "Legacy v2"
    assert loaded.matrix_config is None
    assert loaded.layout.to_dict() == L06.to_dict() | {
        "keys": [
            {
                **key.to_dict(),
                "assignment": loaded.assignments[key.key_id],
            }
            for key in L06.keys
        ]
    }
    assert loaded.profile_path == "profiles/source.json"
    assert loaded.assignments["K03"] == ShortcutAction(("lctrl",), "x").to_json()

    migrated = load_project(save_project(tmp_path / "migrated", document))
    assert migrated.matrix_config is None
    assert migrated.assignments == loaded.assignments
    migrated_document = json.loads(
        (tmp_path / "migrated.kb75.json").read_text(encoding="utf-8")
    )
    assert migrated_document["project_version"] == PROJECT_VERSION


def test_short_written_matrix_project_raises_clear_error(tmp_path):
    path = tmp_path / "short.kb75.json"
    path.write_text('{"type": "/project-project", "matrix": {', encoding="utf-8")

    with pytest.raises(ProjectError, match="Malformed JSON in project"):
        load_project(path)


def test_gui_save_and_open_restores_complete_matrix_project(tmp_path):
    application = QApplication.instance() or QApplication([])
    config = _matrix_config()
    source = Keyboard75Window(layout=L06)
    reopened = Keyboard75Window(layout=L06)
    try:
        source.matrix_config = config
        source.matrix_layout = config.to_layout("Sparse 3x4")
        source._install_layout(source.matrix_layout)
        source.layout.keys[0].assignment = ShortcutAction(("lctrl",), "c").to_json()
        source.current_project_name = "GUI Matrix"
        source.current_project_path = tmp_path / "gui-matrix.kb75.json"

        path = source.save_project()
        assert reopened.load_project(path)

        assert reopened.matrix_config == config
        assert reopened.matrix_layout is not None
        assert reopened.layout.label == "matrix"
        assert reopened.layout.keys[0].assignment == ShortcutAction(
            ("lctrl",), "c"
        ).to_json()
        assert reopened.saved_matrix_action.isEnabled()
        assert reopened.matrix_pinmap_action.isEnabled()
    finally:
        source._set_dirty(False)
        reopened._set_dirty(False)
        source.close()
        reopened.close()
        application.processEvents()
