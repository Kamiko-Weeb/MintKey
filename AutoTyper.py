#!/usr/bin/env python3
"""Auto Typer V13 - PyQt6 GUI with AI Chat Mode"""

from __future__ import annotations

import sys
import os
import time
import random
import pathlib
import requests

try:
    from dotenv import load_dotenv
    import sys as _sys
    # PyInstaller apps run from a temp dir so we need to check multiple locations
    _home = os.path.expanduser('~')
    _env_locations = [
        os.path.join(_home, 'Desktop', '.env'),
        os.path.join(_home, '.env'),
        os.path.join(os.getcwd(), '.env'),
    ]
    # Also check the directory the .app or .exe lives in
    if getattr(_sys, 'frozen', False):
        _app_dir = os.path.dirname(_sys.executable)
        _env_locations.insert(0, os.path.join(_app_dir, '.env'))
        _env_locations.insert(0, os.path.join(os.path.dirname(_app_dir), '.env'))
    for _env_path in _env_locations:
        if os.path.exists(_env_path):
            load_dotenv(_env_path)
            break
except ImportError:
    pass

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QTextEdit, QLineEdit, QLabel, QSlider, QCheckBox, QSpinBox,
    QDoubleSpinBox, QStackedWidget, QFrame, QScrollArea, QSizePolicy,
    QMessageBox, QComboBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, pyqtSlot
from PyQt6.QtGui import QFont, QColor, QPalette, QTextCursor

# --- Constants ---
import platform
import webbrowser
from config import APIConfig, AppConfig, TypingConfig, UIConfig
IS_MAC = platform.system() == "Darwin"
IS_WINDOWS = platform.system() == "Windows"

# Version is read from version.txt sitting next to AutoTyper.py.
# To release a new version just update that one file - nothing in the
# code needs to change.
def _read_local_version() -> int:
    try:
        import sys as _sys
        # PyInstaller extracts bundled data files to sys._MEIPASS at runtime
        if getattr(_sys, 'frozen', False):
            _here = pathlib.Path(_sys._MEIPASS)
        else:
            _here = pathlib.Path(__file__).parent if '__file__' in dir() else pathlib.Path.home() / "Desktop"
        return int((_here / "version.txt").read_text().strip())
    except Exception:
        return 0

CURRENT_VERSION = _read_local_version()

# Ensure the Desktop directory is in the module search path so that
# both the services and utils packages can always be found regardless
# of how the script is launched (terminal, PyInstaller, double-click, etc.)
import sys as _sys_path_fix
import pathlib as _pathlib
_desktop = str(_pathlib.Path.home() / "Desktop")
if _desktop not in _sys_path_fix.path:
    _sys_path_fix.path.insert(0, _desktop)

# Logger must be imported early, before other services
from utils.logger import get_logger  # noqa: E402
log = get_logger(__name__)

# AI logic lives in services/ai_service.py.
from services.ai_service import NIM_MODELS, NIM_MODEL, AIWorker  # noqa: E402

# Typing engine lives in services/typing_engine.py.
from services.typing_engine import TypingEngine  # noqa: E402


# --- Update Checker ---
# This runs in a background thread on launch so it never slows down the UI.
# It fetches version.txt from GitHub, compares to CURRENT_VERSION,
# and emits update_available if a newer version exists.
class UpdateChecker(QThread):
    update_available = pyqtSignal(int)  # emits the new version number

    def run(self):
        try:
            response = requests.get(
                AppConfig.VERSION_CHECK_URL, timeout=AppConfig.VERSION_CHECK_TIMEOUT
            )
            response.raise_for_status()
            latest = int(response.text.strip())
            log.debug("Version check: local=%d, remote=%d", CURRENT_VERSION, latest)
            if latest > CURRENT_VERSION:
                log.info("Update available: v%d -> v%d", CURRENT_VERSION, latest)
                self.update_available.emit(latest)
        except Exception as e:
            # Silently ignore all errors - no internet, bad response, etc.
            log.debug("Version check failed: %s", e)


# Theme definitions and stylesheet builder live in utils/theme.py.
from utils.theme import THEMES, build_style, DEFAULT_THEME

# Persistent settings (theme choice, defaults) live in utils/settings.py.
from utils.settings import load as settings_load, set as settings_set

# Active theme color tokens - used in inline styles throughout the file
_t = THEMES[DEFAULT_THEME]
DARK_BG =      _t["DARK_BG"]
PANEL_BG =     _t["PANEL_BG"]
ACCENT =       _t["ACCENT"]
ACCENT_DIM =   _t["ACCENT_DIM"]
TEXT_PRIMARY = _t["TEXT_PRIMARY"]
TEXT_DIM =     _t["TEXT_DIM"]
DANGER =       _t["DANGER"]
BORDER =       _t["BORDER"]
INPUT_BG =     _t["INPUT_BG"]

