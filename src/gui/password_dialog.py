"""
gui/password_dialog.py — Password manager dialog for VARA Term.

Manages per-station passwords for HMAC-SHA256 authentication.
"""

import logging
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QHeaderView, QLabel, QLineEdit, QComboBox,
    QMessageBox, QDialogButtonBox, QFormLayout, QGroupBox, QCheckBox,
)
from PyQt6.QtCore import Qt

from gui.theme import info_style

log = logging.getLogger(__name__)


class PasswordDialog(QDialog):
    """Password manager for saved BBS station credentials."""

    def __init__(self, password_store, parent=None):
        super().__init__(parent)
        self.store = password_store
        self.setWindowTitle("Password Manager")
        self.setMinimumWidth(550)
        self.setMinimumHeight(350)
        if parent and parent.styleSheet():
            self.setStyleSheet(parent.styleSheet())
        self._build_ui()
        self._refresh_table()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        info = QLabel(
            "Manage passwords for BBS stations. Passwords are encrypted\n"
            "at rest and used for HMAC-SHA256 challenge-response authentication."
        )
        info.setStyleSheet(info_style("4px 0 8px 0"))
        layout.addWidget(info)

        # Table
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(
            ["Target Callsign", "Password", "Auth Mode", "Last Used"]
        )
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table)

        # Buttons
        btn_layout = QHBoxLayout()
        add_btn = QPushButton("Add")
        add_btn.clicked.connect(self._add_password)
        edit_btn = QPushButton("Edit")
        edit_btn.clicked.connect(self._edit_password)
        remove_btn = QPushButton("Remove")
        remove_btn.clicked.connect(self._remove_password)
        btn_layout.addWidget(add_btn)
        btn_layout.addWidget(edit_btn)
        btn_layout.addWidget(remove_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # Close
        close_btn = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close_btn.rejected.connect(self.accept)
        layout.addWidget(close_btn)

    def _refresh_table(self):
        entries = self.store.get_all()
        self.table.setRowCount(len(entries))
        for row, (callsign, data) in enumerate(sorted(entries.items())):
            self.table.setItem(row, 0, QTableWidgetItem(callsign))
            self.table.setItem(row, 1, QTableWidgetItem("●●●●●●●●"))
            self.table.setItem(row, 2, QTableWidgetItem(
                data.get("auth_mode", "HMAC-SHA256")))
            self.table.setItem(row, 3, QTableWidgetItem(
                data.get("last_used", "Never")))

    def _add_password(self):
        dlg = _PasswordEntryDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.store.set_password(dlg.callsign, dlg.password, dlg.auth_mode)
            self._refresh_table()

    def _edit_password(self):
        row = self.table.currentRow()
        if row < 0:
            return
        callsign = self.table.item(row, 0).text()
        current_pw = self.store.get_password(callsign) or ""
        dlg = _PasswordEntryDialog(self, callsign=callsign, password=current_pw)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.store.set_password(dlg.callsign, dlg.password, dlg.auth_mode)
            self._refresh_table()

    def _remove_password(self):
        row = self.table.currentRow()
        if row < 0:
            return
        callsign = self.table.item(row, 0).text()
        reply = QMessageBox.question(
            self, "Confirm Removal",
            f"Remove saved password for {callsign}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.store.remove_password(callsign)
            self._refresh_table()


class _PasswordEntryDialog(QDialog):
    """Dialog for adding/editing a single password entry."""

    def __init__(self, parent, callsign: str = "", password: str = ""):
        super().__init__(parent)
        self.setWindowTitle("Add Password" if not callsign else "Edit Password")
        self.setMinimumWidth(350)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.call_input = QLineEdit(callsign)
        self.call_input.setPlaceholderText("e.g. KK4ODA-5")
        if callsign:
            self.call_input.setReadOnly(True)
        form.addRow("Target Callsign:", self.call_input)

        self.pw_input = QLineEdit(password)
        self.pw_input.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Password:", self.pw_input)

        self.show_pw = QCheckBox("Show password")
        self.show_pw.toggled.connect(
            lambda on: self.pw_input.setEchoMode(
                QLineEdit.EchoMode.Normal if on else QLineEdit.EchoMode.Password
            )
        )
        form.addRow(self.show_pw)

        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["HMAC-SHA256", "Plaintext Fallback"])
        self.mode_combo.setToolTip(
            "HMAC-SHA256 = secure challenge-response (recommended).\n"
            "Password is never sent over RF.\n"
            "Plaintext Fallback = sends password if HMAC fails."
        )
        form.addRow("Auth Mode:", self.mode_combo)

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._validate)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _validate(self):
        if not self.call_input.text().strip():
            QMessageBox.warning(self, "Error", "Callsign is required")
            return
        if not self.pw_input.text():
            QMessageBox.warning(self, "Error", "Password is required")
            return
        self.accept()

    @property
    def callsign(self) -> str:
        return self.call_input.text().upper().strip()

    @property
    def password(self) -> str:
        return self.pw_input.text()

    @property
    def auth_mode(self) -> str:
        return self.mode_combo.currentText()
