# VARA Term Changelog

All notable changes to VARA Term are documented here.
Format: [version] — YYYY-MM-DD, then a bulleted list of changes.

---

## [1.0.1] — 2026-03-06

### Fixed

- **[BLOCKING] Silent PTT drop on CAT control failure (HF)** — If FLrig, Hamlib,
  or OmniRig was not running when Connect was clicked, PTTController was never
  enabled and VARA HF PTT ON/OFF events were silently dropped, preventing the
  radio from keying. Connection now aborts immediately with a clear error message
  if the configured PTT backend cannot be reached. A secondary guard in
  `_send_rf_connect()` catches the case where CAT setup was still in-flight
  when the 4-second init timer fired.
  *(gui/main_window.py — `_setup_hf_radio_control()`, `_send_rf_connect()`)*

- **[SIGNIFICANT] `_init_cleanup` race condition in modem init (HF)** — The
  DISCONNECT cleanup at the start of `_do_init()` used a fixed 0.8 s sleep to
  suppress VARA's response. If VARA HF responded after the sleep window closed,
  the resulting DISCONNECTED event was processed normally, emitting a spurious
  `rf_disconnected` signal and printing a false "connection attempt failed"
  message before any connection had been attempted. Replaced the sleep with a
  `threading.Event` that blocks until VARA actually acknowledges (WRONG /
  DISCONNECTED / PTT) or times out after 2 s.
  *(vara/modem.py — `_do_init()`, `_handle_event()`)*

- **[SIGNIFICANT] Config migration silently overriding `hf_ptt_method`** — The
  v1.2→v1.3 migration consumed `flrig_enabled` / `hamlib_enabled` flags to
  set `hf_ptt_method`, but never deleted the flags afterwards. On every
  subsequent launch the migration re-ran and could overwrite a manually chosen
  PTT method. Flags are now deleted after being consumed so the migration runs
  exactly once per install.
  *(config.py — `_migrate()`)*

- **[MINOR] GUI thread blocked during CAT/PTT startup (HF)** — `_start_flrig_cat()`
  and `_start_hamlib_cat()` were called directly from `_on_connect()` on the
  main Qt thread. Each can block for up to 10 s during XML-RPC / socket
  negotiation, freezing the UI and delaying processing of the `modem_connected`
  signal. CAT/PTT setup now runs on a dedicated background thread
  (`RadioControlSetup`). A `_term()` helper posts terminal messages back to
  the main thread via a queued signal.
  *(gui/main_window.py — `_setup_hf_radio_control()`, `_term()`)*

- **[MINOR] Repeated "connection failed" messages during HF retries** — VARA HF
  sends DISCONNECTED for every individual retry attempt. Each event triggered
  `_on_rf_disconnected()` with `was_connected = False`, printing the "attempt
  failed" warning once per retry (up to 5 times). Added a `_retry_warned` flag
  per connect attempt so the message appears only once, replaced by a clearer
  "VARA is retrying..." status.
  *(gui/main_window.py — `_on_rf_disconnected()`)*

---

## [1.0.0] — Initial release