# --- Typing worker (PyQt bridge to TypingEngine) ---
# TypingEngine in services/typing_engine.py holds all typing logic.
# TypingWorker is a thin QThread wrapper whose only job is:
#   1. Give the engine a thread to run in (QThread.run → engine.start_typing)
#   2. Route engine callbacks to PyQt signals so the UI can connect to them
#
# One TypingWorker instance is created per typing session (same lifecycle as before).
class TypingWorker(QThread):
    status_update = pyqtSignal(str)
    countdown     = pyqtSignal(int)
    finished      = pyqtSignal()

    def __init__(
        self,
        text: str,
        wpm: float,
        mistake_rate: float,
        max_speed: bool,
        delay: int,
    ) -> None:
        super().__init__()
        self._text         = text
        self._wpm          = wpm
        self._mistake_rate = mistake_rate
        self._max_speed    = max_speed
        self._delay        = delay

        # Engine callbacks are wired directly to signal emission.
        # Signals are emitted from the QThread, which is the correct
        # way to do cross-thread communication in PyQt.
        self._engine = TypingEngine(
            on_status    = self.status_update.emit,
            on_countdown = self.countdown.emit,
            on_finished  = self.finished.emit,
        )

    def run(self) -> None:
        """QThread entry point — calls engine synchronously."""
        self._engine.start_typing(
            text         = self._text,
            wpm          = self._wpm,
            mistake_rate = self._mistake_rate,
            max_speed    = self._max_speed,
            delay        = self._delay,
        )

    def stop(self) -> None:
        """Request the engine to stop. Safe to call from the main thread."""
        self._engine.stop_typing()

    @property
    def lost_focus(self) -> bool:
        return self._engine.lost_focus

    @lost_focus.setter
    def lost_focus(self, value: bool) -> None:
        """Write True to pause mid-type; False to resume."""
        self._engine.lost_focus = value


# --- Auto Typer Panel ---
class AutoTyperPanel(QWidget):
    def __init__(self, debug_window=None):
        super().__init__()
        self.typing_worker = None   # set per session in start_typing()
        self.debug_window = debug_window
        self._build_ui()

    def apply_defaults(self, wpm: float, delay: int, mistake_rate: float) -> None:
        """Called by SettingsWindow when the user changes default values."""
        self.wpm_input.setValue(wpm)
        self.delay_input.setValue(delay)
        self.mistake_input.setValue(mistake_rate)

    def _log(self, msg: str):
        if self.debug_window and self.debug_window.isVisible():
            self.debug_window.log("AutoTyper", msg)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(20, 20, 20, 20)

        # Text input
        text_label = QLabel("Text to Type")
        text_label.setObjectName("heading")
        layout.addWidget(text_label)

        self.text_input = QTextEdit()
        self.text_input.setPlaceholderText("Paste your text here...")
        self.text_input.setMinimumHeight(UIConfig.TEXT_INPUT_MIN_HEIGHT)
        layout.addWidget(self.text_input)

        # Settings row
        settings_frame = QFrame()
        settings_layout = QHBoxLayout(settings_frame)
        settings_layout.setSpacing(20)
        settings_layout.setContentsMargins(0, 0, 0, 0)

        # WPM
        wpm_col = QVBoxLayout()
        wpm_col.addWidget(QLabel("Speed (WPM)"))
        self.wpm_input = QDoubleSpinBox()
        self.wpm_input.setRange(TypingConfig.WPM_MIN, TypingConfig.WPM_MAX)
        self.wpm_input.setValue(TypingConfig.DEFAULT_WPM)
        self.wpm_input.setDecimals(0)
        wpm_col.addWidget(self.wpm_input)
        settings_layout.addLayout(wpm_col)

        # Mistake rate
        mistake_col = QVBoxLayout()
        mistake_col.addWidget(QLabel("Mistake Rate (0-1)"))
        self.mistake_input = QDoubleSpinBox()
        self.mistake_input.setRange(TypingConfig.MISTAKE_RATE_MIN, TypingConfig.MISTAKE_RATE_MAX)
        self.mistake_input.setValue(TypingConfig.DEFAULT_MISTAKE_RATE)
        self.mistake_input.setSingleStep(TypingConfig.MISTAKE_STEP)
        self.mistake_input.setDecimals(2)
        mistake_col.addWidget(self.mistake_input)
        settings_layout.addLayout(mistake_col)

        # Delay
        delay_col = QVBoxLayout()
        delay_col.addWidget(QLabel("Start Delay (sec)"))
        self.delay_input = QSpinBox()
        self.delay_input.setRange(TypingConfig.DELAY_MIN, TypingConfig.DELAY_MAX)
        self.delay_input.setValue(TypingConfig.DEFAULT_DELAY)
        delay_col.addWidget(self.delay_input)
        settings_layout.addLayout(delay_col)

        # Checkboxes
        check_col = QVBoxLayout()
        self.max_speed_check = QCheckBox("Max Speed")
        self.dry_run_check = QCheckBox("Dry Run")
        check_col.addWidget(self.max_speed_check)
        check_col.addWidget(self.dry_run_check)
        settings_layout.addLayout(check_col)

        settings_layout.addStretch()
        layout.addWidget(settings_frame)

        # Status
        self.status_label = QLabel("Ready.")
        self.status_label.setObjectName("accent")
        layout.addWidget(self.status_label)

        # Buttons
        btn_row = QHBoxLayout()
        self.start_btn = QPushButton("Start Typing")
        self.start_btn.clicked.connect(self.start_typing)
        btn_row.addWidget(self.start_btn)

        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setObjectName("danger")
        self.stop_btn.clicked.connect(self.stop_typing)
        self.stop_btn.setEnabled(False)
        btn_row.addWidget(self.stop_btn)

        layout.addLayout(btn_row)
        layout.addStretch()

    def start_typing(self):
        text = self.text_input.toPlainText().strip()
        if not text:
            self.status_label.setText("No text entered.")
            return

        if self.dry_run_check.isChecked():
            wc = len(text.split())
            self.status_label.setText(f"Dry run: {wc} words, {len(text)} chars.")
            self._log(f"Dry run: {wc} words, {len(text)} chars.")
            return

        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)

        delay = self.delay_input.value()
        self.status_label.setText(f"Starting in {delay}s - switch to your target window!")
        self._log(f"Typing started. Delay: {delay}s, WPM: {self.wpm_input.value()}, Mistakes: {self.mistake_input.value()}, MaxSpeed: {self.max_speed_check.isChecked()}")

        self.typing_worker = TypingWorker(
            text         = text,
            wpm          = self.wpm_input.value(),
            mistake_rate = self.mistake_input.value(),
            max_speed    = self.max_speed_check.isChecked(),
            delay        = delay,
        )
        self.typing_worker.status_update.connect(self.on_status)
        self.typing_worker.countdown.connect(self.on_countdown)
        self.typing_worker.finished.connect(self.on_finished)
        self.typing_worker.start()

    def stop_typing(self):
        if self.typing_worker:
            self.typing_worker.stop()
        self.status_label.setText("Stopping...")
        self._log("Typing stopped by user.")

    @pyqtSlot(str)
    def on_status(self, msg):
        self.status_label.setText(msg)
        self._log(msg)

    @pyqtSlot(int)
    def on_countdown(self, seconds):
        self.status_label.setText(f"Starting in {seconds}s - switch to your target window!")
        self._log(f"Countdown: {seconds}s")

    @pyqtSlot()
    def on_finished(self):
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self._log("Typing finished.")


