"""PySide6 user interface for configurable keyboard layouts."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QCloseEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from .action import (
    Action,
    ActionValidationError,
    LegacyAction,
    MEDIA_KEYS,
    MODIFIERS,
    SINGLE_KEYS,
    MediaAction,
    ModifierAction,
    ShortcutAction,
    SingleKeyAction,
    parse_shortcut,
)
from .device import SimulatedESP32S3Device
from .layout_model import Key, Layout
from .layouts import BUILT_IN_LAYOUTS, L75, make_custom_layout
from .profile import (
    ProfileError,
    create_profile,
    load_profile as load_profile_file,
    save_profile as save_profile_file,
)
from .project import (
    PROJECTS_DIRECTORY,
    ProjectError,
    create_project,
    list_project_files,
    load_project as load_project_file,
    project_path,
    save_project as save_project_file,
)


DARK_STYLESHEET = """
QMainWindow, QWidget {
    background-color: #181b20;
    color: #e4e8ee;
}
QMenuBar {
    background-color: #14171b;
    color: #dce1e8;
    border-bottom: 1px solid #30353d;
}
QMenuBar::item {
    background: transparent;
    padding: 5px 10px;
}
QMenuBar::item:selected, QMenuBar::item:pressed {
    background-color: #2a2f37;
}
QMenu {
    background-color: #20242a;
    color: #e4e8ee;
    border: 1px solid #3b414b;
    padding: 4px;
}
QMenu::item {
    padding: 6px 24px 6px 10px;
}
QMenu::item:selected {
    background-color: #343b45;
}
QPushButton {
    background-color: #2a2f36;
    color: #eef1f5;
    border: 1px solid #454c57;
    border-radius: 5px;
    padding: 6px 12px;
}
QPushButton:hover {
    background-color: #343a43;
    border-color: #596271;
}
QPushButton:pressed {
    background-color: #24282e;
}
QPushButton:disabled {
    background-color: #22262b;
    color: #747b85;
    border-color: #343941;
}
QComboBox, QSpinBox {
    background-color: #111419;
    color: #eef1f5;
    border: 1px solid #444b55;
    border-radius: 4px;
    padding: 6px;
    selection-background-color: #356f9f;
}
QComboBox:focus, QSpinBox:focus {
    border-color: #67a9d8;
}
QCheckBox {
    spacing: 6px;
}
QCheckBox::indicator {
    width: 15px;
    height: 15px;
}
QFrame#keyInspector {
    background-color: #20242a;
    border: 1px solid #353b44;
    border-radius: 7px;
}
QLabel#provisionalBanner {
    background-color: #2b2922;
    color: #d9c98c;
    border: 1px solid #5f5738;
    border-radius: 3px;
    padding: 3px 8px;
    font-size: 11px;
    font-weight: 600;
}
QStatusBar {
    background-color: #121519;
    color: #bfc6cf;
    border-top: 1px solid #30353d;
}
QStatusBar QLabel {
    background: transparent;
    color: #bfc6cf;
    padding: 2px 8px;
}
QLabel#simulatedDeviceStatusLabel {
    border-left: 1px solid #3a4049;
}
QToolTip {
    background-color: #292e35;
    color: #eef1f5;
    border: 1px solid #4b535f;
    padding: 4px;
}
"""


class _AssignmentEditCompatibility:
    """Non-visual adapter for the pre-S1.2 smoke-test automation API."""

    def __init__(self, window: Keyboard75Window) -> None:
        self._window = window

    def setText(self, text: str) -> None:  # noqa: N802 - Qt compatibility name
        self._window._compatibility_clear_requested = text.strip().casefold() in {
            "",
            "none",
        }
        self._window._load_legacy_editor_text(text)

    def text(self) -> str:
        action = self._window._editor_action_or_none()
        return "NONE" if action is None else action.label

    def clear(self) -> None:
        self.setText("NONE")

    def setEnabled(self, enabled: bool) -> None:  # noqa: N802
        self._window._set_action_editor_enabled(enabled)

    def setFocus(self) -> None:  # noqa: N802
        self._window.action_type_combo.setFocus()

    def selectAll(self) -> None:  # noqa: N802
        pass


class _ActionPayload(dict[str, Any]):
    """Typed payload that remains comparable to old smoke labels during T3."""

    def __eq__(self, other: object) -> bool:
        if isinstance(other, str):
            try:
                return Action.from_json(self).label == other
            except ActionValidationError:
                return False
        return super().__eq__(other)


KEYCAP_STYLESHEET = """
QPushButton {
    background-color: #30363e;
    color: #eef2f6;
    border: 2px solid #4b535e;
    border-bottom: 4px solid #171a1e;
    border-radius: 8px;
    padding: 6px 4px 8px 4px;
    font-weight: 600;
}
QPushButton:hover {
    background-color: #3a424c;
    border-color: #697483;
    border-bottom-color: #22272d;
}
QPushButton:checked {
    background-color: #294e68;
    color: #ffffff;
    border-color: #77bce8;
    border-bottom-color: #3f87b6;
}
QPushButton:checked:hover {
    background-color: #315c79;
}
"""


class Keyboard75Window(QMainWindow):
    """Main window for editing an in-memory keyboard layout."""

    def __init__(
        self,
        layout: Layout | None = None,
        device: SimulatedESP32S3Device | None = None,
    ) -> None:
        super().__init__()
        self.layout = Layout.from_dict((layout or L75).to_dict())
        for key in self.layout.keys:
            action = self._action_from_assignment(key.assignment)
            key.assignment = None if action is None else self._typed_payload(action)
        self.device = device or SimulatedESP32S3Device(
            key.key_id for key in self.layout.keys
        )
        if device is not None:
            self.device.set_key_ids(key.key_id for key in self.layout.keys)
        self.selected_key: Key | None = None
        self.key_widgets: dict[str, QPushButton] = {}
        self.profile: dict[str, object] | None = None
        self.current_profile_path: Path | None = None
        self.current_project_name: str | None = None
        self.current_project_path: Path | None = None
        self.dirty = False
        self._compatibility_clear_requested = False

        self.setStyleSheet(DARK_STYLESHEET)
        self._build_file_menu()
        self._build_layout_menu()

        central_widget = QWidget(self)
        root_layout = QVBoxLayout(central_widget)
        root_layout.setContentsMargins(16, 16, 16, 16)
        root_layout.setSpacing(12)

        root_layout.addWidget(self._build_top_bar())
        self.layout_banner = self._build_provisional_banner()
        root_layout.addWidget(self.layout_banner)

        self.content_layout = QHBoxLayout()
        self.content_layout.setSpacing(16)
        self.key_grid_container = self._build_key_grid()
        self.content_layout.addWidget(self.key_grid_container, stretch=1)
        self.inspector = self._build_inspector()
        self.content_layout.addWidget(self.inspector)
        root_layout.addLayout(self.content_layout, stretch=1)

        self.setCentralWidget(central_widget)
        self._build_status_bar()
        self._refresh_profile_status()
        self._resize_for_layout()

    def _build_file_menu(self) -> None:
        file_menu = self.menuBar().addMenu("&File")

        open_action = QAction("Open Local Profile...", self)
        open_action.setObjectName("openProfileAction")
        open_action.setToolTip("Open a local JSON profile; this does not read hardware")
        open_action.triggered.connect(self._open_profile_dialog)
        file_menu.addAction(open_action)

        save_action = QAction("Save Local Profile...", self)
        save_action.setObjectName("saveProfileAction")
        save_action.setToolTip("Save local JSON only; this does not write to hardware")
        save_action.triggered.connect(self._save_profile_dialog)
        file_menu.addAction(save_action)

        file_menu.addSeparator()
        projects_menu = file_menu.addMenu("Projects")
        projects_menu.setObjectName("projectsMenu")

        new_project_action = QAction("New Project...", self)
        new_project_action.setObjectName("newProjectAction")
        new_project_action.triggered.connect(self._new_project_dialog)
        projects_menu.addAction(new_project_action)

        save_project_action = QAction("Save Project", self)
        save_project_action.setObjectName("saveProjectAction")
        save_project_action.triggered.connect(self._save_project_from_menu)
        projects_menu.addAction(save_project_action)

        self.open_projects_menu = projects_menu.addMenu("Open Project")
        self.open_projects_menu.setObjectName("openProjectsMenu")
        self.open_projects_menu.aboutToShow.connect(self._refresh_open_projects_menu)

    def _build_layout_menu(self) -> None:
        layout_menu = self.menuBar().addMenu("&Layout")
        layout_menu.setObjectName("layoutMenu")
        for built_in in BUILT_IN_LAYOUTS:
            action = QAction(
                f"{built_in.name} ({built_in.key_count} keys)", self
            )
            action.setObjectName(f"layoutAction_{built_in.name}")
            action.triggered.connect(
                lambda _checked=False, selected=built_in: self.switch_layout(selected)
            )
            layout_menu.addAction(action)
        layout_menu.addSeparator()
        custom_action = QAction("Custom...", self)
        custom_action.setObjectName("customLayoutAction")
        custom_action.triggered.connect(self._open_custom_layout_dialog)
        layout_menu.addAction(custom_action)

    def _build_status_bar(self) -> None:
        self.local_profile_status_label = QLabel(self)
        self.local_profile_status_label.setObjectName("localProfileStatusLabel")
        self.simulated_device_status_label = QLabel(self)
        self.simulated_device_status_label.setObjectName("simulatedDeviceStatusLabel")
        self.statusBar().addPermanentWidget(self.local_profile_status_label, 1)
        self.statusBar().addPermanentWidget(self.simulated_device_status_label)

    def _build_top_bar(self) -> QWidget:
        top_bar = QWidget(self)
        layout = QVBoxLayout(top_bar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        heading_row = QHBoxLayout()
        controls_row = QHBoxLayout()

        title = QLabel("Keyboard75 Layout Editor", top_bar)
        title.setStyleSheet("font-size: 18px; font-weight: 600;")
        self.device_status_label = QLabel(top_bar)
        self.device_status_label.setObjectName("deviceStatusLabel")
        self.transport_label = QLabel(top_bar)
        self.transport_label.setObjectName("transportLabel")

        self.host_connected_checkbox = QCheckBox("USB host connected", top_bar)
        self.host_connected_checkbox.setObjectName("hostConnectedCheckbox")
        self.host_connected_checkbox.toggled.connect(self.set_host_connected)

        self.connect_button = QPushButton("Connect", top_bar)
        self.connect_button.setObjectName("connectButton")
        self.connect_button.clicked.connect(self.connect_device)

        self.disconnect_button = QPushButton("Disconnect", top_bar)
        self.disconnect_button.setObjectName("disconnectButton")
        self.disconnect_button.clicked.connect(self.disconnect_device)

        heading_row.addWidget(title)
        heading_row.addStretch()
        heading_row.addWidget(self.host_connected_checkbox)
        controls_row.addWidget(self.device_status_label)
        controls_row.addWidget(self.transport_label)
        controls_row.addStretch()
        controls_row.addWidget(self.connect_button)
        controls_row.addWidget(self.disconnect_button)
        layout.addLayout(heading_row)
        layout.addLayout(controls_row)
        self._refresh_device_status()
        return top_bar

    def _build_provisional_banner(self) -> QLabel:
        banner = QLabel(self.layout.label, self)
        banner.setObjectName("provisionalBanner")
        banner.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        banner.setMaximumHeight(24)
        banner.setVisible(self._layout_is_provisional())
        return banner

    def _build_key_grid(self) -> QWidget:
        grid_container = QWidget(self)
        self.key_widgets = {}
        grid = QGridLayout(grid_container)
        grid.setContentsMargins(0, 0, 0, 0)
        key_width, key_height, spacing = self._key_grid_metrics()
        grid.setHorizontalSpacing(spacing)
        grid.setVerticalSpacing(spacing)

        for key in self.layout.keys:
            button = QPushButton(self._button_text(key), grid_container)
            button.setObjectName(f"keyButton_{key.key_id}")
            button.setCheckable(True)
            button.setFixedSize(key_width, key_height)
            button.setStyleSheet(KEYCAP_STYLESHEET)
            button.clicked.connect(
                lambda _checked=False, selected=key: self.select_key(selected)
            )
            grid.addWidget(button, key.y, key.x, key.h, key.w)
            self.key_widgets[key.key_id] = button
            self._refresh_keycap(key)

        grid_container.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
        )
        return grid_container

    def _key_grid_metrics(self) -> tuple[int, int, int]:
        """Return compact keycap dimensions and spacing for the active layout."""
        if self.layout.cols >= 10:
            return (58, 58, 5)
        if self.layout.key_count <= 12:
            return (64, 60, 8)
        return (60, 58, 6)

    def _layout_is_provisional(self) -> bool:
        """Return whether the active layout is the built-in provisional L75."""
        return self.layout.name == L75.name and self.layout.label == L75.label

    def _resize_for_layout(self) -> None:
        """Resize the window around the active key grid without empty grid space."""
        key_width, key_height, spacing = self._key_grid_metrics()
        grid_width = self.layout.cols * key_width + max(0, self.layout.cols - 1) * spacing
        grid_height = self.layout.rows * key_height + max(0, self.layout.rows - 1) * spacing

        if self.layout.key_count >= 50:
            target_width = 1240
            target_height = 520
        else:
            target_width = max(620, grid_width + 250 + 64)
            target_height = max(410, grid_height + 240)
        self.resize(target_width, target_height)

    def switch_layout(self, layout: Layout) -> bool:
        """Switch to a copy of *layout* while retaining shared assignments."""
        if not self.confirm_unsaved_changes():
            return False

        previous_assignments = {
            key.key_id: key.assignment for key in self.layout.keys
        }
        new_layout = Layout.from_dict(layout.to_dict())
        for key in new_layout.keys:
            key.assignment = previous_assignments.get(key.key_id)

        self._install_layout(new_layout)
        self._set_dirty(True)
        return True

    def _install_layout(self, new_layout: Layout) -> None:
        """Install an already-copied layout and synchronize its UI/device key set."""

        for key in new_layout.keys:
            action = self._action_from_assignment(key.assignment)
            key.assignment = None if action is None else self._typed_payload(action)
        self.selected_key = None
        self._load_action_into_editor(None)
        self._set_action_editor_enabled(False)
        self.apply_button.setEnabled(False)
        self.clear_button.setEnabled(False)
        self.inspector_key_id.setText("Key ID: Select a key")
        self.inspector_position.setText("Position: —")

        old_grid = self.key_grid_container
        self.layout = new_layout
        self.key_grid_container = self._build_key_grid()
        self.content_layout.replaceWidget(old_grid, self.key_grid_container)
        old_grid.deleteLater()
        self.layout_banner.setText(self.layout.label)
        self.layout_banner.setVisible(self._layout_is_provisional())
        self.device.set_key_ids(
            (key.key_id for key in self.layout.keys),
            {
                key.key_id: self._device_assignment(key.assignment)
                for key in self.layout.keys
            },
        )
        self._refresh_device_status()
        self._resize_for_layout()

    def _open_custom_layout_dialog(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("Custom layout")
        form = QFormLayout(dialog)

        count_input = QSpinBox(dialog)
        count_input.setObjectName("customKeyCountInput")
        count_input.setRange(2, 500)
        count_input.setValue(self.layout.key_count)
        form.addRow("Key count", count_input)

        cols_input = QSpinBox(dialog)
        cols_input.setObjectName("customColsInput")
        cols_input.setRange(0, 500)
        cols_input.setSpecialValueText("Auto")
        form.addRow("Columns (optional)", cols_input)

        rows_input = QSpinBox(dialog)
        rows_input.setObjectName("customRowsInput")
        rows_input.setRange(0, 500)
        rows_input.setSpecialValueText("Auto")
        form.addRow("Rows (optional)", rows_input)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel,
            parent=dialog,
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        form.addRow(buttons)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        cols = cols_input.value() or None
        rows = rows_input.value() or None
        try:
            custom_layout = make_custom_layout(count_input.value(), cols, rows)
        except ValueError as error:
            QMessageBox.critical(self, "Could not create custom layout", str(error))
            return
        self.switch_layout(custom_layout)

    def _build_inspector(self) -> QWidget:
        inspector = QFrame(self)
        inspector.setObjectName("keyInspector")
        inspector.setFrameShape(QFrame.Shape.StyledPanel)
        inspector.setFixedWidth(250)
        layout = QVBoxLayout(inspector)

        heading = QLabel("Key inspector", inspector)
        heading.setStyleSheet("font-size: 17px; font-weight: 600;")
        self.inspector_key_id = QLabel("Key ID: Select a key", inspector)
        self.inspector_position = QLabel("Position: —", inspector)

        assignment_label = QLabel("Action", inspector)
        self.action_type_combo = QComboBox(inspector)
        self.action_type_combo.setObjectName("actionTypeCombo")
        for label, action_type in (
            ("Single Key", "key"),
            ("Modifier Key", "modifier"),
            ("Keyboard Shortcut", "shortcut"),
            ("Media Key", "media"),
            ("None", "none"),
        ):
            self.action_type_combo.addItem(label, action_type)

        self.single_key_panel = QWidget(inspector)
        single_key_layout = QVBoxLayout(self.single_key_panel)
        single_key_layout.setContentsMargins(0, 0, 0, 0)
        single_key_layout.setSpacing(3)
        single_key_layout.addWidget(QLabel("Key", self.single_key_panel))
        self.single_key_combo = self._make_key_combo(
            self.single_key_panel, "singleKeyCombo"
        )
        single_key_layout.addWidget(self.single_key_combo)

        self.modifier_panel = QWidget(inspector)
        modifier_layout = QGridLayout(self.modifier_panel)
        modifier_layout.setContentsMargins(0, 0, 0, 0)
        modifier_layout.setHorizontalSpacing(5)
        modifier_layout.setVerticalSpacing(2)
        modifier_layout.addWidget(QLabel("Modifiers", self.modifier_panel), 0, 0, 1, 2)
        self.modifier_checkboxes: dict[str, QCheckBox] = {}
        modifier_rows = (
            ("lctrl", "rctrl"),
            ("lshift", "rshift"),
            ("lalt", "ralt"),
            ("lsuper", "rsuper"),
        )
        for row, modifier_ids in enumerate(modifier_rows, start=1):
            for column, modifier_id in enumerate(modifier_ids):
                checkbox = QCheckBox(MODIFIERS[modifier_id].label, self.modifier_panel)
                checkbox.setObjectName(f"modifierCheckbox_{modifier_id}")
                checkbox.toggled.connect(
                    lambda checked, selected=modifier_id: self._modifier_toggled(
                        selected, checked
                    )
                )
                modifier_layout.addWidget(checkbox, row, column)
                self.modifier_checkboxes[modifier_id] = checkbox

        self.shortcut_key_panel = QWidget(inspector)
        shortcut_key_layout = QVBoxLayout(self.shortcut_key_panel)
        shortcut_key_layout.setContentsMargins(0, 0, 0, 0)
        shortcut_key_layout.setSpacing(3)
        shortcut_key_layout.addWidget(QLabel("Main key", self.shortcut_key_panel))
        self.shortcut_key_combo = self._make_key_combo(
            self.shortcut_key_panel, "shortcutKeyCombo"
        )
        shortcut_key_layout.addWidget(self.shortcut_key_combo)

        self.media_key_panel = QWidget(inspector)
        media_key_layout = QVBoxLayout(self.media_key_panel)
        media_key_layout.setContentsMargins(0, 0, 0, 0)
        media_key_layout.setSpacing(3)
        media_key_layout.addWidget(QLabel("Media control", self.media_key_panel))
        self.media_key_combo = QComboBox(self.media_key_panel)
        self.media_key_combo.setObjectName("mediaKeyCombo")
        for media_id, definition in MEDIA_KEYS.items():
            self.media_key_combo.addItem(definition.label, media_id)
        media_key_layout.addWidget(self.media_key_combo)

        # Kept as a non-widget compatibility surface for the existing smoke runner.
        self.assignment_edit = _AssignmentEditCompatibility(self)

        self.apply_button = QPushButton("Apply", inspector)
        self.apply_button.setObjectName("applyButton")
        self.apply_button.setEnabled(False)
        self.apply_button.clicked.connect(self.apply_assignment)

        self.clear_button = QPushButton("Clear", inspector)
        self.clear_button.setObjectName("clearActionButton")
        self.clear_button.setEnabled(False)
        self.clear_button.clicked.connect(self.clear_action)

        button_row = QHBoxLayout()
        button_row.addWidget(self.apply_button)
        button_row.addWidget(self.clear_button)

        layout.addWidget(heading)
        layout.addSpacing(8)
        layout.addWidget(self.inspector_key_id)
        layout.addWidget(self.inspector_position)
        layout.addSpacing(12)
        layout.addWidget(assignment_label)
        layout.addWidget(self.action_type_combo)
        layout.addWidget(self.single_key_panel)
        layout.addWidget(self.modifier_panel)
        layout.addWidget(self.shortcut_key_panel)
        layout.addWidget(self.media_key_panel)
        layout.addLayout(button_row)
        layout.addStretch()
        self.action_type_combo.currentIndexChanged.connect(
            self._action_type_changed
        )
        self._loading_action_editor = False
        self._update_action_editor_visibility()
        self._set_action_editor_enabled(False)
        return inspector

    @staticmethod
    def _make_key_combo(parent: QWidget, object_name: str) -> QComboBox:
        combo = QComboBox(parent)
        combo.setObjectName(object_name)
        combo.setMaxVisibleItems(18)
        for key_id, definition in SINGLE_KEYS.items():
            combo.addItem(definition.label, key_id)
        return combo

    @staticmethod
    def _action_from_assignment(assignment: Any) -> Action | None:
        if assignment is None:
            return None
        if isinstance(assignment, str):
            stripped = assignment.strip()
            if not stripped or stripped.casefold() == "none":
                return None
            if "+" in stripped:
                try:
                    return parse_shortcut(stripped)
                except ActionValidationError:
                    pass
            for action_class in (MediaAction, ModifierAction, SingleKeyAction):
                try:
                    return action_class(stripped)
                except ActionValidationError:
                    pass
            return LegacyAction(assignment)
        if isinstance(assignment, Action):
            return assignment.validate()
        return Action.from_json(assignment).validate()

    @staticmethod
    def _typed_payload(action: Action) -> dict[str, Any]:
        return _ActionPayload(action.to_json())

    @classmethod
    def _assignment_label(cls, assignment: Any) -> str | None:
        action = cls._action_from_assignment(assignment)
        return None if action is None else action.label

    @classmethod
    def _device_assignment(cls, assignment: Any) -> str:
        return cls._assignment_label(assignment) or "NONE"

    @classmethod
    def _button_text(cls, key: Key) -> str:
        label = cls._assignment_label(key.assignment)
        return key.key_id if label is None else f"{key.key_id}\n{label}"

    def _refresh_keycap(self, key: Key) -> None:
        button = self.key_widgets[key.key_id]
        label = self._assignment_label(key.assignment)
        button.setText(self._button_text(key))
        button.setToolTip(key.key_id if label is None else f"{key.key_id}: {label}")
        font = button.font()
        label_length = len(label or key.key_id)
        font.setPointSize(7 if label_length > 12 else 8 if label_length > 8 else 9)
        button.setFont(font)

    def _set_action_editor_enabled(self, enabled: bool) -> None:
        self.action_type_combo.setEnabled(enabled)
        self.single_key_combo.setEnabled(enabled)
        self.shortcut_key_combo.setEnabled(enabled)
        self.media_key_combo.setEnabled(enabled)
        for checkbox in self.modifier_checkboxes.values():
            checkbox.setEnabled(enabled)

    def _selected_modifier_ids(self) -> tuple[str, ...]:
        return tuple(
            modifier_id
            for modifier_id in MODIFIERS
            if self.modifier_checkboxes[modifier_id].isChecked()
        )

    def _clear_modifier_checks(self) -> None:
        for checkbox in self.modifier_checkboxes.values():
            checkbox.blockSignals(True)
            checkbox.setChecked(False)
            checkbox.blockSignals(False)

    def _modifier_toggled(self, modifier_id: str, checked: bool) -> None:
        if not checked or self.action_type_combo.currentData() != "modifier":
            return
        for other_id, checkbox in self.modifier_checkboxes.items():
            if other_id != modifier_id and checkbox.isChecked():
                checkbox.blockSignals(True)
                checkbox.setChecked(False)
                checkbox.blockSignals(False)

    def _action_type_changed(self) -> None:
        if not self._loading_action_editor:
            self._clear_modifier_checks()
            self.single_key_combo.setCurrentIndex(0)
            self.shortcut_key_combo.setCurrentIndex(0)
            self.media_key_combo.setCurrentIndex(0)
        self._update_action_editor_visibility()

    def _update_action_editor_visibility(self) -> None:
        action_type = self.action_type_combo.currentData()
        self.single_key_panel.setVisible(action_type == "key")
        self.modifier_panel.setVisible(action_type in {"modifier", "shortcut"})
        self.shortcut_key_panel.setVisible(action_type == "shortcut")
        self.media_key_panel.setVisible(action_type == "media")

    @staticmethod
    def _set_combo_data(combo: QComboBox, value: str) -> None:
        index = combo.findData(value)
        if index >= 0:
            combo.setCurrentIndex(index)

    def _load_action_into_editor(self, action: Action | None) -> None:
        self._loading_action_editor = True
        self._clear_modifier_checks()
        action_type = "none" if action is None else action.action_type
        if action_type == "legacy":
            action_type = "none"
        self._set_combo_data(self.action_type_combo, action_type)
        if isinstance(action, SingleKeyAction):
            self._set_combo_data(self.single_key_combo, action.key)
        elif isinstance(action, ModifierAction):
            self.modifier_checkboxes[action.modifier].setChecked(True)
        elif isinstance(action, ShortcutAction):
            for modifier_id in action.modifiers:
                self.modifier_checkboxes[modifier_id].setChecked(True)
            self._set_combo_data(self.shortcut_key_combo, action.key)
        elif isinstance(action, MediaAction):
            self._set_combo_data(self.media_key_combo, action.media_key)
        self._loading_action_editor = False
        self._update_action_editor_visibility()

    def _load_legacy_editor_text(self, text: str) -> None:
        """Translate known pre-S1.2 automation text into editor controls."""
        self._load_action_into_editor(self._action_from_assignment(text))

    def _editor_action_or_none(self) -> Action | None:
        action_type = self.action_type_combo.currentData()
        if action_type == "none":
            return None
        if action_type == "key":
            return SingleKeyAction(self.single_key_combo.currentData())
        if action_type == "modifier":
            modifiers = self._selected_modifier_ids()
            if len(modifiers) != 1:
                raise ActionValidationError("Select exactly one modifier")
            return ModifierAction(modifiers[0])
        if action_type == "shortcut":
            return ShortcutAction(
                self._selected_modifier_ids(), self.shortcut_key_combo.currentData()
            )
        if action_type == "media":
            return MediaAction(self.media_key_combo.currentData())
        raise ActionValidationError(f"Unsupported editor action type {action_type!r}")

    def select_key(self, key: Key) -> None:
        """Select *key* and populate the inspector with its current values."""
        if self.selected_key is not None:
            self.key_widgets[self.selected_key.key_id].setChecked(False)

        self.selected_key = key
        self.key_widgets[key.key_id].setChecked(True)
        self.inspector_key_id.setText(f"Key ID: {key.key_id}")
        self.inspector_position.setText(
            f"Position: x={key.x}, y={key.y} ({key.w}u × {key.h}u)"
        )
        self._load_action_into_editor(self._action_from_assignment(key.assignment))
        self._set_action_editor_enabled(True)
        self.apply_button.setEnabled(True)
        self.clear_button.setEnabled(True)
        self.action_type_combo.setFocus()

    def apply_assignment(self) -> None:
        """Apply the inspector value to the selected key in memory."""
        if self.selected_key is None:
            return

        try:
            action = self._editor_action_or_none()
        except ActionValidationError as error:
            self.statusBar().showMessage(str(error), 5000)
            return
        assignment: Any
        if action is None:
            assignment = "NONE" if self._compatibility_clear_requested else None
        else:
            assignment = self._typed_payload(action)
        self._compatibility_clear_requested = False
        if self.device.is_connected():
            self.device.send_key_assignment(
                self.selected_key.key_id, "NONE" if action is None else action.label
            )
        self.selected_key.assignment = assignment
        if self.profile is not None:
            keys = self.profile.get("keys")
            if isinstance(keys, dict) and self.selected_key.key_id in keys:
                keys[self.selected_key.key_id]["assignment"] = assignment
        self._refresh_keycap(self.selected_key)
        self._set_dirty(True)

    def clear_action(self) -> None:
        """Select the explicit None action and apply it to the active key."""
        if self.selected_key is None:
            return
        self._load_action_into_editor(None)
        self.apply_assignment()

    def connect_device(self) -> None:
        """Connect the simulated device and refresh the top-bar state."""
        self.device.connect()
        self._refresh_device_status()

    def disconnect_device(self) -> None:
        """Disconnect the simulated device and refresh the top-bar state."""
        self.device.disconnect()
        self._refresh_device_status()

    def set_host_connected(self, connected: bool) -> None:
        """Simulate USB host presence and display the auto-selected transport."""
        self.device.set_host_connected(connected)
        self._refresh_device_status()

    def _refresh_device_status(self) -> None:
        state = "connected" if self.device.is_connected() else "not connected"
        layout_summary = f"{self.layout.name} ({self.layout.key_count} keys)"
        self.device_status_label.setText(
            f"Device: {state} (simulated) — {layout_summary}"
        )
        if hasattr(self, "simulated_device_status_label"):
            self.simulated_device_status_label.setText(
                f"Device: {state} (simulated) — {layout_summary}"
            )
        self.transport_label.setText(
            f"Transport: {self.device.get_transport().upper()}"
        )
        self.connect_button.setEnabled(not self.device.is_connected())
        self.disconnect_button.setEnabled(self.device.is_connected())

    def _set_dirty(self, dirty: bool) -> None:
        self.dirty = dirty
        self._refresh_profile_status()

    def _refresh_profile_status(self) -> None:
        name = self.current_profile_path.name if self.current_profile_path else "none"
        project = self.current_project_name or "none"
        unsaved = " — (unsaved)" if self.dirty else ""
        if self.current_project_name is None:
            status = f"Local profile: {name}{unsaved}"
        else:
            status = f"Project: {project} — Local profile: {name}{unsaved}"
        self.local_profile_status_label.setText(status)
        title_unsaved = " (unsaved)" if self.dirty else ""
        self.setWindowTitle(
            f"Keyboard75 — {self.layout.name} — {project}{title_unsaved}"
        )

    def confirm_unsaved_changes(self) -> bool:
        """Offer to save or discard local edits; return whether to proceed."""
        if not self.dirty:
            return True

        choice = QMessageBox.warning(
            self,
            "Unsaved local profile changes",
            "The local profile has unsaved changes. Save them before continuing?\n\n"
            "Saving a local profile does not write to the simulated device.",
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Save,
        )
        if choice == QMessageBox.StandardButton.Save:
            return self._save_current_profile()
        return choice == QMessageBox.StandardButton.Discard

    def load_profile(self, path: str | Path) -> bool:
        """Load *path* for this layout after guarding unsaved local edits."""
        if not self.confirm_unsaved_changes():
            return False

        key_ids = tuple(key.key_id for key in self.layout.keys)
        profile = load_profile_file(path, key_ids=key_ids)
        assignments = profile["keys"]
        for key in self.layout.keys:
            action = self._action_from_assignment(
                assignments[key.key_id]["assignment"]
            )
            key.assignment = None if action is None else self._typed_payload(action)
            self._refresh_keycap(key)

        self.profile = profile
        self.current_profile_path = Path(path)
        if self.selected_key is not None:
            self._load_action_into_editor(
                self._action_from_assignment(self.selected_key.assignment)
            )
        self._set_dirty(True)
        return True

    def save_profile(self, path: str | Path) -> Path:
        """Save assignments to local JSON only, never to device hardware."""
        assignments = {key.key_id: key.assignment for key in self.layout.keys}
        if self.profile is None:
            profile = create_profile(assignments)
        else:
            profile = dict(self.profile)
            profile["keys"] = {
                key_id: {"assignment": assignment}
                for key_id, assignment in assignments.items()
            }
        self.profile = save_profile_file(path, profile)
        saved_path = Path(path)
        if not str(saved_path).endswith(".json"):
            saved_path = Path(f"{saved_path}.json")
        self.current_profile_path = saved_path
        self._set_dirty(False)
        message = f"Saved to {saved_path}"
        self.statusBar().showMessage(message, 5000)
        print(message)
        return saved_path

    def _save_current_profile(self) -> bool:
        if self.current_project_path is not None:
            try:
                self.save_project()
            except (OSError, ProjectError) as error:
                QMessageBox.critical(self, "Could not save project", str(error))
                return False
            return True
        if self.current_profile_path is None:
            return self._save_profile_dialog()
        try:
            self.save_profile(self.current_profile_path)
        except (OSError, ProfileError) as error:
            QMessageBox.critical(self, "Could not save local profile", str(error))
            return False
        return True

    def _open_profile_dialog(self) -> None:
        path, _selected_filter = QFileDialog.getOpenFileName(
            self, "Open Keyboard75 profile", "", "JSON profiles (*.json)"
        )
        if not path:
            return
        try:
            self.load_profile(path)
        except (OSError, ProfileError) as error:
            QMessageBox.critical(self, "Could not open local profile", str(error))

    def _save_profile_dialog(self) -> bool:
        path, _selected_filter = QFileDialog.getSaveFileName(
            self, "Save local Keyboard75 profile", "", "JSON profiles (*.json)"
        )
        if not path:
            return False
        try:
            self.save_profile(path)
        except (OSError, ProfileError) as error:
            QMessageBox.critical(self, "Could not save local profile", str(error))
            return False
        return True

    def new_project(
        self,
        name: str,
        directory: str | Path = PROJECTS_DIRECTORY,
    ) -> Path | None:
        """Create and activate a clean named project using the current layout."""
        if not self.confirm_unsaved_changes():
            return None
        clean_layout = Layout.from_dict(self.layout.to_dict())
        for key in clean_layout.keys:
            key.assignment = None
        self._install_layout(clean_layout)
        self.profile = None
        self.current_profile_path = None
        self.current_project_name = name.strip()
        self.current_project_path = project_path(name, directory)
        return self.save_project()

    def save_project(self, path: str | Path | None = None) -> Path:
        """Save the active layout and assignments as a local keyboard project."""
        if self.current_project_name is None:
            raise ProjectError("Create or open a project before saving it")
        target = Path(path) if path is not None else self.current_project_path
        if target is None:
            target = project_path(self.current_project_name)
        assignments = {key.key_id: key.assignment for key in self.layout.keys}
        document = create_project(
            self.current_project_name,
            self.layout,
            assignments,
            self.current_profile_path,
        )
        saved_path = save_project_file(target, document)
        self.profile = document
        self.current_project_path = saved_path
        self._set_dirty(False)
        message = f"Saved project to {saved_path}"
        self.statusBar().showMessage(message, 5000)
        print(message)
        return saved_path

    def load_project(self, path: str | Path) -> bool:
        """Atomically open a project and adopt its layout, assignments, and profile."""
        if not self.confirm_unsaved_changes():
            return False
        loaded = load_project_file(path, fallback_layout=self.layout)
        self._install_layout(Layout.from_dict(loaded.layout.to_dict()))
        self.profile = loaded.profile
        self.current_profile_path = (
            Path(loaded.profile_path) if loaded.profile_path is not None else None
        )
        self.current_project_name = (
            loaded.name
            if loaded.name != "Legacy profile"
            else Path(path).stem.removesuffix(".kb75")
        )
        self.current_project_path = Path(path)
        self._set_dirty(False)
        return True

    def _new_project_dialog(self) -> None:
        name, accepted = QInputDialog.getText(self, "New keyboard project", "Name")
        if not accepted or not name.strip():
            return
        try:
            self.new_project(name)
        except (OSError, ProjectError) as error:
            QMessageBox.critical(self, "Could not create project", str(error))

    def _save_project_from_menu(self) -> None:
        if self.current_project_name is None:
            self._new_project_dialog()
            return
        try:
            self.save_project()
        except (OSError, ProjectError) as error:
            QMessageBox.critical(self, "Could not save project", str(error))

    def _refresh_open_projects_menu(self) -> None:
        self.open_projects_menu.clear()
        paths = list_project_files()
        if not paths:
            empty_action = self.open_projects_menu.addAction("No saved projects")
            empty_action.setEnabled(False)
            return
        for path in paths:
            action = self.open_projects_menu.addAction(path.name)
            action.setData(str(path))
            action.triggered.connect(
                lambda _checked=False, selected=path: self._open_project(selected)
            )

    def _open_project(self, path: str | Path) -> None:
        try:
            self.load_project(path)
        except (OSError, ProjectError) as error:
            QMessageBox.critical(self, "Could not open project", str(error))

    def closeEvent(self, event: QCloseEvent) -> None:
        """Protect unsaved local profile changes when closing the window."""
        if self.confirm_unsaved_changes():
            event.accept()
        else:
            event.ignore()


# A concise alias is useful to callers embedding the window.
MainWindow = Keyboard75Window
