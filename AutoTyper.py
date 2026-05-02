#!/usr/bin/env python3
"""Auto Typer V13 - PyQt6 GUI with AI Chat Mode"""

from __future__ import annotations

import sys
import os
import time
import random
import threading
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
CHARS_PER_WORD = 5
DEFAULT_WPM = 1000.0
TARGET_TIME_SECONDS = 10.0
NIM_API_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
NIM_MODEL = "mistralai/mistral-medium-3.5-128b"
IS_MAC = platform.system() == "Darwin"
IS_WINDOWS = platform.system() == "Windows"

# Version system - bump this number every release
CURRENT_VERSION = 29
VERSION_CHECK_URL = "https://raw.githubusercontent.com/Kamiko-Weeb/MintKey/main/version.txt"
DOWNLOAD_URL = "https://kamiko-weeb.github.io/MintKey"

# Ensure the Desktop directory is in the module search path so that
# the services package can always be found regardless of how the script
# is launched (terminal, PyInstaller, double-click, etc.)
import sys as _sys_path_fix
import pathlib as _pathlib
_desktop = str(_pathlib.Path.home() / "Desktop")
if _desktop not in _sys_path_fix.path:
    _sys_path_fix.path.insert(0, _desktop)

# AI logic lives in services/ai_service.py.
# Importing NIM_MODELS and AIWorker from there keeps this file focused on UI.
from services.ai_service import NIM_MODELS, NIM_MODEL, AIWorker  # noqa: E402


# --- Update Checker ---
# This runs in a background thread on launch so it never slows down the UI.
# It fetches version.txt from GitHub, compares to CURRENT_VERSION,
# and emits update_available if a newer version exists.
class UpdateChecker(QThread):
    update_available = pyqtSignal(int)  # emits the new version number

    def run(self):
        try:
            response = requests.get(VERSION_CHECK_URL, timeout=5)
            response.raise_for_status()
            latest = int(response.text.strip())
            if latest > CURRENT_VERSION:
                self.update_available.emit(latest)
        except Exception:
            # Silently ignore all errors - no internet, bad response, etc.
            pass

# --- Styling ---
DARK_BG = "#fdf6f8"
PANEL_BG = "#f5e6eb"
ACCENT = "#c4677a"
ACCENT_DIM = "#a04f62"
TEXT_PRIMARY = "#3d1a26"
TEXT_DIM = "#a07080"
DANGER = "#b03030"
BORDER = "#e8c4cc"

STYLE = f"""
QMainWindow, QWidget {{
    background-color: {DARK_BG};
    color: {TEXT_PRIMARY};
    font-family: 'Helvetica Neue', 'Arial Rounded MT Bold', sans-serif;
}}
QPushButton {{
    background-color: {PANEL_BG};
    color: {ACCENT};
    border: 1.5px solid {ACCENT};
    border-radius: 20px;
    padding: 8px 22px;
    font-size: 13px;
    font-weight: bold;
}}
QPushButton:hover {{
    background-color: {ACCENT};
    color: white;
}}
QPushButton:disabled {{
    color: {TEXT_DIM};
    border-color: {BORDER};
    background-color: {PANEL_BG};
    border-radius: 20px;
}}
QPushButton#danger {{
    color: {ACCENT};
    border-color: {ACCENT};
    border-radius: 20px;
}}
QPushButton#danger:hover {{
    background-color: {ACCENT};
    color: white;
}}
QPushButton#toggle {{
    border-radius: 0px;
    border: none;
    border-bottom: 2px solid transparent;
    padding: 10px 28px;
    font-size: 14px;
    background-color: transparent;
    color: {TEXT_DIM};
}}
QPushButton#toggle:checked {{
    color: {ACCENT};
    border-bottom: 2px solid {ACCENT};
}}
QTextEdit {{
    background-color: white;
    color: {TEXT_PRIMARY};
    border: 1.5px solid {BORDER};
    border-radius: 12px;
    padding: 10px;
    font-size: 13px;
    font-family: 'Helvetica Neue', sans-serif;
}}
QLabel {{
    color: {TEXT_DIM};
    font-size: 12px;
}}
QLabel#heading {{
    color: {TEXT_PRIMARY};
    font-size: 15px;
    font-weight: bold;
}}
QLabel#accent {{
    color: {ACCENT};
    font-size: 12px;
    font-weight: bold;
}}
QDoubleSpinBox, QSpinBox {{
    background-color: white;
    color: {TEXT_PRIMARY};
    border: 1.5px solid {BORDER};
    border-radius: 10px;
    padding: 4px 8px;
    font-size: 13px;
}}
QDoubleSpinBox::up-button, QSpinBox::up-button,
QDoubleSpinBox::down-button, QSpinBox::down-button {{
    width: 0px;
    height: 0px;
    border: none;
}}
QCheckBox {{
    color: {TEXT_PRIMARY};
    font-size: 13px;
    spacing: 8px;
}}
QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border: 1.5px solid {ACCENT};
    border-radius: 8px;
    background-color: white;
}}
QCheckBox::indicator:checked {{
    background-color: {ACCENT};
}}
QFrame#separator {{
    background-color: {BORDER};
    max-height: 1px;
}}
QScrollArea {{
    border: none;
    background-color: transparent;
}}
QLineEdit {{
    background-color: white;
    color: {TEXT_PRIMARY};
    border: 1.5px solid {BORDER};
    border-radius: 12px;
    padding: 10px 14px;
    font-size: 13px;
    font-family: 'Helvetica Neue', sans-serif;
}}
QComboBox {{
    background-color: white;
    color: {TEXT_PRIMARY};
    border: 1.5px solid {BORDER};
    border-radius: 12px;
    padding: 6px 12px;
    font-size: 12px;
}}
QComboBox::drop-down {{
    border: none;
    padding-right: 8px;
}}
QComboBox QAbstractItemView {{
    background-color: white;
    color: {TEXT_PRIMARY};
    border: 1.5px solid {BORDER};
    selection-background-color: {PANEL_BG};
    selection-color: {ACCENT};
}}
"""


