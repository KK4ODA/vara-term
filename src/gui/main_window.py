"""
gui/main_window.py — Main application window for VTerm.

Ties together the terminal, connection bar, macro buttons, status bar,
VARA modem interface, and authentication interceptor.
"""

import logging
import os
import subprocess
from datetime import datetime, timezone
from typing import Optional

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QComboBox, QStatusBar,
    QMenuBar, QMenu, QFrame, QMessageBox, QApplication,
)
from PyQt6.QtGui import QAction, QFont, QColor
from PyQt6.QtCore import Qt, QTimer, pyqtSlot

from config import Config, APP_NAME, APP_VERSION
from passwords import PasswordStore
from auth import AuthInterceptor
from vara.modem import VARAModem
from vara.connection import ConnectionState, STATE_LABELS, STATE_COLORS
from vara.ptt import PTTController
from gui.theme import C, STATE_HEX, build_stylesheet, macro_btn_style, \
    macro_frame_style, macro_label_style, connection_bar_style
from gui.terminal_widget import TerminalWidget
from gui.sn_graph import SNGraph
from gui.settings_dialog import SettingsDialog
from gui.password_dialog import PasswordDialog
from gui.profile_dialog import ProfileDialog

log = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """VTerm main application window."""

    def __init__(self, config: Config, password_store: PasswordStore):
        super().__init__()
        self.config = config
        self.passwords = password_store
        self.modem = VARAModem()
        self.auth = AuthInterceptor()
        self.ptt = PTTController()
        self._modem_procs: list = []   # tracked VARA modem subprocesses
        self._connect_in_progress = False  # True while connect sequence is running
        self._cleanup_timer = QTimer(self)  # cancellable modem cleanup timer
        self._cleanup_timer.setSingleShot(True)
        self._cleanup_timer.setInterval(500)
        self._cleanup_timer.timeout.connect(self._cleanup_modem_connection)
        self._session_log_file = None
        self._session_start: Optional[datetime] = None
        self._data_buffer = ""

        self.setWindowTitle(f"{APP_NAME} — VARA BBS Terminal Client")
        self.setMinimumSize(800, 600)
        self.resize(950, 700)

        # Apply global stylesheet (arrow SVGs are embedded in theme.py)
        self.setStyleSheet(build_stylesheet())

        self._build_menus()
        self._build_toolbar()
        self._build_central()
        self._build_macros()
        self._build_status_bar()

        self._connect_signals()

        # Session duration timer
        self._duration_timer = QTimer(self)
        self._duration_timer.setInterval(1000)
        self._duration_timer.timeout.connect(self._update_duration)

        self._update_ui_state()
        self._show_welcome()

        # Auto-launch VARA modem(s) at startup
        QTimer.singleShot(500, self._launch_modem_processes)

    # ── Build UI ───────────────────────────────────────────────────

    def _build_menus(self):
        menubar = self.menuBar()

        # File
        file_menu = menubar.addMenu("&File")
        connect_action = QAction("&Connect", self)
        connect_action.setShortcut("Ctrl+Shift+C")
        connect_action.triggered.connect(self._on_connect)
        file_menu.addAction(connect_action)

        disconnect_action = QAction("&Disconnect", self)
        disconnect_action.triggered.connect(self._on_disconnect)
        file_menu.addAction(disconnect_action)

        file_menu.addSeparator()

        exit_action = QAction("E&xit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Settings
        settings_menu = menubar.addMenu("&Settings")
        terminal_action = QAction("&Terminal Setup...", self)
        terminal_action.triggered.connect(self._open_settings)
        settings_menu.addAction(terminal_action)

        modem_action = QAction("&Modem Configuration...", self)
        modem_action.triggered.connect(lambda: self._open_settings(tab=1))
        settings_menu.addAction(modem_action)

        passwords_action = QAction("&Security / Passwords...", self)
        passwords_action.triggered.connect(self._open_passwords)
        settings_menu.addAction(passwords_action)

        settings_menu.addSeparator()

        profiles_action = QAction("Connection &Profiles...", self)
        profiles_action.triggered.connect(self._open_profiles)
        settings_menu.addAction(profiles_action)

        # Help
        help_menu = menubar.addMenu("&Help")
        about_action = QAction("&About VTerm", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

        commands_action = QAction("BBS &Commands Reference", self)
        commands_action.triggered.connect(self._show_commands_ref)
        help_menu.addAction(commands_action)

    def _build_toolbar(self):
        """Build two-row connection bar replacing the old single-row QToolBar.

        Row 1: Target, Via 1, Via 2, Connect, Disconnect
        Row 2: Mode combo, status dot, (spacer), Profile combo
        """
        bar = QFrame()
        bar.setObjectName("connectionBar")
        bar.setStyleSheet(connection_bar_style())
        bar_layout = QVBoxLayout(bar)
        bar_layout.setContentsMargins(8, 6, 8, 6)
        bar_layout.setSpacing(4)

        # ── Row 1: Connection controls ────────────────────────────
        row1 = QHBoxLayout()
        row1.setSpacing(6)

        row1.addWidget(QLabel("Target:"))

        self.target_input = QComboBox()
        self.target_input.setEditable(True)
        self.target_input.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.target_input.lineEdit().setPlaceholderText("BBS Callsign (e.g. KK4ODA-5)")
        self.target_input.setMinimumWidth(160)
        self.target_input.setDuplicatesEnabled(False)
        # Load saved history
        saved_history = self.config.get("target_history", [])
        log.debug(f"Loading target history: {saved_history}")
        for call in saved_history:
            if call and isinstance(call, str):
                self.target_input.addItem(call.upper().strip())
        if count > 0:
            self.target_input.setCurrentIndex(0)
        else:
            self.target_input.setCurrentText("")
        row1.addWidget(self.target_input, stretch=1)

        row1.addWidget(QLabel("Via 1:"))
        self.via1_input = QLineEdit()
        self.via1_input.setPlaceholderText("(optional)")
        self.via1_input.setMaximumWidth(120)
        row1.addWidget(self.via1_input)

        row1.addWidget(QLabel("Via 2:"))
        self.via2_input = QLineEdit()
        self.via2_input.setPlaceholderText("(optional)")
        self.via2_input.setMaximumWidth(120)
        row1.addWidget(self.via2_input)

        self.connect_btn = QPushButton("  Connect  ")
        self.connect_btn.setObjectName("connectBtn")
        self.connect_btn.clicked.connect(self._on_connect)
        row1.addWidget(self.connect_btn)

        self.disconnect_btn = QPushButton("  Disconnect  ")
        self.disconnect_btn.setObjectName("disconnectBtn")
        self.disconnect_btn.clicked.connect(self._on_disconnect)
        row1.addWidget(self.disconnect_btn)

        bar_layout.addLayout(row1)

        # ── Row 2: Mode, status, profile ──────────────────────────
        row2 = QHBoxLayout()
        row2.setSpacing(6)

        self.mode_combo = QComboBox()
        self.mode_combo.setObjectName("modeCombo")
        self.mode_combo.addItems(["VARA FM", "VARA HF"])
        if self.config.is_hf:
            self.mode_combo.setCurrentIndex(1)
        else:
            self.mode_combo.setCurrentIndex(0)
        self.mode_combo.currentIndexChanged.connect(self._on_mode_switched)
        row2.addWidget(self.mode_combo)

        self.status_dot = QLabel("●")
        self.status_dot.setObjectName("statusDot")
        row2.addWidget(self.status_dot)

        row2.addStretch()

        row2.addWidget(QLabel("Profile:"))
        self.profile_combo = QComboBox()
        self.profile_combo.setMinimumWidth(140)
        self.profile_combo.addItem("(none)")
        self._refresh_profiles()
        self.profile_combo.currentIndexChanged.connect(self._on_profile_selected)
        row2.addWidget(self.profile_combo)

        bar_layout.addLayout(row2)

        self._connection_bar = bar

    def _build_central(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(6, 0, 6, 2)
        layout.setSpacing(4)

        # Connection bar at top (flush against menu bar)
        layout.addWidget(self._connection_bar)

        # Terminal (display + input)
        self.terminal = TerminalWidget()
        self.terminal.command_entered.connect(self._on_command)
        layout.addWidget(self.terminal, stretch=1)

        # S/N graph is added AFTER macros (in _build_macros)
        self.sn_graph = SNGraph()

    _MACRO_BTN_STYLE = macro_btn_style()

    def _build_macros(self):
        """Build macro button bar below the terminal input."""
        # We add the macro bar to the central widget layout
        central_layout = self.centralWidget().layout()

        self.macro_frame = QFrame()
        self.macro_frame.setStyleSheet(macro_frame_style())
        macro_layout = QHBoxLayout(self.macro_frame)
        macro_layout.setContentsMargins(8, 4, 8, 4)
        macro_layout.setSpacing(6)

        # Label
        lbl = QLabel("Quick:")
        lbl.setStyleSheet(macro_label_style())
        macro_layout.addWidget(lbl)

        self.macro_buttons = []
        for macro in self.config.get_macros():
            btn = QPushButton(macro.get("label", ""))
            btn.setStyleSheet(self._MACRO_BTN_STYLE)
            cmd = macro.get("command", "")
            btn.clicked.connect(lambda checked, c=cmd: self._send_macro(c))
            macro_layout.addWidget(btn)
            self.macro_buttons.append(btn)

        macro_layout.addStretch()
        central_layout.addWidget(self.macro_frame)

        # S/N graph goes below macros
        central_layout.addWidget(self.sn_graph)

    def _build_status_bar(self):
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        self.state_label = QLabel("DISCONNECTED")
        self.state_label.setStyleSheet(f"color: {C['error']}; font-weight: bold;")
        self.status_bar.addWidget(self.state_label)

        self.status_bar.addWidget(self._sep())

        self.sn_label = QLabel("S/N: —")
        self.status_bar.addWidget(self.sn_label)

        self.status_bar.addWidget(self._sep())

        self.bw_label = QLabel("BW: —")
        self.status_bar.addWidget(self.bw_label)

        self.status_bar.addWidget(self._sep())

        self.duration_label = QLabel("Duration: 00:00:00")
        self.status_bar.addWidget(self.duration_label)

        self.status_bar.addWidget(self._sep())

        self.modem_status_label = QLabel("Modem: Not connected")
        self.status_bar.addPermanentWidget(self.modem_status_label)

        self.ptt_label = QLabel("")
        self.ptt_label.setStyleSheet("font-weight: bold;")
        self.status_bar.addPermanentWidget(self.ptt_label)

    @staticmethod
    def _sep() -> QLabel:
        sep = QLabel("│")
        sep.setStyleSheet(f"color: {C['border_light']}; padding: 0 4px;")
        return sep

    # ── Signal connections ─────────────────────────────────────────

    def _connect_signals(self):
        self.modem.state_changed.connect(self._on_state_changed, Qt.ConnectionType.QueuedConnection)
        self.modem.data_received.connect(self._on_data_received, Qt.ConnectionType.QueuedConnection)
        self.modem.command_event.connect(self._on_command_event, Qt.ConnectionType.QueuedConnection)
        self.modem.sn_report.connect(self._on_sn_report, Qt.ConnectionType.QueuedConnection)
        self.modem.error_signal.connect(self._on_error, Qt.ConnectionType.QueuedConnection)
        self.modem.modem_connected.connect(self._on_modem_connected, Qt.ConnectionType.QueuedConnection)
        self.modem.rf_connected.connect(self._on_rf_connected, Qt.ConnectionType.QueuedConnection)
        self.modem.rf_disconnected.connect(self._on_rf_disconnected, Qt.ConnectionType.QueuedConnection)
        self.modem.pending_signal.connect(
            lambda: self.terminal.display.append_system("Connection pending..."),
            Qt.ConnectionType.QueuedConnection)
        self.modem.busy_signal.connect(
            lambda: self.terminal.display.append_warning("Remote station is busy"),
            Qt.ConnectionType.QueuedConnection)
        # HF PTT: modem emits ptt_event → PTT controller keys/unkeys radio
        self.modem.ptt_event.connect(self.ptt.on_ptt_event,
                                      Qt.ConnectionType.QueuedConnection)
        self.ptt.ptt_changed.connect(self._on_ptt_changed,
                                      Qt.ConnectionType.QueuedConnection)
        self.ptt.ptt_error.connect(
            lambda msg: self.terminal.display.append_warning(f"[PTT] {msg}"),
            Qt.ConnectionType.QueuedConnection)

    # ── Actions ────────────────────────────────────────────────────

    def _on_connect(self):
        """Initiate a connection to the target BBS."""
        callsign = self.config.full_callsign
        if not callsign:
            QMessageBox.warning(self, "Configuration Error",
                                "Please set your callsign in Settings → Terminal Setup.")
            self._open_settings()
            return

        target = self.target_input.currentText().upper().strip()
        if not target:
            QMessageBox.warning(self, "Missing Target",
                                "Please enter the target BBS callsign.")
            self.target_input.setFocus()
            return

        self.terminal.display.append_system(
            f"Connecting to {target} as {callsign} via "
            f"{'VARA HF' if self.config.is_hf else 'VARA FM'}...")

        host = self.config.modem_host
        cmd_port = self.config.cmd_port
        data_port = self.config.data_port

        self.terminal.display.append_system(
            f"VARA modem: {host}:{cmd_port}/{data_port}")

        # Store target for later use
        self._target = target
        self._via1 = self.via1_input.text().upper().strip()
        self._via2 = self.via2_input.text().upper().strip()
        self._connect_in_progress = True
        self._cleanup_timer.stop()  # cancel any stale cleanup timer

        # Save target to recent stations history immediately
        self._add_to_target_history(target)

        # Connect TCP to modem
        self.modem.connect_to_modem(host, cmd_port, data_port)

        # Start OmniRig PTT for HF mode (if configured)
        if self.config.is_hf and self.config.get("hf_ptt_method") == "OmniRig":
            rig_num = self.config.get("omnirig_rig_number", 1)
            self.terminal.display.append_system(
                f"Starting OmniRig PTT (Rig {rig_num})...")
            if self.ptt.start(rig_number=rig_num):
                self.terminal.display.append_success("OmniRig PTT connected")
            else:
                self.terminal.display.append_warning(
                    "OmniRig PTT not available — radio must be in VOX mode")

    @pyqtSlot()
    def _on_modem_connected(self):
        """TCP link to modem is up — now initialize it."""
        self.terminal.display.append_system("TCP connection to modem established")
        self.modem_status_label.setText("Modem: Connected")
        self.modem_status_label.setStyleSheet(f"color: {C['success']};")

        callsign = self.config.full_callsign
        is_hf = self.config.is_hf
        bw = self.config.get("hf_bandwidth", 500)
        self.modem.initialize_modem(callsign, is_hf, bw)

        # After a delay, send the RF CONNECT command
        # (allow time for cleanup DISCONNECT + MYCALL + COMPRESSION + BW + LISTEN)
        QTimer.singleShot(4000, self._send_rf_connect)

    def _send_rf_connect(self):
        """Send the CONNECT command to initiate the RF link."""
        if self.modem.state not in (ConnectionState.MODEM_CONNECTED,
                                     ConnectionState.INITIALIZING):
            return
        target = getattr(self, '_target', '')
        via1 = getattr(self, '_via1', '')
        via2 = getattr(self, '_via2', '')
        callsign = self.config.full_callsign

        self.terminal.display.append_system(f"Initiating RF connection to {target}...")
        self.modem.rf_connect(callsign, target, via1, via2)

    @pyqtSlot(str)
    def _on_rf_connected(self, calls_str: str):
        """RF session is now active.  Resolve which call is the remote."""
        parts = calls_str.split()
        my_call = self.config.full_callsign.upper()

        # Figure out which is the remote call
        if len(parts) == 2:
            if parts[0].upper() == my_call:
                remote = parts[1]
            elif parts[1].upper() == my_call:
                remote = parts[0]
            else:
                # Neither matches exactly — use the target we requested
                remote = getattr(self, '_target', parts[0])
        elif len(parts) == 1:
            remote = parts[0]
        else:
            remote = getattr(self, '_target', 'UNKNOWN')

        self.terminal.display.append_success(f"*** CONNECTED to {remote} ***")
        self.terminal.set_input_enabled(True)
        self.terminal.input.setFocus()

        # Also save the resolved remote callsign (may differ from
        # what the user typed if routed via digipeaters)
        self._add_to_target_history(remote)

        # Reset auth state
        self.auth.reset()
        self._data_buffer = ""

        # Start session timer
        self._session_start = datetime.now(timezone.utc)
        self._duration_timer.start()

        # Start session log
        if self.config.get("session_logging"):
            self._start_session_log(remote)

    @pyqtSlot()
    def _on_rf_disconnected(self):
        """RF session has ended."""
        self.terminal.display.append_warning("*** DISCONNECTED ***")
        self.terminal.set_input_enabled(False)
        self._duration_timer.stop()
        self._close_session_log()
        self.auth.reset()
        self.sn_graph.clear_data()
        # Release PTT (HF safety)
        if self.ptt.is_enabled:
            self.ptt.stop()
            self.ptt_label.setText("")
        # Modem TCP cleanup is handled by _on_state_changed when
        # state transitions to MODEM_CONNECTED with no connect in progress.

    def _cleanup_modem_connection(self):
        """Close TCP sockets to modem after RF session ends."""
        # Safety: don't kill an active connect sequence
        if self._connect_in_progress:
            log.debug("Cleanup skipped — connect in progress")
            return
        if self.modem.state != ConnectionState.DISCONNECTED:
            log.info("Cleaning up modem TCP connection")
            self.modem.disconnect_from_modem()

    def _on_disconnect(self):
        """User requested disconnect."""
        self._connect_in_progress = False
        self._cleanup_timer.stop()

        # Release PTT first
        if self.ptt.is_enabled:
            self.ptt.stop()
            self.ptt_label.setText("")

        if self.modem.state == ConnectionState.CONNECTED:
            self.terminal.display.append_system("Disconnecting...")
            self.modem.rf_disconnect()
            # _on_rf_disconnected will handle the rest asynchronously
        elif self.modem.state != ConnectionState.DISCONNECTED:
            self.modem.disconnect_from_modem()

    def _send_text(self, text: str):
        """Send a line of text over RF, echo locally, and log."""
        if self.modem.state != ConnectionState.CONNECTED:
            self.terminal.display.append_warning(
                "Not connected — command not sent.")
            return
        self.terminal.display.append_text(f"> {text}\n", "dim")
        self.modem.send_data(text + "\r\n")
        self._log_line(f"> {text}")

    def _on_command(self, text: str):
        """User typed a command in the input bar."""
        if not text.strip():
            return
        self._send_text(text)

    # ── Data handling ──────────────────────────────────────────────

    @pyqtSlot(str)
    def _on_data_received(self, text: str):
        """Process incoming data from the BBS."""
        self._data_buffer += text

        # Process complete lines
        while "\n" in self._data_buffer:
            line, self._data_buffer = self._data_buffer.split("\n", 1)
            line = line.rstrip("\r")
            self._process_line(line)

        # Handle partial data (prompt characters like "> ")
        if self._data_buffer and not self._data_buffer.endswith("\r"):
            # Check if it looks like a prompt (short, ends with space or >)
            if len(self._data_buffer) < 10 and (
                    self._data_buffer.rstrip().endswith(">") or
                    self._data_buffer.rstrip().endswith(":")):
                prompt = self._data_buffer
                self._data_buffer = ""
                # Auth interceptor might want to suppress ">" prompts during auth
                action = self.auth.process_line(
                    prompt,
                    self.passwords.get_password(getattr(self, '_target', '')),
                    self.config.get("auto_respond_hmac", True),
                    self.config.get("show_auth_protocol", False),
                )
                if not action.suppress:
                    self.terminal.display.append_text(prompt, "normal")

    def _process_line(self, line: str):
        """Process a single complete line from the BBS."""
        target = getattr(self, '_target', '')
        password = self.passwords.get_password(target)

        action = self.auth.process_line(
            line,
            password,
            self.config.get("auto_respond_hmac", True),
            self.config.get("show_auth_protocol", False),
        )

        # Send auth response if needed
        if action.send_response:
            self.modem.send_data(action.send_response)
            log.info("Sent HMAC auth response")

        # Display handling
        if action.suppress and not action.display_text:
            # Completely suppressed
            pass
        elif action.display_text:
            # Custom display text
            if action.is_success:
                self.terminal.display.append_success(action.display_text)
                self.passwords.update_last_used(target)
            elif action.is_error:
                self.terminal.display.append_error(action.display_text)
            elif action.is_warning:
                self.terminal.display.append_warning(action.display_text)
            else:
                self.terminal.display.append_system(action.display_text)
        else:
            # Normal line — display as-is
            self.terminal.display.append_line(line, "normal")

        # Log
        self._log_line(line)

    # ── State management ───────────────────────────────────────────

    @pyqtSlot(object)
    def _on_state_changed(self, state: ConnectionState):
        label = STATE_LABELS.get(state, "UNKNOWN")
        color = STATE_COLORS.get(state, "red")

        hex_color = STATE_HEX.get(color, C["text"])
        self.state_label.setText(label)
        self.state_label.setStyleSheet(
            f"color: {hex_color}; font-weight: bold;")
        self.status_dot.setStyleSheet(
            f"color: {hex_color}; font-size: 14pt;")

        # Clear the connect flag only at terminal states — the full
        # connect sequence is: MODEM_CONNECTED → INITIALIZING →
        # MODEM_CONNECTED → CONNECTING → CONNECTED.  The flag must
        # stay True until we reach CONNECTED (success) or
        # DISCONNECTED (total failure).
        if state in (ConnectionState.CONNECTED,
                     ConnectionState.DISCONNECTED):
            self._connect_in_progress = False

        # If we've fallen back to MODEM_CONNECTED and we're NOT in a
        # connect sequence, it means the RF session ended (DISCONNECTED
        # from BBS, CANCELPENDING, etc). Close the modem TCP sockets
        # so the state returns to DISCONNECTED and buttons re-enable.
        if (state == ConnectionState.MODEM_CONNECTED
                and not self._connect_in_progress):
            self._cleanup_timer.start()  # 500ms, cancellable

        self._update_ui_state()

    def _update_ui_state(self):
        """Enable/disable buttons based on connection state."""
        state = self.modem.state
        connected = state == ConnectionState.CONNECTED
        disconnected = state == ConnectionState.DISCONNECTED
        in_progress = state in (ConnectionState.CONNECTING,
                                ConnectionState.INITIALIZING,
                                ConnectionState.MODEM_CONNECTED)

        self.connect_btn.setEnabled(disconnected)
        self.disconnect_btn.setEnabled(not disconnected)
        self.target_input.setEnabled(disconnected)
        self.via1_input.setEnabled(disconnected)
        self.via2_input.setEnabled(disconnected)
        self.terminal.set_input_enabled(connected)

        # Lock mode switching while any connection activity is happening
        self.mode_combo.setEnabled(disconnected)

        # Sync combo selection with config (e.g. after Settings dialog)
        expected_idx = 1 if self.config.is_hf else 0
        if self.mode_combo.currentIndex() != expected_idx:
            self.mode_combo.blockSignals(True)
            try:
                self.mode_combo.setCurrentIndex(expected_idx)
            finally:
                self.mode_combo.blockSignals(False)

        # Update bandwidth label
        if self.config.is_hf:
            self.bw_label.setText(f"BW: {self.config.get('hf_bandwidth', 500)} Hz")
        else:
            self.bw_label.setText(f"BW: {self.config.get('fm_bandwidth', 'NARROW')}")

    @pyqtSlot(str)
    def _on_command_event(self, event: str):
        """Show relevant VARA events in terminal."""
        upper = event.upper()
        if upper.startswith("CONNECTED") or upper.startswith("DISCONNECTED"):
            pass  # handled by specific signals
        elif upper == "PENDING":
            pass
        elif upper == "BUSY":
            pass
        elif upper == "WRONG":
            cmd_hint = ""
            if self.modem._last_cmd:
                cmd_hint = f" (cmd: {self.modem._last_cmd})"
            self.terminal.display.append_warning(
                f"[MODEM] Command rejected: WRONG{cmd_hint}")
        elif upper == "CANCELPENDING":
            self.terminal.display.append_warning("[MODEM] Connection attempt cancelled")
        elif upper.startswith("PTT"):
            # PTT events are noisy during normal operation — only show
            # if the user has opted in via settings
            if self.config.get("show_ptt_events", False):
                self.terminal.display.append_text(
                    f"[MODEM] {event}\n", "dim")

    @pyqtSlot(str)
    def _on_sn_report(self, value: str):
        try:
            sn = float(value)
            self.sn_label.setText(f"S/N: {sn:.0f} dB")
            self.sn_graph.add_value(sn)
        except ValueError:
            self.sn_label.setText(f"S/N: {value}")

    @pyqtSlot(str)
    def _on_error(self, msg: str):
        self.terminal.display.append_error(f"[ERROR] {msg}")
        # If this looks like a modem TCP connection failure, hint about mode
        if "Cannot connect to VARA modem" in msg:
            mode = self.config.get("vara_mode", "VARA FM")
            self.terminal.display.append_warning(
                f"  Tip: VTerm is set to {mode}. Make sure the {mode}\n"
                f"  modem is running. Switch modes in the toolbar if needed.")
        self.modem_status_label.setText("Modem: Error")
        self.modem_status_label.setStyleSheet(f"color: {C['error']};")
        self._connect_in_progress = False

    @pyqtSlot(bool)
    def _on_ptt_changed(self, ptt_on: bool):
        """Update the PTT indicator in the status bar."""
        if ptt_on:
            self.ptt_label.setText("● TX")
            self.ptt_label.setStyleSheet(f"color: {C['error']}; font-weight: bold;")
        else:
            self.ptt_label.setText("")

    def _update_duration(self):
        if self._session_start:
            elapsed = (datetime.now(timezone.utc) - self._session_start).total_seconds()
            h = int(elapsed // 3600)
            m = int((elapsed % 3600) // 60)
            s = int(elapsed % 60)
            self.duration_label.setText(f"Duration: {h:02d}:{m:02d}:{s:02d}")

    # ── Macros ─────────────────────────────────────────────────────

    def _send_macro(self, command: str):
        self._send_text(command)

    def _refresh_macros(self):
        """Rebuild macro buttons from config."""
        for btn in self.macro_buttons:
            btn.deleteLater()
        self.macro_buttons.clear()

        layout = self.macro_frame.layout()
        # Remove all except the "Quick:" label at index 0
        while layout.count() > 1:
            item = layout.takeAt(1)
            if item.widget():
                item.widget().deleteLater()

        for macro in self.config.get_macros():
            btn = QPushButton(macro.get("label", ""))
            btn.setStyleSheet(self._MACRO_BTN_STYLE)
            cmd = macro.get("command", "")
            btn.clicked.connect(lambda checked, c=cmd: self._send_macro(c))
            layout.addWidget(btn)
            self.macro_buttons.append(btn)
        layout.addStretch()

    # ── Profiles ───────────────────────────────────────────────────

    def _refresh_profiles(self):
        self.profile_combo.clear()
        self.profile_combo.addItem("(none)")
        for p in self.config.get_profiles():
            self.profile_combo.addItem(p.get("name", "Untitled"))

    def _on_profile_selected(self, index: int):
        if index <= 0:
            return
        profiles = self.config.get_profiles()
        if 0 <= index - 1 < len(profiles):
            p = profiles[index - 1]
            self.target_input.setCurrentText(p.get("target_callsign", ""))
            self.via1_input.setText(p.get("via1", ""))
            self.via2_input.setText(p.get("via2", ""))

            mode = p.get("mode", "VARA FM")
            if mode != self.config.get("vara_mode"):
                self.config.set("vara_mode", mode)
                bw = p.get("bandwidth", 500)
                self.config.set("hf_bandwidth", bw)
                self._update_ui_state()

    # ── Session logging ────────────────────────────────────────────

    def _start_session_log(self, remote: str):
        try:
            logs_dir = self.config.logs_dir
            timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
            filename = f"{timestamp}_{remote}.log"
            self._session_log_file = open(logs_dir / filename, "w", encoding="utf-8")
            self._session_log_file.write(
                f"VTerm Session Log\n"
                f"Date: {datetime.now().isoformat()}\n"
                f"Station: {self.config.full_callsign}\n"
                f"Remote: {remote}\n"
                f"Mode: {self.config.get('vara_mode')}\n"
                f"{'─' * 60}\n\n"
            )
            log.info(f"Session log started: {filename}")
        except Exception as e:
            log.error(f"Failed to start session log: {e}")

    def _log_line(self, text: str):
        if self._session_log_file:
            try:
                ts = datetime.now().strftime("%H:%M:%S")
                self._session_log_file.write(f"[{ts}] {text}\n")
                self._session_log_file.flush()
            except Exception:
                pass

    def _close_session_log(self):
        if self._session_log_file:
            try:
                self._session_log_file.write(
                    f"\n{'─' * 60}\n"
                    f"Session ended: {datetime.now().isoformat()}\n"
                )
            except Exception:
                pass
            finally:
                try:
                    self._session_log_file.close()
                except Exception:
                    pass
                self._session_log_file = None

    # ── Target history ────────────────────────────────────────────

    def _add_to_target_history(self, callsign: str):
        """Add a callsign to the target dropdown history."""
        try:
            callsign = callsign.upper().strip()
            if not callsign:
                return

            # Get current history (copy to avoid mutating config directly)
            history = list(self.config.get("target_history", []))

            # Move to front if already present, otherwise prepend
            if callsign in history:
                history.remove(callsign)
            history.insert(0, callsign)

            # Cap at 20 entries
            history = history[:20]

            self.config.set("target_history", history)
            self.config.save()
            log.info(f"Target history saved: {history}")
            log.info(f"Config path: {self.config._path}")

            # Refresh the combo box
            self.target_input.blockSignals(True)
            current = self.target_input.currentText()
            self.target_input.clear()
            for call in history:
                self.target_input.addItem(call)
            self.target_input.setCurrentText(current)
            self.target_input.blockSignals(False)

            count = self.target_input.count()
            log.info(f"ComboBox now has {count} items")
        except Exception as e:
            log.error(f"Failed to save target history: {e}")
            import traceback
            log.error(traceback.format_exc())

    # ── Modem process management ──────────────────────────────────

    # Common VARA install locations (tried in order)
    _VARA_FM_PATHS = [
        r"C:\VARA FM\VARAFM.exe",
        r"C:\VARA FM\VARA FM.exe",
        r"C:\Program Files\VARA FM\VARAFM.exe",
        r"C:\Program Files (x86)\VARA FM\VARAFM.exe",
    ]
    _VARA_HF_PATHS = [
        r"C:\VARA HF\VARA HF.exe",
        r"C:\VARA\VARA.exe",
        r"C:\Program Files\VARA\VARA.exe",
        r"C:\Program Files (x86)\VARA\VARA.exe",
    ]

    def _find_vara_exe(self, configured_path: str, search_paths: list) -> str:
        """Return a valid exe path: configured path if it exists,
        otherwise try common install locations."""
        if configured_path and os.path.isfile(configured_path):
            return configured_path
        for path in search_paths:
            if os.path.isfile(path):
                log.info(f"Auto-detected VARA at: {path}")
                return path
        return configured_path  # return whatever was configured (for error msg)

    def _on_mode_switched(self, index: int):
        """User changed VARA mode via the toolbar combo."""
        new_mode = "VARA HF" if index == 1 else "VARA FM"
        old_mode = self.config.get("vara_mode", "VARA FM")
        if new_mode == old_mode:
            return

        self.config.set("vara_mode", new_mode)
        self.config.save()

        # Terminate the old modem process(es) and launch the new one
        self._terminate_modem_processes()
        self.terminal.display.append_system(f"Switched to {new_mode}")
        QTimer.singleShot(300, self._launch_modem_processes)

        self._update_ui_state()

    def _launch_modem_processes(self):
        """Launch the VARA modem executable matching the selected mode."""
        is_hf = self.config.is_hf
        mode_label = "VARA HF" if is_hf else "VARA FM"

        if is_hf:
            should_launch = self.config.get("vara_hf_auto_launch", True)
            configured_path = self.config.get("vara_hf_exe_path", "")
            search_paths = self._VARA_HF_PATHS
            path_key = "vara_hf_exe_path"
        else:
            should_launch = self.config.get("vara_fm_auto_launch", True)
            configured_path = self.config.get("vara_fm_exe_path", "")
            search_paths = self._VARA_FM_PATHS
            path_key = "vara_fm_exe_path"

        if not should_launch:
            return

        exe = self._find_vara_exe(configured_path, search_paths)
        proc = self._start_modem_exe(exe, mode_label)
        if proc:
            self.terminal.display.append_system(
                f"Launched {mode_label} modem")
            # Save the working path back to config
            if exe != configured_path:
                self.config.set(path_key, exe)
        else:
            self.terminal.display.append_warning(
                f"{mode_label} modem not found.\n"
                "  Set the executable path in Settings > Modem Configuration.")

    def _start_modem_exe(self, exe_path: str, label: str) -> Optional[subprocess.Popen]:
        """Start a modem executable and track the process."""
        if not exe_path:
            return None
        if not os.path.exists(exe_path):
            self.terminal.display.append_warning(
                f"{label} executable not found: {exe_path}")
            return None
        try:
            proc = subprocess.Popen([exe_path], shell=False)
            self._modem_procs.append(proc)
            log.info(f"Launched {label}: {exe_path} (PID {proc.pid})")
            return proc
        except Exception as e:
            self.terminal.display.append_error(
                f"Failed to launch {label}: {e}")
            return None

    def _terminate_modem_processes(self):
        """Terminate all VARA modem processes we launched."""
        for proc in self._modem_procs:
            if proc.poll() is None:  # still running
                try:
                    log.info(f"Terminating modem process PID {proc.pid}")
                    proc.terminate()
                    try:
                        proc.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        log.warning(
                            f"Modem PID {proc.pid} did not exit, killing")
                        proc.kill()
                except Exception as e:
                    log.error(f"Error terminating modem PID {proc.pid}: {e}")
        self._modem_procs.clear()

    # ── Dialogs ────────────────────────────────────────────────────

    def _open_settings(self, tab: int = 0):
        old_mode = self.config.get("vara_mode", "VARA FM")
        dlg = SettingsDialog(self.config, self)
        if hasattr(dlg, 'tabs'):
            dlg.tabs.setCurrentIndex(tab)
        if dlg.exec():
            # Apply font changes
            self.terminal.set_font_size(self.config.get("font_size", 11))
            self.terminal.display.set_font_family(
                self.config.get("font_family", "Consolas"))
            self._refresh_macros()

            # If mode changed in settings, relaunch the modem
            new_mode = self.config.get("vara_mode", "VARA FM")
            if new_mode != old_mode:
                self._terminate_modem_processes()
                self.terminal.display.append_system(f"Switched to {new_mode}")
                QTimer.singleShot(300, self._launch_modem_processes)

            self._update_ui_state()

    def _open_passwords(self):
        dlg = PasswordDialog(self.passwords, self)
        dlg.exec()

    def _open_profiles(self):
        dlg = ProfileDialog(self.config, self)
        dlg.profile_connect.connect(self._connect_from_profile)
        dlg.exec()
        self._refresh_profiles()

    def _connect_from_profile(self, profile: dict):
        self.target_input.setCurrentText(profile.get("target_callsign", ""))
        self.via1_input.setText(profile.get("via1", ""))
        self.via2_input.setText(profile.get("via2", ""))
        mode = profile.get("mode", "VARA FM")
        self.config.set("vara_mode", mode)
        if mode == "VARA HF":
            self.config.set("hf_bandwidth", profile.get("bandwidth", 500))
        self._update_ui_state()
        QTimer.singleShot(200, self._on_connect)

    def _show_about(self):
        QMessageBox.about(self, f"About {APP_NAME}",
            f"<h2>{APP_NAME} v{APP_VERSION}</h2>"
            f"<p>VARA BBS Terminal Client</p>"
            f"<p>A modern terminal for connecting to amateur radio BBS systems "
            f"over VARA FM and VARA HF modems.</p>"
            f"<p><b>Features:</b><br>"
            f"• HMAC-SHA256 challenge-response authentication<br>"
            f"• Password never transmitted over RF<br>"
            f"• VARA FM and HF support with digipeater routing<br>"
            f"• Connection profiles and macro buttons</p>"
            f"<p>Built with Python and PyQt6.</p>"
        )

    def _show_commands_ref(self):
        QMessageBox.information(self, "BBS Commands Reference",
            "<h3>Common BBS Commands</h3>"
            "<table>"
            "<tr><td><b>H</b></td><td>Help / command list</td></tr>"
            "<tr><td><b>LM</b></td><td>List my messages</td></tr>"
            "<tr><td><b>RM</b></td><td>Read new messages</td></tr>"
            "<tr><td><b>R #</b></td><td>Read message by number</td></tr>"
            "<tr><td><b>SP call</b></td><td>Send private message</td></tr>"
            "<tr><td><b>SB topic</b></td><td>Send bulletin</td></tr>"
            "<tr><td><b>LB</b></td><td>List bulletins</td></tr>"
            "<tr><td><b>LF</b></td><td>List files</td></tr>"
            "<tr><td><b>DF file</b></td><td>Download file</td></tr>"
            "<tr><td><b>I</b></td><td>Station info</td></tr>"
            "<tr><td><b>BYE</b></td><td>Disconnect</td></tr>"
            "</table>"
        )

    # ── Welcome ────────────────────────────────────────────────────

    def _show_welcome(self):
        self.terminal.display.append_text(
            "\n"
            "  VTerm  --  VARA BBS Terminal Client\n"
            f"  Version {APP_VERSION}\n"
            "  -----------------------------------\n"
            "\n",
            "cyan"
        )
        self.terminal.display.append_text(
            "  Configure your callsign in Settings > Terminal Setup\n"
            "  Enter the target BBS callsign above and click Connect\n"
            "\n"
            "  HMAC-SHA256 authentication is automatic when\n"
            "  a password is saved for the target station.\n"
            "\n",
            "normal"
        )

        if not self.config.get("my_callsign"):
            self.terminal.display.append_warning(
                "  No callsign configured. Go to Settings > Terminal Setup.\n")

        # Show loaded target history for diagnostics
        history = self.config.get("target_history", [])
        if history:
            self.terminal.display.append_text(
                f"  Recent stations: {', '.join(history)}\n\n", "dim")

    # ── Cleanup ────────────────────────────────────────────────────

    def closeEvent(self, event):
        """Clean up on window close."""
        self._cleanup_timer.stop()
        if self.ptt.is_enabled:
            self.ptt.stop()
        if self.modem.state != ConnectionState.DISCONNECTED:
            self.modem.disconnect_from_modem()
        self._close_session_log()
        self._terminate_modem_processes()
        self.config.save()
        event.accept()
