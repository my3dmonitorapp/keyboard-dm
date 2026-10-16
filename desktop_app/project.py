"""Keyboard project persistence with additive matrix-layout support."""

from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .layout_model import Key, Layout
from .matrix_model import MatrixConfig, MatrixDataError
from .profile import ProfileError, create_profile, validate_profile


PROJECT_TYPE = "/project-project"
PROJECT_VERSION = 3
LEGACY_PROJECT_VERSIONS = frozenset({1, 2})
PROJECT_SUFFIX = ".kb75.json"
PROJECTS_DIRECTORY = Path(__file__).resolve().parents[1] / "profiles"


class ProjectError(ProfileError):
    """Raised when a keyboard project cannot be validated."""


@dataclass(frozen=True)
class KeyboardProject:
    """A validated named project with its layout, assignments, and source path."""

    name: str
    layout: Layout
    profile: dict[str, Any]
    profile_path: str | None = None
    matrix_config: MatrixConfig | None = None

    @property
    def assignments(self) -> dict[str, Any]:
        return {
            key_id: key_data["assignment"]
            for key_id, key_data in self.profile["keys"].items()
        }


def _project_filename(name: str) -> str:
    safe_name = "".join(
        character if character.isalnum() or character in "-_" else "-"
        for character in name.strip()
    ).strip("-_")
    if not safe_name:
        raise ProjectError("Project name must contain a letter or number")
    return f"{safe_name}{PROJECT_SUFFIX}"


def project_path(name: str, directory: str | Path = PROJECTS_DIRECTORY) -> Path:
    """Return the local project path for *name*."""
    return Path(directory) / _project_filename(name)


def list_project_files(
    directory: str | Path = PROJECTS_DIRECTORY,
) -> list[Path]:
    """List project files without creating or mutating the project directory."""
    root = Path(directory)
    if not root.is_dir():
        return []
    return sorted(root.glob(f"*{PROJECT_SUFFIX}"), key=lambda path: path.name.lower())


def _layout_block(layout: Layout) -> dict[str, Any]:
    def geometry(key: Key) -> dict[str, Any]:
        item = {
            "key_id": key.key_id,
            "x": key.x,
            "y": key.y,
            "w": key.w,
            "h": key.h,
            "label": key.label,
        }
        if key.dx or key.dy:
            item["dx"] = key.dx
            item["dy"] = key.dy
        return item

    return {
        "name": layout.name,
        "key_count": layout.key_count,
        "cols": layout.cols,
        "rows": layout.rows,
        "label": layout.label,
        "keys": [geometry(key) for key in layout.keys],
    }


