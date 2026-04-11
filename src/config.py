"""
config.py — Configuration management for VARA Term.

Loads/saves settings from a JSON file in the user's app data directory.
"""

import json
import os
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)

APP_NAME = "VARA Term"


def _read_version() -> str:
    """Read version from version.txt at the project root.

    Tries parent of this file's directory (src/ → project root),
    then the file's own directory (for frozen builds where files
    may be flattened), then falls back to a default.
    """
    for base in (Path(__file__).parent.parent, Path(__file__).parent):
        vf = base / "version.txt"
        if vf.is_file():
            try:
                return vf.read_text(encoding="utf-8").strip()
            except Exception:
                pass
    return "0.0.0"


APP_VERSION = _read_version()

def _app_data_dir() -> Path:
    """Return the platform-appropriate app data directory."""
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:
        base = Path.home() / ".config"
    d = base / APP_NAME
    d.mkdir(parents=True, exist_ok=True)
    return d


def _logs_dir() -> Path:
    d = Path.home() / APP_NAME / "logs"
    d.mkdir(parents=True, exist_ok=True)
    return d


DEFAULT_MACROS: List[Dict[str, str]] = [
    {"label": "Help", "command": "H"},
    {"label": "List Mine", "command": "L"},
    {"label": "Read New", "command": "N"},
    {"label": "List Bull", "command": "LB"},
    {"label": "List Files", "command": "FL"},
    {"label": "Bye", "command": "B"},
]


DEFAULT_SETTINGS: Dict[str, Any] = {
    # Identity
    "my_callsign": "",
    "my_ssid": 0,

    # VARA mode
    "vara_mode": "VARA FM",  # or "VARA HF"

    # VARA FM modem
    "vara_fm_host": "127.0.0.1",
    "vara_fm_cmd_port": 8300,
    "vara_fm_data_port": 8301,
    "vara_fm_auto_launch": True,
    "vara_fm_exe_path": r"C:\VARA FM\VARAFM.exe",

    # VARA HF modem
    "vara_hf_host": "127.0.0.1",
    "vara_hf_cmd_port": 8300,
    "vara_hf_data_port": 8301,
    "vara_hf_auto_launch": True,
    "vara_hf_exe_path": r"C:\VARA HF\VARA HF.exe",

    # RF settings
    "hf_bandwidth": 500,  # 500 / 2300 / 2750
    "fm_bandwidth": "WIDE",  # NARROW / WIDE
    "max_retries": 5,

    # Soundmodem (AGWPE) — alternative transport
    "soundmodem_host": "127.0.0.1",
    "soundmodem_port": 8000,

    # PTT (HF only — FM handles PTT internally)
    "hf_ptt_method": "OmniRig",  # "None (VOX)" or "OmniRig"
    "omnirig_rig_number": 1,  # OmniRig Rig 1 or 2

    # Terminal appearance
    "font_family": "Consolas",
    "font_size": 11,
    "theme": "dark",

    # Auth
    "auto_respond_hmac": True,
    "allow_plaintext_fallback": True,
    "show_auth_protocol": False,

    # Session
    "session_logging": True,
    "show_ptt_events": False,  # hide PTT ON/OFF from terminal by default
    "target_history": [],  # recently connected callsigns (most recent first)

    # Macros
    "macros": DEFAULT_MACROS,

    # Connection profiles
    "profiles": [],

    # Command history
    "command_history_size": 100,

    # Software updates
    "check_updates_on_startup": True,
    "update_branch": "main",
}