# --- Worker thread for typing ---
class TypingWorker(QThread):
    status_update = pyqtSignal(str)
    finished = pyqtSignal()
    countdown = pyqtSignal(int)

    def __init__(self, text, wpm, mistake_rate, max_speed, delay, stop_event, focus_monitor):
        super().__init__()
        self.text = text
        self.wpm = wpm
        self.mistake_rate = mistake_rate
        self.max_speed = max_speed
        self.delay = delay
        self.stop_event = stop_event
        self.focus_monitor = focus_monitor

    def run(self):
        try:
            import pyautogui
            pyautogui.FAILSAFE = False
        except ImportError:
            self.status_update.emit("Error: pyautogui not installed.")
            self.finished.emit()
            return

        # Countdown
        for i in range(self.delay, 0, -1):
            if self.stop_event.is_set():
                self.status_update.emit("Cancelled.")
                self.finished.emit()
                return
            self.countdown.emit(i)
            time.sleep(1)

        self.status_update.emit("Typing...")

        interval = 0.0 if self.max_speed else 60.0 / (self.wpm * CHARS_PER_WORD)
        alphabet = "abcdefghijklmnopqrstuvwxyz"
        buffer = []
        i = 0
        text_len = len(self.text)

        while i < text_len:
            if self.stop_event.is_set():
                self.status_update.emit("Stopped.")
                break
            # Pause if focus lost
            if self.focus_monitor and self.focus_monitor.lost_focus:
                self.status_update.emit("Paused - switch back to target window...")
                while self.focus_monitor.lost_focus and not self.stop_event.is_set():
                    time.sleep(0.2)
                if self.stop_event.is_set():
                    break
                self.status_update.emit("Resumed typing...")

            character = self.text[i]
            make_mistake = (
                self.mistake_rate > 0
                and character.isalpha()
                and random.random() < self.mistake_rate
            )
            if make_mistake:
                if buffer:
                    pyautogui.write(''.join(buffer), interval=0)
                    buffer = []
                choices = [c for c in alphabet if c != character.lower()]
                wrong_char = random.choice(choices)
                if character.isupper():
                    wrong_char = wrong_char.upper()
                pyautogui.write(wrong_char, interval=0)
                if interval > 0:
                    time.sleep(interval)
                pyautogui.press("backspace")
                if interval > 0:
                    time.sleep(interval)
                pyautogui.write(character, interval=0)
                if interval > 0:
                    time.sleep(interval)
            else:
                buffer.append(character)
            i += 1

        if buffer and not self.stop_event.is_set():
            pyautogui.write(''.join(buffer), interval=0)

        if not self.stop_event.is_set():
            self.status_update.emit("Done!")
        self.finished.emit()


# --- Focus monitor (detects window switch) ---
class FocusMonitor:
    def __init__(self):
        self.lost_focus = False