def _validate_layout_block(data: Any, profile: Mapping[str, Any]) -> Layout:
    if not isinstance(data, dict):
        raise ProjectError("Project field 'layout' must be a JSON object")

    name = data.get("name")
    label = data.get("label", "project")
    key_count = data.get("key_count")
    cols = data.get("cols")
    rows = data.get("rows")
    if not isinstance(name, str) or not name.strip():
        raise ProjectError("Project layout name must be a non-empty string")
    if not isinstance(label, str):
        raise ProjectError("Project layout label must be a string")
    if type(key_count) is not int or not 2 <= key_count <= 500:
        raise ProjectError("Project layout key_count must be an integer from 2 to 500")
    if type(cols) is not int or cols < 1 or type(rows) is not int or rows < 1:
        raise ProjectError("Project layout cols and rows must be positive integers")
    profile_ids = list(profile["keys"])
    if key_count != len(profile_ids):
        raise ProjectError(
            "Project layout key_count does not match profile keys "
            f"({key_count} declared, {len(profile_ids)} found)"
        )
    if cols * rows < key_count:
        raise ProjectError(
            f"Project layout grid {cols}x{rows} cannot contain {key_count} keys"
        )

    geometry = data.get("keys")
    if geometry is None:
        geometry = [
            {
                "key_id": key_id,
                "x": index % cols,
                "y": index // cols,
                "w": 1,
                "h": 1,
            }
            for index, key_id in enumerate(profile_ids)
        ]
    if not isinstance(geometry, list) or len(geometry) != key_count:
        raise ProjectError(
            "Project layout geometry must contain exactly one entry per key"
        )

    keys: list[Key] = []
    seen_ids: set[str] = set()
    for item in geometry:
        if not isinstance(item, dict):
            raise ProjectError("Each project layout geometry entry must be an object")
        key_id = item.get("key_id")
        x, y = item.get("x"), item.get("y")
        w, h = item.get("w", 1), item.get("h", 1)
        dx, dy = item.get("dx", 0), item.get("dy", 0)
        if key_id not in profile["keys"] or key_id in seen_ids:
            raise ProjectError(
                f"Project layout geometry has an unknown or duplicate key ID {key_id!r}"
            )
        if type(x) is not int or x < 0 or type(y) is not int or y < 0:
            raise ProjectError(f"Project layout position for {key_id} must be non-negative")
        if type(w) not in (int, float) or w < 1 or type(h) is not int or h < 1:
            raise ProjectError(f"Project layout size for {key_id} must be positive")
        if type(dx) is not int or type(dy) is not int:
            raise ProjectError(f"Project layout visual offset for {key_id} must be integer")
        if x + w > cols or y + h > rows:
            raise ProjectError(f"Project layout geometry for {key_id} is outside its grid")
        seen_ids.add(key_id)
        keys.append(
            Key(
                key_id=key_id,
                x=x,
                y=y,
                w=w,
                h=h,
                assignment=profile["keys"][key_id]["assignment"],
                label=item.get("label", ""),
                dx=dx,
                dy=dy,
            )
        )

    missing = set(profile_ids) - seen_ids
    if missing:
        raise ProjectError(
            "Project layout geometry is missing key IDs: " + ", ".join(sorted(missing))
        )
    return Layout(name=name, label=label, cols=cols, rows=rows, keys=keys)


def create_project(
    name: str,
    layout: Layout,
    assignments: Mapping[str, Any],
    profile_path: str | Path | None = None,
    matrix_config: MatrixConfig | None = None,
) -> dict[str, Any]:
    """Create a v3 project document containing a compatible v2 profile."""
    if not isinstance(name, str) or not name.strip():
        raise ProjectError("Project name must be a non-empty string")
    key_ids = [key.key_id for key in layout.keys]
    if set(assignments) != set(key_ids):
        raise ProjectError("Project assignments must exactly match the layout key set")
    if matrix_config is not None:
        try:
            matrix_config = MatrixConfig.from_dict(matrix_config.to_dict())
        except MatrixDataError as error:
            raise ProjectError(str(error)) from error
        if layout.label != "matrix":
            raise ProjectError("A matrix config requires a matrix layout")
        if set(matrix_config.keys()) != set(key_ids):
            raise ProjectError(
                "Project matrix switches must exactly match the layout key set"
            )
    elif layout.label == "matrix":
        raise ProjectError("Matrix projects must include a matrix config")
    document = create_profile(assignments)
    document.update(
        {
            "type": PROJECT_TYPE,
            "project_version": PROJECT_VERSION,
            "name": name.strip(),
            "layout": _layout_block(layout),
        }
    )
    if profile_path is not None:
        document["profile_path"] = str(profile_path)
    if matrix_config is not None:
        document["matrix"] = matrix_config.to_dict()
    validate_project(document)
    return document


