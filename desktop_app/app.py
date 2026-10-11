"""PySide6 user interface for the provisional Keyboard75 layout."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .layout_model import Key, Layout, PROVISIONAL_75_LAYOUT


class Keyboard75Window(QMainWindow):
    """Main window for editing the in-memory provisional key layout."""

    def __init__(self, layout: Layout | None = None) -> None:
        super().__init__()
        self.layout = layout or Layout.from_dict(PROVISIONAL_75_LAYOUT.to_dict())
        self.selected_key: Key | None = None
        self.key_widgets: dict[str, QPushButton] = {}

        self.setWindowTitle("Keyboard75 — PROVISIONAL Layout")
        self.resize(1240, 520)

        central_widget = QWidget(self)
        root_layout = QVBoxLayout(central_widget)
        root_layout.setContentsMargins(16, 16, 16, 16)
        root_layout.setSpacing(12)

        root_layout.addWidget(self._build_top_bar())
        root_layout.addWidget(self._build_provisional_banner())

        content_layout = QHBoxLayout()
        content_layout.setSpacing(16)
        content_layout.addWidget(self._build_key_grid(), stretch=1)
        content_layout.addWidget(self._build_inspector())
        root_layout.addLayout(content_layout, stretch=1)

        self.setCentralWidget(central_widget)

    def _build_top_bar(self) -> QWidget:
        top_bar = QWidget(self)
        layout = QHBoxLayout(top_bar)
        layout.setContentsMargins(0, 0, 0, 0)

        title = QLabel("Keyboard75 Layout Editor", top_bar)
        title.setStyleSheet("font-size: 18px; font-weight: 600;")
        self.device_status_label = QLabel("Device: not connected", top_bar)
        self.device_status_label.setObjectName("deviceStatusLabel")

        layout.addWidget(title)
        layout.addStretch()
        layout.addWidget(self.device_status_label)
        return top_bar

    def _build_provisional_banner(self) -> QLabel:
        banner = QLabel("PROVISIONAL — physical key arrangement is not final", self)
        banner.setObjectName("provisionalBanner")
        banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        banner.setStyleSheet(
            "background: #f4c542; color: #241f0c; border: 2px solid #9b7600; "
            "border-radius: 5px; font-size: 16px; font-weight: 700; padding: 8px;"
        )
        return banner

    def _build_key_grid(self) -> QWidget:
        grid_container = QWidget(self)
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

        self.selected_key.assignment = self.assignment_edit.text()
        self.key_widgets[self.selected_key.key_id].setText(
            self._button_text(self.selected_key)
        )


# A concise alias is useful to callers embedding the window.
MainWindow = Keyboard75Window

