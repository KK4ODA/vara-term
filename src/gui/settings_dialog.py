"""
gui/settings_dialog.py — Settings/configuration dialog for VARA Term.

Four tabs: Terminal Setup, Modem Configuration, Security, Macros.
Each tab wraps its content in a QScrollArea so nothing is clipped
at any dialog size.
"""

import logging
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
    QFormLayout, QLineEdit, QSpinBox, QComboBox, QCheckBox,
    QPushButton, QLabel, QGroupBox, QFileDialog, QRadioButton,
    QButtonGroup, QDialogButtonBox, QScrollArea, QFrame,
)
from PyQt6.QtCore import Qt

from gui.theme import hint_style, info_style, settings_scroll_style

log = logging.getLogger(__name__)


class SettingsDialog(QDialog):
    """Main settings dialog with tabbed interface."""

    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("VARA Term Settings")
        self.setMinimumWidth(520)
        self.setMinimumHeight(460)
        self.resize(560, 580)  # comfortable default
        # Apply dark theme from parent (ensures consistent styling)
        if parent and parent.styleSheet():
            self.setStyleSheet(parent.styleSheet())
        self._build_ui()
        self._load_values()

    # ── UI construction ────────────────────────────────────────────

    def _build_ui(self):
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()

        self.tabs.addTab(self._build_terminal_tab(), "Terminal Setup")
        self.tabs.addTab(self._build_modem_tab(), "Modem Configuration")
        self.tabs.addTab(self._build_auth_tab(), "Security")
        self.tabs.addTab(self._build_macros_tab(), "Macros")

        layout.addWidget(self.tabs)

        # OK / Cancel
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save_and_close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    @staticmethod
    def _make_scrollable(inner: QWidget) -> QScrollArea:
        """Wrap a widget in a frameless QScrollArea for tab content."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet(settings_scroll_style())
        scroll.setWidget(inner)
        return scroll

    # ── Terminal Setup Tab ─────────────────────────────────────────

    def _build_terminal_tab(self) -> QScrollArea:
        w = QWidget()
        layout = QVBoxLayout(w)

        # Identity group
        id_group = QGroupBox("Station Identity")
        id_form = QFormLayout(id_group)
        self.callsign_input = QLineEdit()
        self.callsign_input.setPlaceholderText("e.g. KK4ABC")
        self.callsign_input.setMaxLength(10)
        self.callsign_input.setToolTip("Your amateur radio callsign (e.g. KK4ODA).")
        id_form.addRow("My Callsign:", self.callsign_input)

        self.ssid_spin = QSpinBox()
        self.ssid_spin.setRange(0, 15)
        self.ssid_spin.setToolTip(
            "SSID suffix (0-15). Differentiates multiple stations\n"
            "using the same callsign (e.g. KK4ODA-1)."
        )
        id_form.addRow("SSID:", self.ssid_spin)
        layout.addWidget(id_group)

        # Mode group
        mode_group = QGroupBox("VARA Mode")
        mode_layout = QHBoxLayout(mode_group)
        self.mode_group = QButtonGroup(self)
        self.fm_radio = QRadioButton("VARA FM")
        self.fm_radio.setToolTip("VHF/UHF via VARA FM modem.")
        self.hf_radio = QRadioButton("VARA HF")
        self.hf_radio.setToolTip("HF via VARA HF modem (requires PTT control).")
        self.agwpe_radio = QRadioButton("Soundmodem (AGWPE)")
        self.agwpe_radio.setToolTip("AX.25 packet via Soundmodem, Direwolf,\nor any AGWPE-compatible TNC.")
        self.mode_group.addButton(self.fm_radio)
        self.mode_group.addButton(self.hf_radio)
        self.mode_group.addButton(self.agwpe_radio)
        mode_layout.addWidget(self.fm_radio)
        mode_layout.addWidget(self.hf_radio)
        mode_layout.addWidget(self.agwpe_radio)
        layout.addWidget(mode_group)

        # HF Settings — only visible when HF mode selected
        self.hf_bw_group = QGroupBox("HF Settings")
        hf_form = QFormLayout(self.hf_bw_group)
        self.hf_bw_combo = QComboBox()
        self.hf_bw_combo.addItems(["500", "2300", "2750"])
        self.hf_bw_combo.setToolTip(
            "VARA HF session bandwidth.\n"
            "500 Hz = slower but more robust in poor conditions.\n"
            "2300 Hz = balanced (default).\n"
            "2750 Hz = fastest, needs good signal."
        )
        hf_form.addRow("Session Bandwidth (Hz):", self.hf_bw_combo)
        layout.addWidget(self.hf_bw_group)

        # FM Settings — only visible when FM mode selected
        self.fm_bw_group = QGroupBox("FM Settings")
        fm_form = QFormLayout(self.fm_bw_group)
        self.fm_bw_combo = QComboBox()
        self.fm_bw_combo.addItems(["NARROW", "WIDE"])
        self.fm_bw_combo.setToolTip(
            "VARA FM bandwidth mode.\n"
            "NARROW = 1200 Hz (12.5 kHz channel spacing).\n"
            "WIDE = 2300 Hz (25 kHz channel spacing)."
        )
        fm_form.addRow("FM Bandwidth:", self.fm_bw_combo)
        layout.addWidget(self.fm_bw_group)

        # Appearance
        appear_group = QGroupBox("Appearance")
        appear_form = QFormLayout(appear_group)
        self.font_family_combo = QComboBox()
        self.font_family_combo.addItems(["Consolas", "Courier New", "Lucida Console",
                                          "DejaVu Sans Mono", "Liberation Mono"])
        appear_form.addRow("Font:", self.font_family_combo)

        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(8, 24)
        appear_form.addRow("Font Size:", self.font_size_spin)
        layout.addWidget(appear_group)

        # Connection
        conn_group = QGroupBox("Connection")
        conn_form = QFormLayout(conn_group)
        self.max_retries_spin = QSpinBox()
        self.max_retries_spin.setRange(1, 20)
        self.max_retries_spin.setToolTip("Maximum connection retry attempts before giving up.")
        conn_form.addRow("Max Retries:", self.max_retries_spin)

        self.session_logging_cb = QCheckBox("Enable session logging")
        self.session_logging_cb.setToolTip("Save a log of each session to the logs folder.\nUseful for reviewing conversations later.")
        conn_form.addRow(self.session_logging_cb)
        self.show_ptt_cb = QCheckBox("Show PTT ON/OFF events in terminal")
        conn_form.addRow(self.show_ptt_cb)
        layout.addWidget(conn_group)

        layout.addStretch()

        # Toggle bandwidth groups and modem groups when mode changes
        self.fm_radio.toggled.connect(self._update_bw_groups)
        self.fm_radio.toggled.connect(self._update_modem_groups)
        self.hf_radio.toggled.connect(self._update_bw_groups)
        self.hf_radio.toggled.connect(self._update_modem_groups)
        self.agwpe_radio.toggled.connect(self._update_bw_groups)
        self.agwpe_radio.toggled.connect(self._update_modem_groups)

        return self._make_scrollable(w)

    # ── Modem Configuration Tab ────────────────────────────────────

    def _build_modem_tab(self) -> QScrollArea:
        w = QWidget()
        layout = QVBoxLayout(w)

        # Hint about mode switching
        mode_hint = QLabel(
            "Only the active mode's settings are used. "
            "Switch modes in the toolbar or Terminal Setup tab."
        )
        mode_hint.setStyleSheet(hint_style())
        mode_hint.setWordWrap(True)
        layout.addWidget(mode_hint)

        # VARA FM Modem
        self.fm_modem_group = QGroupBox("VARA FM Modem")
        fm_form = QFormLayout(self.fm_modem_group)
        self.fm_host = QLineEdit()
        self.fm_host.setToolTip("IP address of the VARA FM modem.\nUsually 127.0.0.1 for local.")
        fm_form.addRow("Host:", self.fm_host)
        self.fm_cmd_port = QSpinBox()
        self.fm_cmd_port.setRange(1, 65534)
        self.fm_cmd_port.setToolTip("VARA FM TCP command port (default: 8300).\nMust match VARA FM modem settings.")
        fm_form.addRow("Command Port:", self.fm_cmd_port)
        self.fm_data_port = QSpinBox()
        self.fm_data_port.setRange(2, 65535)
        self.fm_data_port.setReadOnly(True)
        self.fm_data_port.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        self.fm_data_port.setToolTip("Data port is always Command Port + 1.")
        self.fm_data_port.setStyleSheet("background: #3a3a3a; color: #888;")
        self.fm_cmd_port.valueChanged.connect(
            lambda v: self.fm_data_port.setValue(v + 1))
        fm_form.addRow("Data Port:", self.fm_data_port)
        self.fm_auto_launch = QCheckBox("Start VARA FM with VARA Term (and close on exit)")
        self.fm_auto_launch.setToolTip("Automatically start VARA FM modem when\nVARA Term launches, and close it on exit.")
        fm_form.addRow(self.fm_auto_launch)
        self.fm_exe_path = QLineEdit()
        self.fm_exe_path.setPlaceholderText(r"C:\VARA FM\VARAFM.exe")
        self.fm_exe_path.setMinimumWidth(200)
        fm_browse = QPushButton("Browse...")
        fm_browse.clicked.connect(lambda: self._browse_exe(self.fm_exe_path))
        exe_row = QHBoxLayout()
        exe_row.addWidget(self.fm_exe_path)
        exe_row.addWidget(fm_browse)
        fm_form.addRow("Executable:", exe_row)
        layout.addWidget(self.fm_modem_group)

        # VARA HF Modem
        self.hf_modem_group = QGroupBox("VARA HF Modem")
        hf_form = QFormLayout(self.hf_modem_group)
        self.hf_host = QLineEdit()
        self.hf_host.setToolTip("IP address of the VARA HF modem.\nUsually 127.0.0.1 for local.")
        hf_form.addRow("Host:", self.hf_host)
        self.hf_cmd_port = QSpinBox()
        self.hf_cmd_port.setRange(1, 65534)
        self.hf_cmd_port.setToolTip("VARA HF TCP command port (default: 8300).\nMust match VARA HF modem settings.")
        hf_form.addRow("Command Port:", self.hf_cmd_port)
        self.hf_data_port = QSpinBox()
        self.hf_data_port.setRange(2, 65535)
        self.hf_data_port.setReadOnly(True)
        self.hf_data_port.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        self.hf_data_port.setToolTip("Data port is always Command Port + 1.")
        self.hf_data_port.setStyleSheet("background: #3a3a3a; color: #888;")
        self.hf_cmd_port.valueChanged.connect(
            lambda v: self.hf_data_port.setValue(v + 1))
        hf_form.addRow("Data Port:", self.hf_data_port)
        self.hf_auto_launch = QCheckBox("Start VARA HF with VARA Term (and close on exit)")
        self.hf_auto_launch.setToolTip("Automatically start VARA HF modem when\nVARA Term launches, and close it on exit.")
        hf_form.addRow(self.hf_auto_launch)
        self.hf_exe_path = QLineEdit()
        self.hf_exe_path.setPlaceholderText(r"C:\VARA HF\VARA HF.exe")
        self.hf_exe_path.setMinimumWidth(200)
        hf_browse = QPushButton("Browse...")
        hf_browse.clicked.connect(lambda: self._browse_exe(self.hf_exe_path))
        hf_exe_row = QHBoxLayout()
        hf_exe_row.addWidget(self.hf_exe_path)
        hf_exe_row.addWidget(hf_browse)
        hf_form.addRow("Executable:", hf_exe_row)
        layout.addWidget(self.hf_modem_group)

        # PTT (HF only — FM handles PTT internally)
        self.ptt_group = QGroupBox("HF PTT Control (OmniRig)")
        ptt_form = QFormLayout(self.ptt_group)
        ptt_info = QLabel(
            "VARA FM handles PTT internally. For VARA HF, PTT is\n"
            "controlled via OmniRig (requires OmniRig + pywin32).\n"
            "Set to 'None' if your radio uses VOX."
        )
        ptt_info.setStyleSheet(info_style("0 0 6px 0"))
        ptt_form.addRow(ptt_info)
        self.hf_ptt_method = QComboBox()
        self.hf_ptt_method.addItems(["None (VOX)", "OmniRig"])
        self.hf_ptt_method.setToolTip(
            "PTT control method for VARA HF.\n"
            "None (VOX) = radio handles PTT automatically.\n"
            "OmniRig = software PTT via OmniRig COM server."
        )
        ptt_form.addRow("HF PTT Method:", self.hf_ptt_method)
        self.omnirig_rig_spin = QSpinBox()
        self.omnirig_rig_spin.setRange(1, 2)
        self.omnirig_rig_spin.setToolTip("OmniRig rig number (1 or 2).\nSelect which OmniRig rig to use for PTT.")
        ptt_form.addRow("OmniRig Rig Number:", self.omnirig_rig_spin)
        layout.addWidget(self.ptt_group)

        # Soundmodem (AGWPE) settings
        self.agwpe_group = QGroupBox("Soundmodem (AGWPE)")
        agwpe_form = QFormLayout(self.agwpe_group)
        agwpe_info = QLabel(
            "Connect via Soundmodem, Direwolf, or any AGWPE-compatible\n"
            "TNC over TCP for AX.25 packet radio."
        )
        agwpe_info.setStyleSheet(info_style("0 0 6px 0"))
        agwpe_form.addRow(agwpe_info)
        self.agwpe_host = QLineEdit()
        self.agwpe_host.setToolTip("IP address of the Soundmodem/Direwolf host.\nUsually 127.0.0.1 for local.")
        agwpe_form.addRow("Host:", self.agwpe_host)
        self.agwpe_port = QSpinBox()
        self.agwpe_port.setRange(1, 65535)
        self.agwpe_port.setToolTip("TCP port for the AGWPE interface.\nSoundmodem default: 8000.")
        agwpe_form.addRow("AGWPE Port:", self.agwpe_port)
        self.agwpe_auto_launch = QCheckBox("Auto-launch Soundmodem")
        self.agwpe_auto_launch.setToolTip(
            "Start the Soundmodem executable automatically\n"
            "when connecting in AGWPE mode."
        )
        agwpe_form.addRow(self.agwpe_auto_launch)
        self.agwpe_exe = QLineEdit()
        self.agwpe_exe.setPlaceholderText("Path to Soundmodem.exe")
        self.agwpe_exe.setToolTip("Full path to the Soundmodem executable.")
        agwpe_form.addRow("Exe Path:", self.agwpe_exe)
        layout.addWidget(self.agwpe_group)

        layout.addStretch()

        # Connect mode radio buttons (from Terminal Setup tab) to toggle groups
        self.fm_radio.toggled.connect(self._update_modem_groups)

        return self._make_scrollable(w)

    # ── Security Tab ───────────────────────────────────────────────

    def _build_auth_tab(self) -> QScrollArea:
        w = QWidget()
        layout = QVBoxLayout(w)

        options_group = QGroupBox("Authentication Options")
        opts_form = QFormLayout(options_group)
        self.auto_hmac_cb = QCheckBox("Auto-respond to HMAC challenges")
        self.auto_hmac_cb.setToolTip(
            "Automatically respond to BBS HMAC-SHA256\n"
            "authentication challenges using saved passwords.\n"
            "No password is ever sent over RF."
        )
        opts_form.addRow(self.auto_hmac_cb)
        self.plaintext_fallback_cb = QCheckBox("Allow plaintext fallback (with warning)")
        self.plaintext_fallback_cb.setToolTip(
            "If HMAC auth fails, fall back to sending the\n"
            "password in plaintext. Less secure but compatible\n"
            "with older BBS systems. A warning is shown."
        )
        opts_form.addRow(self.plaintext_fallback_cb)
        self.show_auth_cb = QCheckBox("Show auth protocol messages in terminal (debug)")
        self.show_auth_cb.setToolTip("Show the raw authentication protocol messages\nin the terminal. Useful for debugging auth issues.")
        opts_form.addRow(self.show_auth_cb)
        layout.addWidget(options_group)

        info = QLabel(
            "Passwords are managed in the main window via\n"
            "Settings → Security/Passwords.\n\n"
            "HMAC-SHA256 authentication ensures your password\n"
            "is never transmitted over RF."
        )
        info.setStyleSheet(info_style())
        layout.addWidget(info)

        layout.addStretch()
        return self._make_scrollable(w)

    # ── Macros Tab ─────────────────────────────────────────────────

    def _build_macros_tab(self) -> QScrollArea:
        w = QWidget()
        layout = QVBoxLayout(w)

        info = QLabel("Configure quick-send macro buttons (up to 8):")
        layout.addWidget(info)

        self.macro_rows = []
        for i in range(8):
            row_layout = QHBoxLayout()
            label_edit = QLineEdit()
            label_edit.setPlaceholderText(f"Label {i+1}")
            label_edit.setMaximumWidth(120)
            cmd_edit = QLineEdit()
            cmd_edit.setPlaceholderText("Command to send")
            row_layout.addWidget(QLabel(f"{i+1}."))
            row_layout.addWidget(label_edit)
            row_layout.addWidget(cmd_edit)
            self.macro_rows.append((label_edit, cmd_edit))
            layout.addLayout(row_layout)

        layout.addStretch()
        return self._make_scrollable(w)

    # ── Helpers ─────────────────────────────────────────────────────

    def _browse_exe(self, target: QLineEdit):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select VARA Executable", "",
            "Executables (*.exe);;All Files (*)")
        if path:
            target.setText(path)

    def _update_bw_groups(self):
        """Show only the active mode's bandwidth group."""
        is_fm = self.fm_radio.isChecked()
        is_agwpe = self.agwpe_radio.isChecked()
        self.fm_bw_group.setVisible(is_fm)
        self.hf_bw_group.setVisible(not is_fm and not is_agwpe)

    def _update_modem_groups(self):
        """Show/hide modem groups based on mode selection.

        All groups remain visible so settings can be configured before
        switching modes.  Only the active mode's group is fully enabled;
        inactive groups are dimmed but auto-launch checkboxes stay
        editable so they can be toggled at any time.
        """
        is_fm = self.fm_radio.isChecked()
        is_agwpe = self.agwpe_radio.isChecked()
        is_hf = self.hf_radio.isChecked()

        self.fm_modem_group.setEnabled(is_fm)
        self.hf_modem_group.setEnabled(is_hf)
        self.ptt_group.setEnabled(is_hf)
        self.agwpe_group.setEnabled(is_agwpe)

        # Auto-launch checkboxes should always be editable
        self.fm_auto_launch.setEnabled(True)
        self.hf_auto_launch.setEnabled(True)

    # ── Load / Save ────────────────────────────────────────────────

    def _load_values(self):
        c = self.config
        self.callsign_input.setText(c.get("my_callsign", ""))
        self.ssid_spin.setValue(c.get("my_ssid", 0))

        mode = c.get("vara_mode", "VARA FM")
        if mode == "VARA HF":
            self.hf_radio.setChecked(True)
        elif mode == "AGWPE":
            self.agwpe_radio.setChecked(True)
        else:
            self.fm_radio.setChecked(True)

        bw = str(c.get("hf_bandwidth", 500))
        idx = self.hf_bw_combo.findText(bw)
        if idx >= 0:
            self.hf_bw_combo.setCurrentIndex(idx)

        fm_bw = c.get("fm_bandwidth", "NARROW")
        idx = self.fm_bw_combo.findText(fm_bw)
        if idx >= 0:
            self.fm_bw_combo.setCurrentIndex(idx)

        self.font_family_combo.setCurrentText(c.get("font_family", "Consolas"))
        self.font_size_spin.setValue(c.get("font_size", 11))
        self.max_retries_spin.setValue(c.get("max_retries", 5))
        self.session_logging_cb.setChecked(c.get("session_logging", True))
        self.show_ptt_cb.setChecked(c.get("show_ptt_events", False))

        # Modem tab
        self.fm_host.setText(c.get("vara_fm_host", "127.0.0.1"))
        self.fm_cmd_port.setValue(c.get("vara_fm_cmd_port", 8300))
        self.fm_data_port.setValue(c.get("vara_fm_data_port", 8301))
        self.fm_auto_launch.setChecked(c.get("vara_fm_auto_launch", True))
        self.fm_exe_path.setText(c.get("vara_fm_exe_path", r"C:\VARA FM\VARAFM.exe"))

        self.hf_host.setText(c.get("vara_hf_host", "127.0.0.1"))
        self.hf_cmd_port.setValue(c.get("vara_hf_cmd_port", 8300))
        self.hf_data_port.setValue(c.get("vara_hf_data_port", 8301))
        self.hf_auto_launch.setChecked(c.get("vara_hf_auto_launch", True))
        self.hf_exe_path.setText(c.get("vara_hf_exe_path", r"C:\VARA HF\VARA HF.exe"))

        ptt = c.get("hf_ptt_method", "None (VOX)")
        idx = self.hf_ptt_method.findText(ptt)
        if idx >= 0:
            self.hf_ptt_method.setCurrentIndex(idx)
        self.omnirig_rig_spin.setValue(c.get("omnirig_rig_number", 1))

        self.agwpe_host.setText(c.get("soundmodem_host", "127.0.0.1"))
        self.agwpe_port.setValue(c.get("soundmodem_port", 8000))
        self.agwpe_auto_launch.setChecked(c.get("soundmodem_auto_launch", False))
        self.agwpe_exe.setText(c.get("soundmodem_exe_path", ""))

        # Auth tab
        self.auto_hmac_cb.setChecked(c.get("auto_respond_hmac", True))
        self.plaintext_fallback_cb.setChecked(c.get("allow_plaintext_fallback", True))
        self.show_auth_cb.setChecked(c.get("show_auth_protocol", False))

        # Macros
        macros = c.get_macros()
        for i, (label_edit, cmd_edit) in enumerate(self.macro_rows):
            if i < len(macros):
                label_edit.setText(macros[i].get("label", ""))
                cmd_edit.setText(macros[i].get("command", ""))

        # Apply initial visibility / enablement
        self._update_bw_groups()
        self._update_modem_groups()

    def _save_and_close(self):
        c = self.config
        c.set("my_callsign", self.callsign_input.text().upper().strip())
        c.set("my_ssid", self.ssid_spin.value())
        if self.agwpe_radio.isChecked():
            c.set("vara_mode", "AGWPE")
        elif self.hf_radio.isChecked():
            c.set("vara_mode", "VARA HF")
        else:
            c.set("vara_mode", "VARA FM")
        c.set("hf_bandwidth", int(self.hf_bw_combo.currentText()))
        c.set("fm_bandwidth", self.fm_bw_combo.currentText())
        c.set("font_family", self.font_family_combo.currentText())
        c.set("font_size", self.font_size_spin.value())
        c.set("max_retries", self.max_retries_spin.value())
        c.set("session_logging", self.session_logging_cb.isChecked())
        c.set("show_ptt_events", self.show_ptt_cb.isChecked())

        c.set("vara_fm_host", self.fm_host.text())
        c.set("vara_fm_cmd_port", self.fm_cmd_port.value())
        c.set("vara_fm_data_port", self.fm_cmd_port.value() + 1)
        c.set("vara_fm_auto_launch", self.fm_auto_launch.isChecked())
        c.set("vara_fm_exe_path", self.fm_exe_path.text())

        c.set("vara_hf_host", self.hf_host.text())
        c.set("vara_hf_cmd_port", self.hf_cmd_port.value())
        c.set("vara_hf_data_port", self.hf_cmd_port.value() + 1)
        c.set("vara_hf_auto_launch", self.hf_auto_launch.isChecked())
        c.set("vara_hf_exe_path", self.hf_exe_path.text())

        c.set("hf_ptt_method", self.hf_ptt_method.currentText())
        c.set("omnirig_rig_number", self.omnirig_rig_spin.value())

        c.set("soundmodem_host", self.agwpe_host.text())
        c.set("soundmodem_port", self.agwpe_port.value())
        c.set("soundmodem_auto_launch", self.agwpe_auto_launch.isChecked())
        c.set("soundmodem_exe_path", self.agwpe_exe.text())

        c.set("auto_respond_hmac", self.auto_hmac_cb.isChecked())
        c.set("allow_plaintext_fallback", self.plaintext_fallback_cb.isChecked())
        c.set("show_auth_protocol", self.show_auth_cb.isChecked())

        # Macros
        macros = []
        for label_edit, cmd_edit in self.macro_rows:
            label = label_edit.text().strip()
            cmd = cmd_edit.text().strip()
            if label and cmd:
                macros.append({"label": label, "command": cmd})
        c.set_macros(macros)

        c.save()
        self.accept()