# --- Auto Typer Panel ---
class AutoTyperPanel(QWidget):
    def __init__(self, debug_window=None):
        super().__init__()
        self.stop_event = threading.Event()
        self.typing_worker = None
        self.focus_monitor = FocusMonitor()
        self.debug_window = debug_window
        self._build_ui()

    def _log(self, msg: str):
        if self.debug_window and self.debug_window.isVisible():
            self.debug_window.log(f"[AutoTyper] {msg}")

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
        self.text_input.setMinimumHeight(140)
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
        self.wpm_input.setRange(10, 50000)
        self.wpm_input.setValue(1000)
        self.wpm_input.setDecimals(0)
        wpm_col.addWidget(self.wpm_input)
        settings_layout.addLayout(wpm_col)

        # Mistake rate
        mistake_col = QVBoxLayout()
        mistake_col.addWidget(QLabel("Mistake Rate (0-1)"))
        self.mistake_input = QDoubleSpinBox()
        self.mistake_input.setRange(0.0, 1.0)
        self.mistake_input.setValue(0.0)
        self.mistake_input.setSingleStep(0.05)
        self.mistake_input.setDecimals(2)
        mistake_col.addWidget(self.mistake_input)
        settings_layout.addLayout(mistake_col)

        # Delay
        delay_col = QVBoxLayout()
        delay_col.addWidget(QLabel("Start Delay (sec)"))
        self.delay_input = QSpinBox()
        self.delay_input.setRange(0, 60)
        self.delay_input.setValue(10)
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

        self.stop_event.clear()
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)

        delay = self.delay_input.value()
        self.status_label.setText(f"Starting in {delay}s - switch to your target window!")
        self._log(f"Typing started. Delay: {delay}s, WPM: {self.wpm_input.value()}, Mistakes: {self.mistake_input.value()}, MaxSpeed: {self.max_speed_check.isChecked()}")

        self.typing_worker = TypingWorker(
            text=text,
            wpm=self.wpm_input.value(),
            mistake_rate=self.mistake_input.value(),
            max_speed=self.max_speed_check.isChecked(),
            delay=delay,
            stop_event=self.stop_event,
            focus_monitor=self.focus_monitor,
        )
        self.typing_worker.status_update.connect(self.on_status)
        self.typing_worker.countdown.connect(self.on_countdown)
        self.typing_worker.finished.connect(self.on_finished)
        self.typing_worker.start()

    def stop_typing(self):
        self.stop_event.set()
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
        self.setWindowTitle("Debug Terminal")
        self.setMinimumSize(600, 400)
        self.setStyleSheet(f"""
            QWidget {{ background-color: #1a1a1a; color: #00ff88; font-family: 'SF Mono', 'Menlo', monospace; font-size: 12px; }}
            QTextEdit {{ background-color: #0f0f0f; color: #00ff88; border: 1px solid #2a2a2a; border-radius: 6px; padding: 10px; font-family: 'SF Mono', 'Menlo', monospace; }}
            QPushButton {{ background-color: #1a1a1a; color: #00ff88; border: 1px solid #00ff88; border-radius: 6px; padding: 6px 14px; font-weight: bold; }}
            QPushButton:hover {{ background-color: #00ff88; color: #0f0f0f; }}
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        title = QLabel("DEBUG TERMINAL")
        title.setStyleSheet("font-size: 13px; font-weight: bold; letter-spacing: 2px;")
        layout.addWidget(title)

        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        layout.addWidget(self.log_display)

        clear_btn = QPushButton("Clear")
        clear_btn.setFixedWidth(80)
        clear_btn.clicked.connect(self.log_display.clear)
        layout.addWidget(clear_btn, alignment=Qt.AlignmentFlag.AlignRight)

    def log(self, message: str):
        timestamp = time.strftime("%H:%M:%S")
        self.log_display.append(f"[{timestamp}] {message}")
        self.log_display.verticalScrollBar().setValue(
            self.log_display.verticalScrollBar().maximum()
        )


# --- AI Chat Panel ---
class AIChatPanel(QWidget):
    def __init__(self, debug_window=None):
        super().__init__()
        self.api_key = os.environ.get("NIM_API_KEY", "")
        self.conversation = [{"role": "system", "content": "You are a helpful assistant."}]
        self.last_response = None
        self.ai_worker = None
        self.stop_event = threading.Event()
        self.debug_window = debug_window
        self._build_ui()

    def _log(self, msg: str):
        if self.debug_window and self.debug_window.isVisible():
            self.debug_window.log(f"[AI] {msg}")

    def _update_model_desc(self, index):
        self.model_desc.setText(NIM_MODELS[index][2])

    def _open_debug(self):
        if self.debug_window:
            self.debug_window.show()
            self.debug_window.raise_()
            self.debug_window.log("[System] Debug terminal opened.")

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
        self.model_desc.setStyleSheet(f"color: {TEXT_DIM}; font-size: 11px; padding-left: 2px;")
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
        self.wpm_input.setRange(10, 50000)
        self.wpm_input.setValue(1000)
        self.wpm_input.setDecimals(0)
        self.wpm_input.setFixedWidth(90)
        wpm_col.addWidget(self.wpm_input)
        settings_row.addLayout(wpm_col)

        mistake_col = QVBoxLayout()
        mistake_col.setSpacing(2)
        mistake_col.addWidget(QLabel("Mistakes"))
        self.mistake_input = QDoubleSpinBox()
        self.mistake_input.setRange(0.0, 1.0)
        self.mistake_input.setValue(0.0)
        self.mistake_input.setSingleStep(0.05)
        self.mistake_input.setDecimals(2)
        self.mistake_input.setFixedWidth(80)
        mistake_col.addWidget(self.mistake_input)
        settings_row.addLayout(mistake_col)

        delay_col = QVBoxLayout()
        delay_col.setSpacing(2)
        delay_col.addWidget(QLabel("Delay (s)"))
        self.delay_input = QSpinBox()
        self.delay_input.setRange(0, 60)
        self.delay_input.setValue(10)
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

        # Handle /terminal command
        if msg.lower() == "/terminal":
            self.chat_input.clear()
            self._open_debug()
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
        self.debug_window.log("Debug terminal opened.")

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
        self.stop_event.clear()
        self.type_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        delay = self.delay_input.value()
        self.status_label.setText(f"Starting in {delay}s - switch to your target window!")
        self._log(f"Typing started. Delay: {delay}s, WPM: {self.wpm_input.value()}, Mistakes: {self.mistake_input.value()}")

        self.typing_worker = TypingWorker(
            text=self.last_response,
            wpm=self.wpm_input.value(),
            mistake_rate=self.mistake_input.value(),
            max_speed=self.max_speed_check.isChecked(),
            delay=delay,
            stop_event=self.stop_event,
            focus_monitor=None,
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
        self.stop_event.set()
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
            t.setObjectName("heading")
            t.setStyleSheet(f"color: {ACCENT}; font-size: 14px; font-weight: bold; margin-top: 6px;")
            layout.addWidget(t)
            b = QLabel(body)
            b.setWordWrap(True)
            b.setStyleSheet(f"color: {TEXT_PRIMARY}; font-size: 13px; line-height: 1.6;")
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
            "/terminal — type this in the AI Chat input and press Send (or Enter) to open the debug terminal. "
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


# --- Main Window ---
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Mintkey")
        self.setMinimumSize(680, 620)
        self._build_ui()
        self._start_update_check()

    def _start_update_check(self):
        # Wait 2 seconds after launch before checking so the window is fully visible
        QTimer.singleShot(2000, self._run_update_check)

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
            webbrowser.open(DOWNLOAD_URL)
            QApplication.quit()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Header
        header = QWidget()
        header.setStyleSheet(f"background-color: {PANEL_BG}; border-bottom: 1.5px solid {BORDER};")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(20, 16, 20, 0)
        header_layout.setSpacing(0)

        title = QLabel("AUTO TYPER")
        title.setStyleSheet(f"color: {ACCENT}; font-size: 20px; font-weight: bold; letter-spacing: 3px;")
        title.setText("MINTKEY")
        header_layout.addWidget(title)

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
        header_layout.addLayout(tab_row)
        main_layout.addWidget(header)

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
        footer = QWidget()
        footer.setStyleSheet(f"background-color: {PANEL_BG};")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(20, 10, 20, 10)
        footer_layout.addStretch()

        terminate_btn = QPushButton("Terminate")
        terminate_btn.setObjectName("danger")
        terminate_btn.setFixedWidth(120)
        terminate_btn.setFixedHeight(36)
        terminate_btn.clicked.connect(self.terminate)
        footer_layout.addWidget(terminate_btn)

        main_layout.addWidget(footer)

    def switch_tab(self, index):
        self.stack.setCurrentIndex(index)
        self.typer_tab.setChecked(index == 0)
        self.ai_tab.setChecked(index == 1)
        self.help_tab.setChecked(index == 2)

    def terminate(self):
        QApplication.quit()


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(STYLE)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