class Config:
    """Application configuration backed by a JSON file."""

    def __init__(self):
        self._dir = _app_data_dir()
        self._path = self._dir / "settings.json"
        self._data: Dict[str, Any] = dict(DEFAULT_SETTINGS)
        self.load()

    # ── persistence ─────────────────────────────────────────────────

    def load(self):
        if self._path.exists():
            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                # Merge saved over defaults so new keys get defaults
                for k, v in saved.items():
                    self._data[k] = v
                log.info(f"Config loaded from {self._path}")
                log.debug(f"Loaded target_history: {self._data.get('target_history', [])}")
            except Exception as e:
                log.warning(f"Failed to load config: {e}")
        self._migrate()

    def save(self):
        try:
            self._dir.mkdir(parents=True, exist_ok=True)
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2)
            log.info(f"Config saved to {self._path}")
        except Exception as e:
            log.error(f"Failed to save config to {self._path}: {e}")
            import traceback
            log.error(traceback.format_exc())

    def _migrate(self):
        """Apply one-time config migrations for new defaults."""
        changed = False

        # v1.0 → v1.1: auto-launch defaults changed from False/empty to True/path
        if not self._data.get("vara_fm_exe_path"):
            self._data["vara_fm_exe_path"] = DEFAULT_SETTINGS["vara_fm_exe_path"]
            self._data["vara_fm_auto_launch"] = True
            changed = True
        if not self._data.get("vara_hf_exe_path"):
            self._data["vara_hf_exe_path"] = DEFAULT_SETTINGS["vara_hf_exe_path"]
            self._data["vara_hf_auto_launch"] = True
            changed = True

        # v1.0.1 → v1.0.2: fix macro commands to match BBS help output
        _MACRO_CMD_FIX = {"LM": "L", "RM": "N", "LF": "FL", "BYE": "B"}
        macros = self._data.get("macros", [])
        for macro in macros:
            old_cmd = macro.get("command", "")
            if old_cmd in _MACRO_CMD_FIX:
                macro["command"] = _MACRO_CMD_FIX[old_cmd]
                changed = True

        # v1.1 → v1.2: add operator identity fields to existing profiles
        for profile in self._data.get("profiles", []):
            if "my_callsign" not in profile:
                profile["my_callsign"] = ""
                profile["my_ssid"] = 0
                changed = True

        if changed:
            log.info("Config migrated with updated defaults")
            self.save()

    # ── access ──────────────────────────────────────────────────────

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def set(self, key: str, value: Any):
        self._data[key] = value

    def __getitem__(self, key: str) -> Any:
        return self._data[key]

    def __setitem__(self, key: str, value: Any):
        self._data[key] = value

    # ── helpers ─────────────────────────────────────────────────────

    @property
    def full_callsign(self) -> str:
        call = self._data.get("my_callsign", "").upper().strip()
        ssid = self._data.get("my_ssid", 0)
        if ssid and ssid != 0:
            return f"{call}-{ssid}"
        return call

    def profile_full_callsign(self, profile: dict) -> str:
        """Return the effective operator callsign for a profile.

        Falls back to the global ``full_callsign`` when the profile does
        not specify its own operator identity.
        """
        call = profile.get("my_callsign", "").upper().strip()
        if not call:
            return self.full_callsign
        ssid = profile.get("my_ssid", 0)
        if ssid and ssid != 0:
            return f"{call}-{ssid}"
        return call

    @property
    def is_hf(self) -> bool:
        return self._data.get("vara_mode", "VARA FM") == "VARA HF"

    @property
    def modem_host(self) -> str:
        if self.is_hf:
            return self._data.get("vara_hf_host", "127.0.0.1")
        return self._data.get("vara_fm_host", "127.0.0.1")

    @property
    def cmd_port(self) -> int:
        if self.is_hf:
            return int(self._data.get("vara_hf_cmd_port", 8300))
        return int(self._data.get("vara_fm_cmd_port", 8300))

    @property
    def data_port(self) -> int:
        if self.is_hf:
            return int(self._data.get("vara_hf_data_port", 8301))
        return int(self._data.get("vara_fm_data_port", 8301))

    @property
    def logs_dir(self) -> Path:
        return _logs_dir()

    @property
    def app_data_dir(self) -> Path:
        return self._dir

    # ── profiles ────────────────────────────────────────────────────

    def get_profiles(self) -> List[Dict[str, Any]]:
        return self._data.get("profiles", [])

    def add_profile(self, profile: Dict[str, Any]):
        profiles = self.get_profiles()
        profiles.append(profile)
        self._data["profiles"] = profiles

    def remove_profile(self, index: int):
        profiles = self.get_profiles()
        if 0 <= index < len(profiles):
            profiles.pop(index)
            self._data["profiles"] = profiles

    # ── macros ──────────────────────────────────────────────────────

    def get_macros(self) -> List[Dict[str, str]]:
        return self._data.get("macros", DEFAULT_MACROS)

    def set_macros(self, macros: List[Dict[str, str]]):
        self._data["macros"] = macros
