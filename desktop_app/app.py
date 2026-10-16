"""PySide6 user interface for configurable keyboard layouts."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

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
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
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
from .matrix_model import (
    DEFAULT_WIDTH_HALF_UNITS,
    MAX_WIDTH_HALF_UNITS,
    MIN_WIDTH_HALF_UNITS,
    MatrixConfig,
)
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
QPushButton[devicePressed="true"] {
    background-color: #8a4f16;
    color: #ffffff;
    border-color: #ffc36b;
    border-bottom-color: #b66e25;
}
QPushButton[devicePressed="true"]:hover {
    background-color: #9b5b1c;
}
"""


class MatrixSetupDialog(QDialog):
    """Editor for the dimensions and populated cells of a sparse matrix."""

    def __init__(
        self, config: MatrixConfig | None = None, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.setObjectName("matrixSetupDialog")
        self.setWindowTitle("Matrix layout")
        self._switches = set(config.switches) if config is not None else set()
        self._key_widths = dict(config.key_widths) if config is not None else {}
        self._key_labels = dict(config.key_labels) if config is not None else {}
        self._row_pins = list(config.row_pins) if config is not None else []
        self._column_pins = list(config.column_pins) if config is not None else []
        self._min_pin = config.min_pin if config is not None else 0
        self._max_pin = config.max_pin if config is not None else 39
        self._selected_cell: tuple[int, int] | None = None
        self.cell_checkboxes: dict[tuple[int, int], QCheckBox] = {}

        root = QVBoxLayout(self)
        dimensions = QHBoxLayout()
        self.rows_input = QSpinBox(self)
        self.rows_input.setObjectName("matrixRowsInput")
        self.rows_input.setRange(2, 32)
        self.rows_input.setValue(config.rows if config is not None else 5)
        self.cols_input = QSpinBox(self)
        self.cols_input.setObjectName("matrixColsInput")
        self.cols_input.setRange(2, 64)
        self.cols_input.setValue(config.cols if config is not None else 15)
        dimensions.addWidget(QLabel("Rows", self))
        dimensions.addWidget(self.rows_input)
        dimensions.addWidget(QLabel("Columns", self))
        dimensions.addWidget(self.cols_input)
        dimensions.addStretch()
        root.addLayout(dimensions)

        help_label = QLabel(
            "Select the intersections that contain switches. "
            "The width field applies to the last selected switch.",
            self,
        )
        help_label.setWordWrap(True)
        root.addWidget(help_label)

        self.grid_widget = QWidget(self)
        self.grid_widget.setObjectName("matrixCellGrid")
        self.grid_layout = QGridLayout(self.grid_widget)
        self.grid_layout.setContentsMargins(4, 4, 4, 4)
        self.grid_layout.setSpacing(4)
        scroll = QScrollArea(self)
        scroll.setObjectName("matrixGridScrollArea")
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.grid_widget)
        root.addWidget(scroll, stretch=1)

        width_row = QHBoxLayout()
        width_row.addWidget(QLabel("Selected key width (half-units)", self))
        self.width_input = QSpinBox(self)
        self.width_input.setObjectName("matrixKeyWidthInput")
        self.width_input.setRange(MIN_WIDTH_HALF_UNITS, MAX_WIDTH_HALF_UNITS)
        self.width_input.setValue(DEFAULT_WIDTH_HALF_UNITS)
        self.width_input.setEnabled(False)
        self.width_input.valueChanged.connect(self._set_selected_width)
        width_row.addWidget(self.width_input)
        width_row.addStretch()
        root.addLayout(width_row)

        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel, self)
        self.generate_button = self.buttons.addButton(
            "Generate", QDialogButtonBox.ButtonRole.AcceptRole
        )
        self.generate_button.setObjectName("matrixGenerateButton")
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        root.addWidget(self.buttons)

        self.rows_input.valueChanged.connect(self._rebuild_grid)
        self.cols_input.valueChanged.connect(self._rebuild_grid)
        self._rebuild_grid()
        self.resize(760, 520)

    def _rebuild_grid(self) -> None:
        """Recreate dimension headers/cells while retaining in-bounds values."""
        rows, cols = self.rows_input.value(), self.cols_input.value()
        self._switches = {
            cell for cell in self._switches if cell[0] < rows and cell[1] < cols
        }
        self._key_widths = {
            cell: width
            for cell, width in self._key_widths.items()
            if cell in self._switches
        }
        self._key_labels = {
            cell: label
            for cell, label in self._key_labels.items()
            if cell in self._switches
        }
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
        self.cell_checkboxes = {}
        for column in range(cols):
            label = QLabel(str(column), self.grid_widget)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.grid_layout.addWidget(label, 0, column + 1)
        for row in range(rows):
            label = QLabel(str(row), self.grid_widget)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.grid_layout.addWidget(label, row + 1, 0)
            for column in range(cols):
                cell = (row, column)
                checkbox = QCheckBox(self.grid_widget)
                checkbox.setObjectName(f"matrixCell_{row}_{column}")
                checkbox.setToolTip(f"Row {row}, column {column}")
                checkbox.setChecked(cell in self._switches)
                checkbox.toggled.connect(
                    lambda checked, selected=cell: self._toggle_cell(selected, checked)
                )
                self.grid_layout.addWidget(
                    checkbox,
                    row + 1,
                    column + 1,
                    alignment=Qt.AlignmentFlag.AlignCenter,
                )
                self.cell_checkboxes[cell] = checkbox
        if self._selected_cell not in self._switches:
            self._selected_cell = None
            self.width_input.setEnabled(False)

    def _toggle_cell(self, cell: tuple[int, int], checked: bool) -> None:
        self._selected_cell = cell
        if checked:
            self._switches.add(cell)
            self.width_input.blockSignals(True)
            self.width_input.setValue(
                self._key_widths.get(cell, DEFAULT_WIDTH_HALF_UNITS)
            )
            self.width_input.blockSignals(False)
            self.width_input.setEnabled(True)
        else:
            self._switches.discard(cell)
            self._key_widths.pop(cell, None)
            self._key_labels.pop(cell, None)
            self.width_input.setEnabled(False)

    def _set_selected_width(self, width: int) -> None:
        if self._selected_cell not in self._switches:
            return
        if width == DEFAULT_WIDTH_HALF_UNITS:
            self._key_widths.pop(self._selected_cell, None)
        else:
            self._key_widths[self._selected_cell] = width

    def matrix_config(self) -> MatrixConfig:
        """Return an independent model containing the current editor values."""
        return MatrixConfig(
            rows=self.rows_input.value(),
            cols=self.cols_input.value(),
            switches=set(self._switches),
            key_widths=dict(self._key_widths),
            key_labels=dict(self._key_labels),
            row_pins=(self._row_pins + [None] * self.rows_input.value())[
                : self.rows_input.value()
            ],
            column_pins=(self._column_pins + [None] * self.cols_input.value())[
                : self.cols_input.value()
            ],
            min_pin=self._min_pin,
            max_pin=self._max_pin,
        )