# --- Debug Terminal Window ---
class DebugWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Mintkey — Debug Terminal")
        self.setMinimumSize(UIConfig.DEBUG_MIN_WIDTH, UIConfig.DEBUG_MIN_HEIGHT)
        self.setStyleSheet("""
            QWidget {
                background-color: #1c1c1e;
                color: #f8f8f2;
                font-family: 'SF Mono', 'Menlo', 'Monaco', monospace;
                font-size: 12px;
            }
            QTextEdit {
                background-color: #1c1c1e;
                color: #f8f8f2;
                border: none;
                padding: 12px;
                font-family: 'SF Mono', 'Menlo', 'Monaco', monospace;
                font-size: 12px;
                selection-background-color: #44475a;
            }
            QPushButton {
                background-color: #3a3a3c;
                color: #f8f8f2;
                border: none;
                border-radius: 5px;
                padding: 4px 12px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #48484a;
            }
            QLabel {
                color: #8e8e93;
                font-size: 11px;
            }
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Title bar mimicking macOS terminal
        title_bar = QWidget()
        title_bar.setFixedHeight(36)
        title_bar.setStyleSheet("background-color: #2c2c2e; border-bottom: 1px solid #3a3a3c;")
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(12, 0, 12, 0)

        title_label = QLabel("mintkey — debug terminal")
        title_label.setStyleSheet("color: #8e8e93; font-size: 12px;")
        title_layout.addWidget(title_label)
        title_layout.addStretch()

        hint_label = QLabel('type "clear" to clear')
        hint_label.setStyleSheet("color: #48484a; font-size: 11px;")
        title_layout.addWidget(hint_label)

        layout.addWidget(title_bar)

        # Log display
        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        layout.addWidget(self.log_display)

        # Command input at the bottom
        cmd_row = QHBoxLayout()
        cmd_row.setContentsMargins(12, 6, 12, 6)
        prompt = QLabel("$")
        prompt.setStyleSheet("color: #50fa7b; font-family: 'SF Mono', 'Menlo', monospace; font-size: 12px;")
        cmd_row.addWidget(prompt)
        self.cmd_input = QLineEdit()
        self.cmd_input.setStyleSheet("""
            QLineEdit {
                background-color: transparent;
                color: #f8f8f2;
                border: none;
                font-family: 'SF Mono', 'Menlo', monospace;
                font-size: 12px;
            }
        """)
        self.cmd_input.setPlaceholderText('type "clear" to clear logs...')
        self.cmd_input.returnPressed.connect(self._handle_command)
        cmd_row.addWidget(self.cmd_input)
        cmd_widget = QWidget()
        cmd_widget.setStyleSheet("background-color: #2c2c2e; border-top: 1px solid #3a3a3c;")
        cmd_widget.setLayout(cmd_row)
        layout.addWidget(cmd_widget)

        # Startup message
        self.log("System", "Debug terminal ready.")

    def _handle_command(self):
        cmd = self.cmd_input.text().strip().lower()
        self.cmd_input.clear()
        if cmd == "clear":
            self.log_display.clear()
            self.log("System", "Cleared.")

    def log(self, tag: str, message: str):
        """
        Log a message with color coding based on tag.
        Tags: System, AI, AutoTyper, Error, Warning
        """
        timestamp = time.strftime("%H:%M:%S")

        # Color per tag - matches Terminal Pro palette
        colors = {
            "System":    "#8be9fd",  # cyan
            "AI":        "#50fa7b",  # green
            "AutoTyper": "#ffb86c",  # orange
            "Error":     "#ff5555",  # red
            "Warning":   "#f1fa8c",  # yellow
        }
        tag_color = colors.get(tag, "#f8f8f2")
        dim = "#6272a4"

        html = (
            f'<span style="color:{dim};">[{timestamp}]</span> '
            f'<span style="color:{tag_color}; font-weight:bold;">[{tag}]</span> '
            f'<span style="color:#f8f8f2;">{message}</span>'
        )
        self.log_display.append(html)
        self.log_display.verticalScrollBar().setValue(
            self.log_display.verticalScrollBar().maximum()
        )


# --- AI Chat Panel ---
class AIChatPanel(QWidget):
    def __init__(self, debug_window=None):
        super().__init__()
        self.api_key = os.environ.get(APIConfig.KEY_ENV, "")
        self.conversation = [{"role": "system", "content": APIConfig.SYSTEM_PROMPT}]
        self.last_response = None
        self.ai_worker = None
        self.typing_worker = None   # set per session in _start_typing()
        self.debug_window = debug_window
        self._build_ui()

    def apply_defaults(self, wpm: float, delay: int, mistake_rate: float) -> None:
        """Called by SettingsWindow when the user changes default values."""
        self.wpm_input.setValue(wpm)
        self.delay_input.setValue(delay)
        self.mistake_input.setValue(mistake_rate)

    def _log(self, msg: str):
        if self.debug_window and self.debug_window.isVisible():
            self.debug_window.log("AI", msg)

    def _update_model_desc(self, index):
        self.model_desc.setText(NIM_MODELS[index][2])

    def _open_debug(self):
        if self.debug_window:
            self.debug_window.show()
            self.debug_window.raise_()
            self.debug_window.log("System", "Debug terminal opened.")

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(20, 16, 20, 16)

        # Model selector
        model_row = QHBoxLayout()
        model_row.setSpacing(8)
        model_label = QLabel("Model")
        model_row.addWidget(model_label)
        self.model_dropdown = QComboBox()
        for label, _, _ in NIM_MODELS:
            self.model_dropdown.addItem(label)
        self.model_dropdown.setFixedHeight(34)
        self.model_dropdown.currentIndexChanged.connect(self._update_model_desc)
        model_row.addWidget(self.model_dropdown, stretch=1)
        layout.addLayout(model_row)

        self.model_desc = QLabel(NIM_MODELS[0][2])
        self.model_desc.setObjectName("modelDesc")
        self.model_desc.setWordWrap(True)
        layout.addWidget(self.model_desc)

        # Chat display - takes up most of the space
        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        self.chat_display.setPlaceholderText("Chat history will appear here...")
        layout.addWidget(self.chat_display, stretch=3)

        # Input row
        input_row = QHBoxLayout()
        input_row.setSpacing(8)
        self.chat_input = QLineEdit()
        self.chat_input.setPlaceholderText("Type a message...")
        self.chat_input.setFixedHeight(38)
        self.chat_input.returnPressed.connect(self.send_message)
        input_row.addWidget(self.chat_input)

        self.send_btn = QPushButton("Send")
        self.send_btn.setFixedWidth(90)
        self.send_btn.setFixedHeight(38)
        self.send_btn.clicked.connect(self.send_message)
        input_row.addWidget(self.send_btn)
        layout.addLayout(input_row)

        # Status bar
        self.status_label = QLabel("Ready.")
        self.status_label.setObjectName("accent")
        layout.addWidget(self.status_label)

        # Divider
        sep = QFrame()
        sep.setObjectName("separator")
        layout.addWidget(sep)

        # Typing settings - compact single row
        settings_row = QHBoxLayout()
        settings_row.setSpacing(16)

        wpm_col = QVBoxLayout()
        wpm_col.setSpacing(2)
        wpm_col.addWidget(QLabel("WPM"))
        self.wpm_input = QDoubleSpinBox()
        self.wpm_input.setRange(TypingConfig.WPM_MIN, TypingConfig.WPM_MAX)
        self.wpm_input.setValue(TypingConfig.DEFAULT_WPM)
        self.wpm_input.setDecimals(0)
        self.wpm_input.setFixedWidth(90)
        wpm_col.addWidget(self.wpm_input)
        settings_row.addLayout(wpm_col)

        mistake_col = QVBoxLayout()
        mistake_col.setSpacing(2)
        mistake_col.addWidget(QLabel("Mistakes"))
        self.mistake_input = QDoubleSpinBox()
        self.mistake_input.setRange(TypingConfig.MISTAKE_RATE_MIN, TypingConfig.MISTAKE_RATE_MAX)
        self.mistake_input.setValue(TypingConfig.DEFAULT_MISTAKE_RATE)
        self.mistake_input.setSingleStep(TypingConfig.MISTAKE_STEP)
        self.mistake_input.setDecimals(2)
        self.mistake_input.setFixedWidth(80)
        mistake_col.addWidget(self.mistake_input)
        settings_row.addLayout(mistake_col)

        delay_col = QVBoxLayout()
        delay_col.setSpacing(2)
        delay_col.addWidget(QLabel("Delay (s)"))
        self.delay_input = QSpinBox()
        self.delay_input.setRange(TypingConfig.DELAY_MIN, TypingConfig.DELAY_MAX)
        self.delay_input.setValue(TypingConfig.DEFAULT_DELAY)
        self.delay_input.setFixedWidth(70)
        delay_col.addWidget(self.delay_input)
        settings_row.addLayout(delay_col)

        self.max_speed_check = QCheckBox("Max Speed")
        settings_row.addWidget(self.max_speed_check, alignment=Qt.AlignmentFlag.AlignBottom)
        settings_row.addStretch()

        # Type + Stop buttons inline with settings
        self.type_btn = QPushButton("Type Response")
        self.type_btn.clicked.connect(self.confirm_type)
        self.type_btn.setEnabled(False)
        settings_row.addWidget(self.type_btn, alignment=Qt.AlignmentFlag.AlignBottom)

        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setObjectName("danger")
        self.stop_btn.clicked.connect(self.stop_typing)
        self.stop_btn.setEnabled(False)
        settings_row.addWidget(self.stop_btn, alignment=Qt.AlignmentFlag.AlignBottom)

        layout.addLayout(settings_row)

    def send_message(self):
        msg = self.chat_input.text().strip()
        if not msg:
            return

        if not self.api_key:
            self.status_label.setText("No API key found in .env file.")
            return

        self.chat_input.clear()
        self._append_chat("You", msg)
        self.conversation.append({"role": "user", "content": msg})
        self.send_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.status_label.setText("AI is thinking...")
        self._log(f"Sending message to AI: {msg[:80]}...")

        selected_model = NIM_MODELS[self.model_dropdown.currentIndex()][1]
        self.ai_worker = AIWorker(self.conversation.copy(), self.api_key, model=selected_model)
        self.ai_worker.response_ready.connect(self.on_ai_response)
        self.ai_worker.error.connect(self.on_ai_error)
        self.ai_worker.start()

    def _open_debug(self):
        if self.debug_window is None:
            self.debug_window = DebugWindow()
        self.debug_window.show()
        self.debug_window.raise_()
        self.debug_window.log("System", "Debug terminal opened.")

    @pyqtSlot(str)
    def on_ai_response(self, reply):
        self.conversation.append({"role": "assistant", "content": reply})
        self.last_response = reply
        self._append_chat("AI", reply)
        self.send_btn.setEnabled(True)
        self.type_btn.setEnabled(True)
        self.status_label.setText("Response ready.")
        self._log(f"AI responded ({len(reply)} chars).")

    @pyqtSlot(str)
    def on_ai_error(self, error):
        self.status_label.setText(f"Error: {error}")
        self._log(f"API error: {error}")
        self.send_btn.setEnabled(True)
        self.conversation.pop()

    def _append_chat(self, sender, message):
        cursor = self.chat_display.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.chat_display.setTextCursor(cursor)
        self.chat_display.append(f"\n{sender}:\n{message}\n")
        self.chat_display.verticalScrollBar().setValue(
            self.chat_display.verticalScrollBar().maximum()
        )

    def confirm_type(self):
        if not self.last_response:
            return
        reply = QMessageBox.question(
            self,
            "Confirm",
            "Type the last AI response into your target window?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._start_typing()

    def _start_typing(self):
        self.type_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        delay = self.delay_input.value()
        self.status_label.setText(f"Starting in {delay}s - switch to your target window!")
        self._log(f"Typing started. Delay: {delay}s, WPM: {self.wpm_input.value()}, Mistakes: {self.mistake_input.value()}")

        self.typing_worker = TypingWorker(
            text         = self.last_response,
            wpm          = self.wpm_input.value(),
            mistake_rate = self.mistake_input.value(),
            max_speed    = self.max_speed_check.isChecked(),
            delay        = delay,
        )
        self.typing_worker.status_update.connect(self.on_type_status)
        self.typing_worker.countdown.connect(self.on_countdown)
        self.typing_worker.finished.connect(self.on_type_finished)
        self.typing_worker.start()

    @pyqtSlot(str)
    def on_type_status(self, msg):
        self.status_label.setText(msg)
        self._log(msg)

    @pyqtSlot(int)
    def on_countdown(self, seconds):
        self.status_label.setText(f"Starting in {seconds}s - switch to your target window!")
        self._log(f"Countdown: {seconds}s")

    @pyqtSlot()
    def on_type_finished(self):
        self.type_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self._log("Typing finished.")

    def stop_typing(self):
        if self.typing_worker:
            self.typing_worker.stop()
        self.status_label.setText("Stopping...")
        self._log("Typing stopped by user.")


# --- Help Panel ---
class HelpPanel(QWidget):
    def __init__(self):
        super().__init__()
        self._build_ui()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setSpacing(18)
        layout.setContentsMargins(28, 24, 28, 24)

        def section(title, body):
            t = QLabel(title)
            t.setObjectName("helpHeading")
            layout.addWidget(t)
            b = QLabel(body)
            b.setObjectName("helpBody")
            b.setWordWrap(True)
            layout.addWidget(b)

        section("Quick Start",
            "1. Open the Auto Typer tab.\n"
            "2. Paste the text you want typed into the box.\n"
            "3. Set your speed, mistake rate, and delay.\n"
            "4. Click Start Typing.\n"
            "5. You have the delay time to click into your target window (e.g. Google Docs).\n"
            "6. The app will type your text automatically."
        )

        section("Auto Typer - Settings",
            "Speed (WPM): How fast the text gets typed. 1000 WPM is the default. "
            "Higher = faster. Max is 50,000.\n\n"
            "Mistake Rate (0-1): Simulates human typos. 0 means no mistakes, "
            "1 means a mistake on every character. 0.05 to 0.1 is realistic.\n\n"
            "Start Delay (sec): How many seconds to wait before typing begins. "
            "Use this time to click into your target window. Default is 10 seconds.\n\n"
            "Max Speed: Ignores WPM and types as fast as your computer can go. "
            "Combine with a mistake rate for fast but human-looking output.\n\n"
            "Dry Run: Previews your settings without actually typing anything. "
            "Good for checking word count before committing."
        )

        section("Auto Typer - Buttons",
            "Start Typing: Begins the countdown then types your text.\n\n"
            "Stop: Immediately cancels typing mid-way through.\n\n"
            "Terminate: Fully closes the app."
        )

        section("AI Chat Mode",
            "1. Switch to the AI Chat tab.\n"
            "2. Type a message to the AI and hit Send.\n"
            "3. The AI will respond in the chat window.\n"
            "4. When you want the AI's response typed out, click Type Last Response.\n"
            "5. A confirmation popup will appear - confirm and switch to your target window.\n"
            "6. The response will be typed using your speed and delay settings."
        )

        section("AI Chat - Settings",
            "The speed, mistake rate, delay, and max speed settings in the AI Chat tab "
            "only apply when typing the AI's response - they don't affect the chat itself.\n\n"
            "The AI remembers the full conversation history within the same session. "
            "If you close and reopen the app, the history resets."
        )

        section("Tips",
            "- Use a 10-second delay so you have time to click your target window.\n"
            "- A mistake rate of 0.05 looks very natural without being obvious.\n"
            "- If typing stops mid-way, check that your target window still has focus.\n"
            "- Your API key is stored in a .env file on your Desktop - never share it.\n"
            "- The app needs Accessibility and Input Monitoring permissions in System Settings > Privacy & Security to type.\n"
            "- If the app crashes on typing, re-add it under Accessibility in System Settings."
        )

        section("Commands",
            "Debug Terminal — click the gear icon (⚙) in the top right corner, then click "
            "'Open Debug Terminal' in the Settings window. "
            "The debug terminal shows a live log of everything happening behind the scenes - "
            "API calls, typing events, countdowns, errors, and more. "
            "It's colour coded: [AI] for chat events, [AutoTyper] for typing events, [System] for app events."
        )

        section("Keyboard Shortcuts",
            "Enter — send a message in AI Chat (no need to click Send).\n"
            "Cmd+X — emergency stop while typing (default stop combo)."
        )

        section("Troubleshooting",
            "App won't type anything: Go to System Settings > Privacy & Security > Accessibility and make sure the app is listed and toggled on. Same for Input Monitoring.\n\n"
            "AI not responding: Check your .env file has NIM_API_KEY=nvapi-... with no quotes or spaces. Also check your internet connection.\n\n"
            "Typing the wrong window: Make sure you click into your target window before the countdown finishes.\n\n"
            "App closes immediately on double click: Run it via the AutoTyper.command file instead."
        )

        layout.addStretch()
        scroll.setWidget(container)
        outer.addWidget(scroll)


# --- Settings Window ---
# Separate window opened via the gear icon in the header.
# Keeps settings UI out of the main window to avoid clutter.
# The debug terminal is accessible from here so it works from any tab.
class SettingsWindow(QWidget):
    defaults_changed = pyqtSignal(float, int, float)

    def __init__(self, debug_window=None, typer_panel=None, ai_panel=None, main_window=None):
        super().__init__()
        self.debug_window = debug_window
        self.typer_panel = typer_panel
        self.ai_panel = ai_panel
        self.main_window = main_window
        self.setWindowTitle("Mintkey Settings")
        self.setMinimumWidth(UIConfig.SETTINGS_MIN_WIDTH)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        # --- General section ---
        general_label = QLabel("General")
        general_label.setObjectName("section")
        layout.addWidget(general_label)

        # Theme selector
        theme_row = QHBoxLayout()
        theme_row.addWidget(QLabel("Theme"))
        theme_row.addStretch()
        self.theme_dropdown = QComboBox()
        for name in THEMES:
            self.theme_dropdown.addItem(name)
        # Show the currently active theme
        if self.main_window:
            current = self.main_window.current_theme
            idx = list(THEMES.keys()).index(current) if current in THEMES else 0
            self.theme_dropdown.setCurrentIndex(idx)
        self.theme_dropdown.setFixedWidth(150)
        self.theme_dropdown.currentTextChanged.connect(self._on_theme_changed)
        theme_row.addWidget(self.theme_dropdown)
        layout.addLayout(theme_row)

        # Default WPM
        wpm_row = QHBoxLayout()
        wpm_row.addWidget(QLabel("Default Speed (WPM)"))
        wpm_row.addStretch()
        self.default_wpm = QDoubleSpinBox()
        self.default_wpm.setRange(TypingConfig.WPM_MIN, TypingConfig.WPM_MAX)
        self.default_wpm.setValue(TypingConfig.DEFAULT_WPM)
        self.default_wpm.setDecimals(0)
        self.default_wpm.setFixedWidth(100)
        wpm_row.addWidget(self.default_wpm)
        layout.addLayout(wpm_row)

        # Default delay
        delay_row = QHBoxLayout()
        delay_row.addWidget(QLabel("Default Start Delay (seconds)"))
        delay_row.addStretch()
        self.default_delay = QSpinBox()
        self.default_delay.setRange(TypingConfig.DELAY_MIN, TypingConfig.DELAY_MAX)
        self.default_delay.setValue(TypingConfig.DEFAULT_DELAY)
        self.default_delay.setFixedWidth(100)
        delay_row.addWidget(self.default_delay)
        layout.addLayout(delay_row)

        # Default mistake rate
        mistake_row = QHBoxLayout()
        mistake_row.addWidget(QLabel("Default Mistake Rate (0-1)"))
        mistake_row.addStretch()
        self.default_mistake = QDoubleSpinBox()
        self.default_mistake.setRange(TypingConfig.MISTAKE_RATE_MIN, TypingConfig.MISTAKE_RATE_MAX)
        self.default_mistake.setValue(TypingConfig.DEFAULT_MISTAKE_RATE)
        self.default_mistake.setSingleStep(TypingConfig.MISTAKE_STEP)
        self.default_mistake.setDecimals(2)
        self.default_mistake.setFixedWidth(100)
        mistake_row.addWidget(self.default_mistake)
        layout.addLayout(mistake_row)

        # Divider
        sep = QFrame()
        sep.setObjectName("separator")
        layout.addWidget(sep)

        # --- Debug section ---
        debug_label = QLabel("Debug")
        debug_label.setObjectName("section")
        layout.addWidget(debug_label)

        debug_desc = QLabel(
            "Open the debug terminal to see a live log of everything "
            "happening behind the scenes - API calls, typing events, "
            "errors, and more."
        )
        debug_desc.setWordWrap(True)
        layout.addWidget(debug_desc)

        debug_btn = QPushButton("Open Debug Terminal")
        debug_btn.clicked.connect(self._open_debug)
        layout.addWidget(debug_btn, alignment=Qt.AlignmentFlag.AlignLeft)

        # Version info
        sep2 = QFrame()
        sep2.setObjectName("separator")
        layout.addWidget(sep2)

        version_label = QLabel(f"Mintkey  ·  Version {CURRENT_VERSION}")
        version_label.setObjectName("versionLabel")
        layout.addWidget(version_label)

        layout.addStretch()

        # Wire spinboxes to push defaults to panels whenever they change
        self.default_wpm.valueChanged.connect(self._push_defaults)
        self.default_delay.valueChanged.connect(self._push_defaults)
        self.default_mistake.valueChanged.connect(self._push_defaults)

    def _on_theme_changed(self, theme_name: str):
        if self.main_window:
            self.main_window.apply_theme(theme_name)

    def _push_defaults(self):
        """Push current default values to both panels."""
        wpm = self.default_wpm.value()
        delay = self.default_delay.value()
        mistake = self.default_mistake.value()
        log.debug("Default settings changed: wpm=%.0f, delay=%d, mistake=%.2f", wpm, delay, mistake)
        if self.typer_panel:
            self.typer_panel.apply_defaults(wpm, delay, mistake)
        if self.ai_panel:
            self.ai_panel.apply_defaults(wpm, delay, mistake)

    def _open_debug(self):
        if self.debug_window:
            self.debug_window.show()
            self.debug_window.raise_()
        self.debug_window.log("System", "Debug terminal opened from Settings.")


# --- Main Window ---
class MainWindow(QMainWindow):
    def __init__(self, app=None, saved_theme=None):
        super().__init__()
        self.app = app
        self.current_theme = saved_theme or DEFAULT_THEME
        self.setWindowTitle("Mintkey")
        self.setMinimumSize(UIConfig.WINDOW_MIN_WIDTH, UIConfig.WINDOW_MIN_HEIGHT)
        self._build_ui()
        self._start_update_check()
        # Apply saved theme colors to inline styles after build
        if saved_theme and saved_theme != DEFAULT_THEME:
            self.apply_theme(saved_theme)

    def apply_theme(self, theme_name: str):
        """Apply a theme across the whole app and save the preference."""
        log.info("Theme changed to: %s", theme_name)
        global DARK_BG, PANEL_BG, ACCENT, ACCENT_DIM, TEXT_PRIMARY, TEXT_DIM, DANGER, BORDER, INPUT_BG
        t = THEMES.get(theme_name, THEMES[DEFAULT_THEME])
        DARK_BG =      t["DARK_BG"]
        PANEL_BG =     t["PANEL_BG"]
        ACCENT =       t["ACCENT"]
        ACCENT_DIM =   t["ACCENT_DIM"]
        TEXT_PRIMARY = t["TEXT_PRIMARY"]
        TEXT_DIM =     t["TEXT_DIM"]
        DANGER =       t["DANGER"]
        BORDER =       t["BORDER"]
        INPUT_BG =     t["INPUT_BG"]

        # Save preference so it persists across launches
        settings_set("theme", theme_name)
        self.current_theme = theme_name

        # Apply global QSS
        if self.app:
            self.app.setStyleSheet(build_style(t))

        # Refresh inline styles that reference color tokens directly
        self.header.setStyleSheet(f"background-color: {PANEL_BG}; border-bottom: 1.5px solid {BORDER};")
        self.title_label.setStyleSheet(f"color: {ACCENT}; font-size: 20px; font-weight: bold; letter-spacing: 3px;")
        self.footer.setStyleSheet(f"background-color: {PANEL_BG};")
        self.settings_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {ACCENT};
                border: none;
                border-radius: 18px;
                font-size: 18px;
                padding: 0px;
            }}
            QPushButton:hover {{
                background-color: {PANEL_BG};
            }}
        """)

    def _start_update_check(self):
        # Wait after launch before checking so the window is fully visible
        QTimer.singleShot(AppConfig.UPDATE_CHECK_DELAY_MS, self._run_update_check)

    def _run_update_check(self):
        self.update_checker = UpdateChecker()
        self.update_checker.update_available.connect(self._on_update_available)
        self.update_checker.start()

    @pyqtSlot(int)
    def _on_update_available(self, new_version: int):
        # This fires on the main thread thanks to pyqtSignal
        # Show a clean popup asking if they want to update
        reply = QMessageBox.question(
            self,
            "Update Available",
            f"Mintkey v{new_version} is available.\nYou're on v{CURRENT_VERSION}.\n\nOpen the download page?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            webbrowser.open(AppConfig.DOWNLOAD_URL)
            QApplication.quit()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Header
        self.header = QWidget()
        self.header.setStyleSheet(f"background-color: {PANEL_BG}; border-bottom: 1.5px solid {BORDER};")
        header_layout = QVBoxLayout(self.header)
        header_layout.setContentsMargins(20, 16, 20, 0)
        header_layout.setSpacing(0)

        self.title_label = QLabel("MINTKEY")
        self.title_label.setStyleSheet(f"color: {ACCENT}; font-size: 20px; font-weight: bold; letter-spacing: 3px;")
        header_layout.addWidget(self.title_label)

        # Toggle tabs
        tab_row = QHBoxLayout()
        tab_row.setSpacing(0)
        tab_row.setContentsMargins(0, 10, 0, 0)

        self.typer_tab = QPushButton("Auto Typer")
        self.typer_tab.setObjectName("toggle")
        self.typer_tab.setCheckable(True)
        self.typer_tab.setChecked(True)
        self.typer_tab.clicked.connect(lambda: self.switch_tab(0))

        self.ai_tab = QPushButton("AI Chat")
        self.ai_tab.setObjectName("toggle")
        self.ai_tab.setCheckable(True)
        self.ai_tab.clicked.connect(lambda: self.switch_tab(1))

        self.help_tab = QPushButton("Help")
        self.help_tab.setObjectName("toggle")
        self.help_tab.setCheckable(True)
        self.help_tab.clicked.connect(lambda: self.switch_tab(2))

        tab_row.addWidget(self.typer_tab)
        tab_row.addWidget(self.ai_tab)
        tab_row.addWidget(self.help_tab)
        tab_row.addStretch()

        # Gear button - opens Settings window
        self.settings_btn = QPushButton("⚙")
        self.settings_btn.setFixedWidth(36)
        self.settings_btn.setFixedHeight(36)
        self.settings_btn.setToolTip("Settings")
        self.settings_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {ACCENT};
                border: none;
                border-radius: 18px;
                font-size: 18px;
                padding: 0px;
            }}
            QPushButton:hover {{
                background-color: {PANEL_BG};
            }}
        """)
        self.settings_btn.clicked.connect(self._open_settings)
        tab_row.addWidget(self.settings_btn)

        header_layout.addLayout(tab_row)
        main_layout.addWidget(self.header)

        # Panels
        self.stack = QStackedWidget()
        self.debug_window = DebugWindow()
        self.typer_panel = AutoTyperPanel(debug_window=self.debug_window)
        self.ai_panel = AIChatPanel(debug_window=self.debug_window)
        self.help_panel = HelpPanel()
        self.stack.addWidget(self.typer_panel)
        self.stack.addWidget(self.ai_panel)
        self.stack.addWidget(self.help_panel)
        main_layout.addWidget(self.stack)

        # Footer terminate button
        self.footer = QWidget()
        self.footer.setStyleSheet(f"background-color: {PANEL_BG};")
        footer_layout = QHBoxLayout(self.footer)
        footer_layout.setContentsMargins(20, 10, 20, 10)
        footer_layout.addStretch()

        terminate_btn = QPushButton("Terminate")
        terminate_btn.setObjectName("danger")
        terminate_btn.setFixedWidth(120)
        terminate_btn.setFixedHeight(36)
        terminate_btn.clicked.connect(self.terminate)
        footer_layout.addWidget(terminate_btn)

        main_layout.addWidget(self.footer)

    def switch_tab(self, index):
        self.stack.setCurrentIndex(index)
        self.typer_tab.setChecked(index == 0)
        self.ai_tab.setChecked(index == 1)
        self.help_tab.setChecked(index == 2)
        self.settings_btn.setChecked(False)

    def _open_settings(self):
        if not hasattr(self, '_settings_window') or self._settings_window is None:
            self._settings_window = SettingsWindow(
                debug_window=self.debug_window,
                typer_panel=self.typer_panel,
                ai_panel=self.ai_panel,
                main_window=self,
            )
        self._settings_window.show()
        self._settings_window.raise_()
        self._settings_window.activateWindow()

    def terminate(self):
        QApplication.quit()


def main():
    app = QApplication(sys.argv)
    log.info("=== Mintkey started ===")
    log.info("Version: %d", CURRENT_VERSION)

    saved = settings_load()
    saved_theme = saved.get("theme", DEFAULT_THEME)
    log.info("Loaded theme: %s", saved_theme)

    app.setStyleSheet(build_style(THEMES.get(saved_theme, THEMES[DEFAULT_THEME])))
    window = MainWindow(app=app, saved_theme=saved_theme)
    window.show()
    log.info("Main window displayed")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