def validate_project(
    document: Any, fallback_layout: Layout | None = None
) -> KeyboardProject:
    """Validate a project or a legacy v1 profile for *fallback_layout*."""
    if not isinstance(document, dict):
        raise ProjectError("Project root must be a JSON object")

    marker = document.get("type")
    if marker is None:
        if "project_version" in document:
            raise ProjectError("Project type marker is missing")
        if fallback_layout is None:
            raise ProjectError("Legacy profile has no layout metadata")
        try:
            profile = validate_profile(
                document, (key.key_id for key in fallback_layout.keys)
            )
        except ProfileError as error:
            raise ProjectError(str(error)) from error
        layout = Layout.from_dict(fallback_layout.to_dict())
        for key in layout.keys:
            key.assignment = profile["keys"][key.key_id]["assignment"]
        return KeyboardProject("Legacy profile", layout, deepcopy(profile))

    if marker != PROJECT_TYPE:
        raise ProjectError(f"Unknown project type {marker!r}; expected {PROJECT_TYPE!r}")
    version = document.get("project_version")
    if type(version) is not int or version not in {
        *LEGACY_PROJECT_VERSIONS,
        PROJECT_VERSION,
    }:
        raise ProjectError(
            f"Unsupported project_version {version!r}; expected 1, 2, or "
            f"{PROJECT_VERSION}"
        )
    name = document.get("name")
    if not isinstance(name, str) or not name.strip():
        raise ProjectError("Project name must be a non-empty string")
    profile_path = document.get("profile_path")
    if profile_path is not None and not isinstance(profile_path, str):
        raise ProjectError("Project profile_path must be a string when present")

    try:
        profile = validate_profile(document)
    except ProfileError as error:
        raise ProjectError(str(error)) from error
    matrix_config = None
    matrix_data = document.get("matrix")
    if matrix_data is not None:
        try:
            matrix_config = MatrixConfig.from_dict(matrix_data)
        except MatrixDataError as error:
            raise ProjectError(f"Invalid project matrix: {error}") from error

    if matrix_config is None:
        layout = _validate_layout_block(document.get("layout"), profile)
        if version == PROJECT_VERSION and layout.label == "matrix":
            raise ProjectError("Matrix project is missing field 'matrix'")
    else:
        layout_data = document.get("layout")
        if not isinstance(layout_data, dict):
            raise ProjectError("Project field 'layout' must be a JSON object")
        name_value = layout_data.get("name")
        if not isinstance(name_value, str) or not name_value.strip():
            raise ProjectError("Project layout name must be a non-empty string")
        if layout_data.get("label") != "matrix":
            raise ProjectError("Project matrix layout label must be 'matrix'")
        if layout_data.get("rows") != matrix_config.rows:
            raise ProjectError("Project layout rows do not match the matrix config")
        if layout_data.get("cols") != matrix_config.cols:
            raise ProjectError("Project layout cols do not match the matrix config")
        if layout_data.get("key_count") != len(matrix_config.switches):
            raise ProjectError("Project layout key_count does not match matrix switches")
        expected_ids = set(matrix_config.keys())
        if set(profile["keys"]) != expected_ids:
            raise ProjectError("Project profile key set does not match matrix switches")
        layout = matrix_config.to_layout(name=name_value.strip())
        for key in layout.keys:
            key.assignment = profile["keys"][key.key_id]["assignment"]
    try:
        validate_profile(profile, (key.key_id for key in layout.keys))
    except ProfileError as error:
        raise ProjectError(str(error)) from error
    return KeyboardProject(
        name.strip(), layout, deepcopy(profile), profile_path, matrix_config
    )


def load_project(
    path: str | Path, fallback_layout: Layout | None = None
) -> KeyboardProject:
    """Load a project, reporting malformed JSON as a clean project error."""
    source = Path(path)
    try:
        with source.open("r", encoding="utf-8") as project_file:
            document = json.load(project_file)
    except json.JSONDecodeError as error:
        raise ProjectError(
            f"Malformed JSON in project '{source}': {error.msg}"
        ) from error
    return validate_project(document, fallback_layout)


def save_project(path: str | Path, document: Mapping[str, Any]) -> Path:
    """Validate and write a project document, returning its normalized path."""
    project = validate_project(dict(document))
    target = Path(path)
    if not str(target).endswith(PROJECT_SUFFIX):
        target = Path(f"{target}{PROJECT_SUFFIX}")
    target.parent.mkdir(parents=True, exist_ok=True)

    output = deepcopy(project.profile)
    output.update(
        {
            "type": PROJECT_TYPE,
            "project_version": PROJECT_VERSION,
            "name": project.name,
            "layout": _layout_block(project.layout),
        }
    )
    if project.profile_path is not None:
        output["profile_path"] = project.profile_path
    if project.matrix_config is not None:
        output["matrix"] = project.matrix_config.to_dict()
    else:
        output.pop("matrix", None)
    with target.open("w", encoding="utf-8") as project_file:
        json.dump(output, project_file, indent=2)
        project_file.write("\n")
    return target
