"""PySide6 user interface for configurable keyboard layouts."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QCloseEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
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


class Keyboard75Window(QMainWindow):
    """Main window for editing an in-memory keyboard layout."""

    def __init__(
        self,
        layout: Layout | None = None,
        device: SimulatedESP32S3Device | None = None,
    ) -> None:
        super().__init__()
        self.layout = Layout.from_dict((layout or L75).to_dict())
        self.device = device or SimulatedESP32S3Device(
            key.key_id for key in self.layout.keys
        )
        if device is not None:
            self.device.set_key_ids(key.key_id for key in self.layout.keys)
        self.selected_key: Key | None = None
        self.key_widgets: dict[str, QPushButton] = {}
        self.profile: dict[str, object] | None = None
        self.current_profile_path: Path | None = None
        self.dirty = False

        self.resize(1240, 520)
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
        self.content_layout.addWidget(self._build_inspector())
        root_layout.addLayout(self.content_layout, stretch=1)

        self.setCentralWidget(central_widget)
        self._build_status_bar()
        self._refresh_profile_status()

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
        layout = QHBoxLayout(top_bar)
        layout.setContentsMargins(0, 0, 0, 0)

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

        layout.addWidget(title)
        layout.addStretch()
        layout.addWidget(self.host_connected_checkbox)
        layout.addWidget(self.device_status_label)
        layout.addWidget(self.transport_label)
        layout.addWidget(self.connect_button)
        layout.addWidget(self.disconnect_button)
        self._refresh_device_status()
        return top_bar

    def _build_provisional_banner(self) -> QLabel:
        banner = QLabel(self.layout.label, self)
        banner.setObjectName("provisionalBanner")
        banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        banner.setStyleSheet(
            "background: #f4c542; color: #241f0c; border: 2px solid #9b7600; "
            "border-radius: 5px; font-size: 16px; font-weight: 700; padding: 8px;"
        )
        return banner

    def _build_key_grid(self) -> QWidget:
        grid_container = QWidget(self)
        self.key_widgets = {}
        grid = QGridLayout(grid_container)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(5)
        grid.setVerticalSpacing(5)

        for key in self.layout.keys:
            button = QPushButton(self._button_text(key), grid_container)
            button.setObjectName(f"keyButton_{key.key_id}")
            button.setCheckable(True)
            button.setMinimumSize(58, 58)
            button.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
            )
            button.setStyleSheet(
                "QPushButton { background: #f7f7f7; color: #202020; "
                "border: 1px solid #777; border-bottom: 4px solid #555; "
                "border-radius: 7px; padding: 4px; font-weight: 600; } "
                "QPushButton:hover { background: #ffffff; } "
                "QPushButton:checked { background: #cfe5ff; border-color: #2774b8; "
                "border-bottom: 4px solid #18558a; }"
            )
            button.clicked.connect(
                lambda _checked=False, selected=key: self.select_key(selected)
            )
            grid.addWidget(button, key.y, key.x, key.h, key.w)
            self.key_widgets[key.key_id] = button

        return grid_container

    def switch_layout(self, layout: Layout) -> bool:
        """Switch to a copy of *layout* while retaining shared assignments."""
        if not self.confirm_unsaved_changes():
            return False

        previous_assignments = {
            key.key_id: key.assignment for key in self.layout.keys
        }
        new_layout = Layout.from_dict(layout.to_dict())
        for key in new_layout.keys:
            key.assignment = previous_assignments.get(key.key_id, "NONE")

        self.selected_key = None
        self.assignment_edit.clear()
        self.assignment_edit.setEnabled(False)
        self.apply_button.setEnabled(False)
        self.inspector_key_id.setText("Key ID: Select a key")
        self.inspector_position.setText("Position: —")

        old_grid = self.key_grid_container
        self.layout = new_layout
        self.key_grid_container = self._build_key_grid()
        self.content_layout.replaceWidget(old_grid, self.key_grid_container)
        old_grid.deleteLater()
        self.layout_banner.setText(self.layout.label)
        self.device.set_key_ids(key.key_id for key in self.layout.keys)
        self._set_dirty(True)
        return True

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

        assignment_label = QLabel("Assignment", inspector)
        self.assignment_edit = QLineEdit(inspector)
        self.assignment_edit.setObjectName("assignmentEdit")
        self.assignment_edit.setMaxLength(32)
        self.assignment_edit.setEnabled(False)
        self.assignment_edit.returnPressed.connect(self.apply_assignment)

        self.apply_button = QPushButton("Apply", inspector)
        self.apply_button.setObjectName("applyButton")
        self.apply_button.setEnabled(False)
        self.apply_button.clicked.connect(self.apply_assignment)

        layout.addWidget(heading)
        layout.addSpacing(8)
        layout.addWidget(self.inspector_key_id)
        layout.addWidget(self.inspector_position)
        layout.addSpacing(12)
        layout.addWidget(assignment_label)
        layout.addWidget(self.assignment_edit)
        layout.addWidget(self.apply_button)
        layout.addStretch()
        return inspector

    @staticmethod
    def _button_text(key: Key) -> str:
        return f"{key.key_id}\n{key.assignment}"

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
        self.assignment_edit.setText(key.assignment)
        self.assignment_edit.setEnabled(True)
        self.apply_button.setEnabled(True)
        self.assignment_edit.setFocus()
        self.assignment_edit.selectAll()

    def apply_assignment(self) -> None:
        """Apply the inspector value to the selected key in memory."""
        if self.selected_key is None:
            return

        assignment = self.assignment_edit.text()
        if self.device.is_connected():
            self.device.send_key_assignment(self.selected_key.key_id, assignment)
        self.selected_key.assignment = assignment
        self.key_widgets[self.selected_key.key_id].setText(
            self._button_text(self.selected_key)
        )
        self._set_dirty(True)

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
        self.device_status_label.setText(f"Device: {state} (simulated)")
        if hasattr(self, "simulated_device_status_label"):
            self.simulated_device_status_label.setText(
                f"Device: {state} (simulated)"
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
        unsaved = " — (unsaved)" if self.dirty else ""
        self.local_profile_status_label.setText(f"Local profile: {name}{unsaved}")
        title_unsaved = " (unsaved)" if self.dirty else ""
        self.setWindowTitle(f"Keyboard75 — {name}{title_unsaved}")

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
            key.assignment = assignments[key.key_id]["assignment"]
            self.key_widgets[key.key_id].setText(self._button_text(key))

        self.profile = profile
        self.current_profile_path = Path(path)
        if self.selected_key is not None:
            self.assignment_edit.setText(self.selected_key.assignment)
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

    def closeEvent(self, event: QCloseEvent) -> None:
        """Protect unsaved local profile changes when closing the window."""
        if self.confirm_unsaved_changes():
            event.accept()
        else:
            event.ignore()


# A concise alias is useful to callers embedding the window.
MainWindow = Keyboard75Window