class MatrixPinmapDialog(QDialog):
    """Live GPIO assignment editor backed directly by a ``MatrixConfig``."""

    def __init__(
        self,
        config: MatrixConfig,
        parent: QWidget | None = None,
        changed: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("matrixPinmapDialog")
        self.setWindowTitle("Matrix GPIO pinmap")
        self.config = config
        self._changed = changed
        self.row_pin_inputs: list[QLineEdit] = []
        self.column_pin_inputs: list[QLineEdit] = []
        self.validation_errors: list[str] = []

        root = QVBoxLayout(self)
        help_label = QLabel(
            "Assign one GPIO pin to each matrix line. Leave a field blank or use "
            "- for an unassigned line.",
            self,
        )
        help_label.setWordWrap(True)
        root.addWidget(help_label)

        range_layout = QHBoxLayout()
        self.min_pin_input = QSpinBox(self)
        self.min_pin_input.setObjectName("matrixMinPinInput")
        self.min_pin_input.setRange(-99999, 99999)
        self.min_pin_input.setValue(config.min_pin)
        self.max_pin_input = QSpinBox(self)
        self.max_pin_input.setObjectName("matrixMaxPinInput")
        self.max_pin_input.setRange(-99999, 99999)
        self.max_pin_input.setValue(config.max_pin)
        range_layout.addWidget(QLabel("Allowed GPIO range", self))
        range_layout.addWidget(self.min_pin_input)
        range_layout.addWidget(QLabel("to", self))
        range_layout.addWidget(self.max_pin_input)
        range_layout.addStretch()
        root.addLayout(range_layout)

        grid_widget = QWidget(self)
        grid_widget.setObjectName("matrixPinmapGrid")
        grid = QGridLayout(grid_widget)
        grid.addWidget(QLabel("Matrix line", grid_widget), 0, 0)
        grid.addWidget(QLabel("GPIO pin", grid_widget), 0, 1)
        grid_row = 1
        for index, pin in enumerate(config.row_pins):
            editor = self._make_pin_editor("row", index, pin, grid_widget)
            self.row_pin_inputs.append(editor)
            grid.addWidget(QLabel(f"Row {index}", grid_widget), grid_row, 0)
            grid.addWidget(editor, grid_row, 1)
            grid_row += 1
        for index, pin in enumerate(config.column_pins):
            editor = self._make_pin_editor("column", index, pin, grid_widget)
            self.column_pin_inputs.append(editor)
            grid.addWidget(QLabel(f"Column {index}", grid_widget), grid_row, 0)
            grid.addWidget(editor, grid_row, 1)
            grid_row += 1

        scroll = QScrollArea(self)
        scroll.setObjectName("matrixPinmapScrollArea")
        scroll.setWidgetResizable(True)
        scroll.setWidget(grid_widget)
        root.addWidget(scroll, stretch=1)

        action_layout = QHBoxLayout()
        self.suggest_button = QPushButton("Suggest pins", self)
        self.suggest_button.setObjectName("matrixPinmapSuggestButton")
        self.clear_button = QPushButton("Clear pins", self)
        self.clear_button.setObjectName("matrixPinmapClearButton")
        action_layout.addWidget(self.suggest_button)
        action_layout.addWidget(self.clear_button)
        action_layout.addStretch()
        root.addLayout(action_layout)

        self.status_label = QLabel(self)
        self.status_label.setObjectName("matrixPinmapStatusLabel")
        self.status_label.setWordWrap(True)
        root.addWidget(self.status_label)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        self.min_pin_input.valueChanged.connect(self._pin_range_changed)
        self.max_pin_input.valueChanged.connect(self._pin_range_changed)
        self.suggest_button.clicked.connect(self.suggest_pins)
        self.clear_button.clicked.connect(self.clear_pins)
        self.refresh_validation()
        self.resize(430, 520)

    def _make_pin_editor(
        self, kind: str, index: int, pin: Any, parent: QWidget
    ) -> QLineEdit:
        editor = QLineEdit(parent)
        title_kind = "Row" if kind == "row" else "Column"
        editor.setObjectName(f"matrix{title_kind}Pin_{index}")
        editor.setPlaceholderText("-")
        editor.setText("" if pin is None else str(pin))
        editor.textChanged.connect(
            lambda text, line_kind=kind, line_index=index: self._pin_changed(
                line_kind, line_index, text
            )
        )
        return editor

    @staticmethod
    def _pin_value(text: str) -> int | None | str:
        stripped = text.strip()
        if not stripped or stripped == "-":
            return None
        try:
            return int(stripped)
        except ValueError:
            return stripped

    def _pin_changed(self, kind: str, index: int, text: str) -> None:
        pins = self.config.row_pins if kind == "row" else self.config.column_pins
        pins[index] = self._pin_value(text)  # type: ignore[assignment]
        self._notify_changed()

    def _pin_range_changed(self) -> None:
        self.config.min_pin = self.min_pin_input.value()
        self.config.max_pin = self.max_pin_input.value()
        self._notify_changed()

    def _notify_changed(self) -> None:
        self.refresh_validation()
        if self._changed is not None:
            self._changed()

    def refresh_validation(self) -> bool:
        """Render model validation without changing the entered state."""
        ok, errors = self.config.validate()
        self.validation_errors = errors
        self.status_label.setProperty("valid", ok)
        if ok:
            self.status_label.setText("Pinmap valid")
            self.status_label.setStyleSheet("color: #79c98b;")
        else:
            self.status_label.setText("Invalid pinmap:\n" + "\n".join(errors))
            self.status_label.setStyleSheet("color: #ef7777;")
        return ok

    def _show_model_pins(self) -> None:
        for editor, pin in zip(self.row_pin_inputs, self.config.row_pins):
            editor.blockSignals(True)
            editor.setText("" if pin is None else str(pin))
            editor.blockSignals(False)
        for editor, pin in zip(self.column_pin_inputs, self.config.column_pins):
            editor.blockSignals(True)
            editor.setText("" if pin is None else str(pin))
            editor.blockSignals(False)

    def clear_pins(self) -> None:
        """Clear every row and column assignment."""
        self.config.row_pins[:] = [None] * self.config.rows
        self.config.column_pins[:] = [None] * self.config.cols
        self._show_model_pins()
        self._notify_changed()

    def suggest_pins(self) -> None:
        """Assign distinct in-range pins in row-first, column-second order."""
        available = iter(range(self.config.min_pin, self.config.max_pin + 1))
        assignments = [
            next(available, None)
            for _ in range(self.config.rows + self.config.cols)
        ]
        self.config.row_pins[:] = assignments[: self.config.rows]
        self.config.column_pins[:] = assignments[self.config.rows :]
        self._show_model_pins()
        self._notify_changed()


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
        self.device.add_pressed_state_listener(self.refresh_pressed_key_highlights)
        self.selected_key: Key | None = None
        self.key_widgets: dict[str, QPushButton] = {}
        self.profile: dict[str, object] | None = None
        self.current_profile_path: Path | None = None
        self.current_project_name: str | None = None
        self.current_project_path: Path | None = None
        self.matrix_config: MatrixConfig | None = None
        self.matrix_layout: Layout | None = None
        self.matrix_setup_dialog: MatrixSetupDialog | None = None
        self.matrix_pinmap_dialog: MatrixPinmapDialog | None = None
        self.dirty = False
        self._compatibility_clear_requested = False
        self._loading_matrix_editor = False

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
        matrix_action = QAction("Matrix...", self)
        matrix_action.setObjectName("matrixLayoutAction")
        matrix_action.triggered.connect(self._open_matrix_layout_dialog)
        layout_menu.addAction(matrix_action)

        self.saved_matrix_action = QAction("Use generated matrix", self)
        self.saved_matrix_action.setObjectName("savedMatrixLayoutAction")
        self.saved_matrix_action.setEnabled(False)
        self.saved_matrix_action.triggered.connect(self.switch_to_matrix_layout)
        layout_menu.addAction(self.saved_matrix_action)

        self.matrix_pinmap_action = QAction("GPIO pinmap...", self)
        self.matrix_pinmap_action.setObjectName("matrixPinmapAction")
        self.matrix_pinmap_action.setEnabled(False)
        self.matrix_pinmap_action.triggered.connect(self.open_matrix_pinmap)
        layout_menu.addAction(self.matrix_pinmap_action)

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

        title = QLabel("Keyboard DM Layout Editor", top_bar)
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
            if self.layout.label == "matrix":
                half_unit_width = (key_width - spacing) / 2
                rendered_width = round(
                    key.w * half_unit_width + max(0, key.w - 1) * spacing
                )
                button.setFixedSize(rendered_width, key_height)
            else:
                button.setFixedSize(key_width, key_height)
            button.setStyleSheet(KEYCAP_STYLESHEET)
            button.clicked.connect(
                lambda _checked=False, selected=key: self.select_key(selected)
            )
            grid_column = key.x * 2 if self.layout.label == "matrix" else key.x
            grid.addWidget(button, key.y, grid_column, key.h, key.w)
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
        if self.layout.label == "matrix" and self.matrix_layout is not None:
            self.matrix_layout = Layout.from_dict(self.layout.to_dict())
        new_layout = Layout.from_dict(layout.to_dict())
        for key in new_layout.keys:
            if key.key_id in previous_assignments:
                key.assignment = previous_assignments[key.key_id]

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
        self.matrix_key_panel.setVisible(False)
        self.matrix_edit_warning.clear()

        old_grid = self.key_grid_container
        self.layout = new_layout
        self.matrix_pinmap_action.setEnabled(
            self.layout.label == "matrix" and self.matrix_config is not None
        )
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
        self.device.set_matrix_config(
            self.matrix_config if self.layout.label == "matrix" else None
        )
        self.refresh_pressed_key_highlights()
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

    def _open_matrix_layout_dialog(self) -> None:
        dialog = MatrixSetupDialog(self.matrix_config, self)
        self.matrix_setup_dialog = dialog
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        config = dialog.matrix_config()
        ok, errors = config.validate()
        if not ok:
            QMessageBox.critical(
                self, "Could not create matrix layout", "\n".join(errors)
            )
            return
        generated = config.to_layout()
        if self.matrix_layout is not None:
            assignments = {key.key_id: key.assignment for key in self.matrix_layout.keys}
            for key in generated.keys:
                if key.key_id in assignments:
                    key.assignment = assignments[key.key_id]
        if not self.switch_layout(generated):
            return
        self.matrix_config = MatrixConfig.from_dict(config.to_dict())
        self.matrix_layout = Layout.from_dict(self.layout.to_dict())
        self.saved_matrix_action.setEnabled(True)
        self.matrix_pinmap_action.setEnabled(True)

    def open_matrix_pinmap(self) -> MatrixPinmapDialog | None:
        """Open the GPIO editor for the active generated matrix."""
        if self.layout.label != "matrix" or self.matrix_config is None:
            return None
        dialog = MatrixPinmapDialog(
            self.matrix_config, self, changed=lambda: self._set_dirty(True)
        )
        self.matrix_pinmap_dialog = dialog
        dialog.exec()
        return dialog

    def switch_to_matrix_layout(self) -> bool:
        """Activate the last generated matrix without reopening its editor."""
        if self.matrix_layout is None:
            self._open_matrix_layout_dialog()
            return self.matrix_layout is not None
        return self.switch_layout(self.matrix_layout)

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

        self.matrix_key_panel = QWidget(inspector)
        self.matrix_key_panel.setObjectName("matrixKeyPanel")
        matrix_form = QFormLayout(self.matrix_key_panel)
        matrix_form.setContentsMargins(0, 0, 0, 0)
        matrix_form.setSpacing(5)
        self.matrix_label_input = QLineEdit(self.matrix_key_panel)
        self.matrix_label_input.setObjectName("matrixKeyLabelInput")
        matrix_form.addRow("Display label", self.matrix_label_input)
        self.matrix_width_input = QComboBox(self.matrix_key_panel)
        self.matrix_width_input.setObjectName("matrixKeyWidthCombo")
        for half_units in range(MIN_WIDTH_HALF_UNITS, MAX_WIDTH_HALF_UNITS + 1):
            self.matrix_width_input.addItem(f"{half_units / 2:g}u", half_units)
        matrix_form.addRow("Width", self.matrix_width_input)
        self.matrix_row_input = QSpinBox(self.matrix_key_panel)
        self.matrix_row_input.setObjectName("matrixKeyRowInput")
        self.matrix_col_input = QSpinBox(self.matrix_key_panel)
        self.matrix_col_input.setObjectName("matrixKeyColumnInput")
        matrix_form.addRow("Row (0-based)", self.matrix_row_input)
        matrix_form.addRow("Column (0-based)", self.matrix_col_input)
        self.matrix_move_button = QPushButton("Move key", self.matrix_key_panel)
        self.matrix_move_button.setObjectName("matrixKeyMoveButton")
        matrix_form.addRow(self.matrix_move_button)
        self.matrix_edit_warning = QLabel(self.matrix_key_panel)
        self.matrix_edit_warning.setObjectName("matrixKeyEditWarning")
        self.matrix_edit_warning.setWordWrap(True)
        self.matrix_edit_warning.setStyleSheet("color: #e1b866;")
        matrix_form.addRow(self.matrix_edit_warning)
        self.matrix_key_panel.setVisible(False)

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
        layout.addWidget(self.matrix_key_panel)
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
        self.matrix_label_input.textChanged.connect(self._matrix_label_changed)
        self.matrix_width_input.currentIndexChanged.connect(
            self._matrix_width_changed
        )
        self.matrix_move_button.clicked.connect(self.move_selected_matrix_key)
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
    def _device_assignment(cls, assignment: Any) -> dict[str, Any] | None:
        action = cls._action_from_assignment(assignment)
        return None if action is None else cls._typed_payload(action)

    @classmethod
    def _button_text(cls, key: Key) -> str:
        assignment_label = cls._assignment_label(key.assignment)
        base_label = key.label or key.key_id
        return (
            base_label
            if assignment_label is None
            else f"{base_label}\n{assignment_label}"
        )

    def _refresh_keycap(self, key: Key) -> None:
        button = self.key_widgets[key.key_id]
        assignment_label = self._assignment_label(key.assignment)
        button.setText(self._button_text(key))
        tooltip_parts = [key.key_id]
        if key.label:
            tooltip_parts.append(key.label)
        if assignment_label is not None:
            tooltip_parts.append(assignment_label)
        button.setToolTip(": ".join(tooltip_parts))
        font = button.font()
        label_length = max(len(key.label or key.key_id), len(assignment_label or ""))
        font.setPointSize(7 if label_length > 12 else 8 if label_length > 8 else 9)
        button.setFont(font)

    def refresh_pressed_key_highlights(self) -> None:
        """Apply simulated device press state to the matching visible keycaps."""
        pressed_key_ids = self.device.get_pressed_key_ids()
        for key_id, button in self.key_widgets.items():
            pressed = key_id in pressed_key_ids
            button.setProperty("devicePressed", pressed)
            button.setDown(pressed)
            button.style().unpolish(button)
            button.style().polish(button)
            button.update()

    def _selected_matrix_cell(self) -> tuple[int, int] | None:
        if (
            self.selected_key is None
            or self.layout.label != "matrix"
            or self.matrix_config is None
        ):
            return None
        cell = (self.selected_key.y, self.selected_key.x)
        return cell if cell in self.matrix_config.switches else None

    def _load_matrix_key_editor(self, key: Key) -> None:
        is_matrix_key = (
            self.layout.label == "matrix" and self.matrix_config is not None
        )
        self.matrix_key_panel.setVisible(is_matrix_key)
        if not is_matrix_key:
            self.matrix_edit_warning.clear()
            return
        cell = (key.y, key.x)
        self._loading_matrix_editor = True
        self.matrix_label_input.setText(self.matrix_config.label_for(cell))
        self._set_combo_data(
            self.matrix_width_input, self.matrix_config.width_for(cell)
        )
        # Keep invalid values enterable so the move action can reject them with
        # an explicit message instead of silently clamping to a different cell.
        self.matrix_row_input.setRange(-1, 999)
        self.matrix_col_input.setRange(-1, 999)
        self.matrix_row_input.setValue(cell[0])
        self.matrix_col_input.setValue(cell[1])
        self._loading_matrix_editor = False
        self._show_matrix_overflow_warning()

    def _matrix_label_changed(self, label: str) -> None:
        if self._loading_matrix_editor:
            return
        cell = self._selected_matrix_cell()
        if cell is None:
            return
        if label:
            self.matrix_config.key_labels[cell] = label
        else:
            self.matrix_config.key_labels.pop(cell, None)
        self._regenerate_matrix_layout(cell)

    def _matrix_width_changed(self) -> None:
        if self._loading_matrix_editor:
            return
        cell = self._selected_matrix_cell()
        if cell is None:
            return
        half_units = self.matrix_width_input.currentData()
        if half_units == DEFAULT_WIDTH_HALF_UNITS:
            self.matrix_config.key_widths.pop(cell, None)
        else:
            self.matrix_config.key_widths[cell] = half_units
        self._regenerate_matrix_layout(cell)

    def _show_matrix_overflow_warning(self) -> None:
        if self.matrix_config is None:
            self.matrix_edit_warning.clear()
            return
        overflowing_rows = sorted(
            {
                row
                for row, column in self.matrix_config.switches
                if column * 2 + self.matrix_config.width_for((row, column))
                > self.matrix_config.cols * 2
            }
        )
        if overflowing_rows:
            row_list = ", ".join(str(row) for row in overflowing_rows)
            message = f"Warning: key width overflows matrix row {row_list}."
            self.matrix_edit_warning.setText(message)
            self.statusBar().showMessage(message, 5000)
        else:
            self.matrix_edit_warning.clear()

    def _regenerate_matrix_layout(
        self,
        selected_cell: tuple[int, int],
        moved_from: tuple[int, int] | None = None,
    ) -> None:
        """Regenerate the matrix view from its authoritative config."""
        if self.matrix_config is None:
            return
        assignments = {key.key_id: key.assignment for key in self.layout.keys}
        if moved_from is not None:
            old_id = f"MX-{moved_from[0]:02d}-{moved_from[1]:02d}"
            new_id = f"MX-{selected_cell[0]:02d}-{selected_cell[1]:02d}"
            assignments[new_id] = assignments.pop(old_id, None)
        generated = self.matrix_config.to_layout(self.layout.name or "Matrix")
        for key in generated.keys:
            if key.key_id in assignments:
                key.assignment = assignments[key.key_id]
        self.matrix_layout = Layout.from_dict(generated.to_dict())
        self._install_layout(generated)
        selected_id = self.matrix_config.key_id_for_cell(selected_cell)
        selected_key = next(
            (key for key in self.layout.keys if key.key_id == selected_id), None
        )
        if selected_key is not None:
            self.select_key(selected_key)
        self._set_dirty(True)

    def move_selected_matrix_key(self) -> bool:
        """Move the selected switch to an empty in-bounds matrix cell."""
        old_cell = self._selected_matrix_cell()
        if old_cell is None or self.matrix_config is None:
            return False
        new_cell = (self.matrix_row_input.value(), self.matrix_col_input.value())
        if new_cell == old_cell:
            return True
        if not (
            0 <= new_cell[0] < self.matrix_config.rows
            and 0 <= new_cell[1] < self.matrix_config.cols
        ):
            message = "The destination cell is outside the matrix bounds."
            QMessageBox.warning(self, "Could not move matrix key", message)
            self.statusBar().showMessage(message, 5000)
            self._load_matrix_key_editor(self.selected_key)
            return False
        if new_cell in self.matrix_config.switches:
            message = (
                f"Matrix cell ({new_cell[0]}, {new_cell[1]}) is already occupied."
            )
            QMessageBox.warning(self, "Could not move matrix key", message)
            self.statusBar().showMessage(message, 5000)
            self._load_matrix_key_editor(self.selected_key)
            return False

        width = self.matrix_config.key_widths.pop(old_cell, None)
        label = self.matrix_config.key_labels.pop(old_cell, None)
        self.matrix_config.switches.remove(old_cell)
        self.matrix_config.switches.add(new_cell)
        if width is not None:
            self.matrix_config.key_widths[new_cell] = width
        if label is not None:
            self.matrix_config.key_labels[new_cell] = label
        self._move_profile_assignment(old_cell, new_cell)
        self._regenerate_matrix_layout(new_cell, moved_from=old_cell)
        return True

    def _move_profile_assignment(
        self, old_cell: tuple[int, int], new_cell: tuple[int, int]
    ) -> None:
        if self.profile is None:
            return
        keys = self.profile.get("keys")
        if not isinstance(keys, dict):
            return
        old_id = f"MX-{old_cell[0]:02d}-{old_cell[1]:02d}"
        new_id = f"MX-{new_cell[0]:02d}-{new_cell[1]:02d}"
        if old_id in keys:
            keys[new_id] = keys.pop(old_id)

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
        width_u = key.w / 2 if self.layout.label == "matrix" else key.w
        self.inspector_position.setText(
            f"Position: x={key.x}, y={key.y} ({width_u:g}u × {key.h}u)"
        )
        self._load_matrix_key_editor(key)
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
                self.selected_key.key_id,
                None if action is None else self._typed_payload(action),
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
            f"Keyboard DM — {self.layout.name} — {project}{title_unsaved}"
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
            self, "Open Keyboard DM profile", "", "JSON profiles (*.json)"
        )
        if not path:
            return
        try:
            self.load_profile(path)
        except (OSError, ProfileError) as error:
            QMessageBox.critical(self, "Could not open local profile", str(error))

    def _save_profile_dialog(self) -> bool:
        path, _selected_filter = QFileDialog.getSaveFileName(
            self, "Save local Keyboard DM profile", "", "JSON profiles (*.json)"
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
            self.matrix_config if self.layout.label == "matrix" else None,
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
        self.matrix_config = (
            MatrixConfig.from_dict(loaded.matrix_config.to_dict())
            if loaded.matrix_config is not None
            else None
        )
        self.matrix_layout = (
            Layout.from_dict(loaded.layout.to_dict())
            if loaded.matrix_config is not None
            else None
        )
        self.saved_matrix_action.setEnabled(self.matrix_layout is not None)
        self.matrix_pinmap_action.setEnabled(
            self.layout.label == "matrix" and self.matrix_config is not None
        )
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
