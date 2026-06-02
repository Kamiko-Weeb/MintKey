"""
services/typing_engine.py

Pure-Python typing execution engine.
Zero PyQt dependency — this module must never import from PyQt6.

The engine is designed to run synchronously inside a QThread:
    TypingWorker.run() calls engine.start_typing(), which blocks until
    typing finishes, is cancelled, or fails.

The engine communicates back to the caller exclusively through three
callbacks supplied at construction time:

    on_status(str)    — human-readable status for the UI status bar
    on_countdown(int) — seconds remaining in the pre-type delay
    on_finished()     — called exactly once when the run is fully done

External control (thread-safe):
    stop_typing()           — signal the engine to halt at the next checkpoint
    lost_focus: bool        — write True to pause mid-type, False to resume

Future extension points are marked with # FUTURE: comments.
"""

from __future__ import annotations

import random
import threading
import time
from typing import Callable

from config import TypingConfig
from utils.logger import get_logger

log = get_logger(__name__)

# Lowercase alphabet used for generating wrong characters in mistake simulation
_ALPHABET = "abcdefghijklmnopqrstuvwxyz"


class TypingEngine:
    """
    Self-contained typing execution engine.

    Lifecycle:
        engine = TypingEngine(on_status=..., on_countdown=..., on_finished=...)
        engine.start_typing(text, wpm, mistake_rate, max_speed, delay)  # blocks
        # from another thread at any point:
        engine.stop_typing()
    """

    def __init__(
        self,
        on_status: Callable[[str], None],
        on_countdown: Callable[[int], None],
        on_finished: Callable[[], None],
    ) -> None:
        self._on_status = on_status
        self._on_countdown = on_countdown
        self._on_finished = on_finished

        # threading.Event is the stop signal. Set by stop_typing() from any thread.
        # Checked at every safe checkpoint inside the typing loop.
        self._stop_event = threading.Event()

        # Pause signal: write True from the UI when the target window loses focus.
        # The engine polls this during typing and pauses until it returns to False.
        # FUTURE: wire this to a real OS focus-detection hook.
        self.lost_focus: bool = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start_typing(
        self,
        text: str,
        wpm: float,
        mistake_rate: float,
        max_speed: bool,
        delay: int,
    ) -> None:
        """
        Execute the full typing sequence synchronously in the calling thread.

        Designed to be called from TypingWorker.run() (a QThread).
        Blocks until typing completes, is stopped, or fails.
        To stop mid-run, call stop_typing() from another thread.
        """
        self._stop_event.clear()
        self.lost_focus = False
        self._run(text, wpm, mistake_rate, max_speed, delay)

    def stop_typing(self) -> None:
        """
        Signal the engine to stop at the next safe checkpoint.
        Safe to call from any thread at any time.
        """
        log.info("Stop requested")
        self._stop_event.set()

    # ------------------------------------------------------------------
    # Internal execution
    # ------------------------------------------------------------------

    def _human_delay(self, base_interval: float, character: str) -> None:
        """
        Sleep for a humanized duration after typing one character.

        Does nothing when base_interval is 0 (max_speed mode).

        Three layers of variation are applied:
          1. Gaussian jitter    — random ±variance around the base interval
          2. Boundary pauses    — longer pause at word/sentence boundaries
          3. Micro-pauses       — rare random hesitations simulating thinking
        """
        if base_interval <= 0:
            return

        # Layer 1: Gaussian jitter — no two keystrokes take the same time
        delay = base_interval * max(0.1, random.gauss(1.0, TypingConfig.TIMING_VARIANCE))

        # Layer 2: natural boundary pauses
        if character == " ":
            delay *= TypingConfig.WORD_PAUSE_MULT       # brief word-boundary pause
        elif character in ".!?":
            delay *= TypingConfig.SENTENCE_PAUSE_MULT   # longer sentence-end pause

        # Layer 3: occasional micro-pause (thinking, reading ahead, hesitation)
        if random.random() < TypingConfig.MICRO_PAUSE_CHANCE:
            delay += random.uniform(0.05, TypingConfig.MICRO_PAUSE_MAX)

        time.sleep(delay)

    def _run(
        self,
        text: str,
        wpm: float,
        mistake_rate: float,
        max_speed: bool,
        delay: int,
    ) -> None:
        """Full typing sequence: import check → countdown → type → finish."""

        # ---- Dependency check ----
        try:
            import pyautogui
            pyautogui.FAILSAFE = False
        except ImportError:
            log.error("pyautogui not installed")
            self._on_status("Error: pyautogui not installed.")
            self._on_finished()
            return

        log.info(
            "Typing started: %d chars, %.0f wpm, %.2f mistakes, max_speed=%s, delay=%ds",
            len(text), wpm, mistake_rate, max_speed, delay,
        )

        # ---- Countdown phase ----
        # FUTURE: expose remaining countdown via a dedicated callback so the
        # UI can drive a progress bar instead of just a label.
        for remaining in range(delay, 0, -1):
            if self._stop_event.is_set():
                log.info("Typing cancelled during countdown")
                self._on_status("Cancelled.")
                self._on_finished()
                return
            self._on_countdown(remaining)
            time.sleep(1)

        log.debug("Countdown complete, entering typing loop")
        self._on_status("Typing...")

        # ---- Timing ----
        # interval = 0 means write as fast as pyautogui can go (max_speed mode).
        # FUTURE: speed profiles (e.g. ramp-up, burst/pause) would replace this
        # single interval calculation.
        interval = (
            0.0 if max_speed
            else 60.0 / (wpm * TypingConfig.CHARS_PER_WORD)
        )

        # ---- Typing loop ----
        # Characters are typed one-at-a-time (no batching) so humanized
        # timing can be applied to every individual keystroke.
        idx = 0
        text_len = len(text)

        while idx < text_len:

            # Stop checkpoint — checked before every character
            if self._stop_event.is_set():
                self._on_status("Stopped.")
                break

            # Focus-lost pause — FUTURE: replace with event-driven notification
            # instead of polling so it reacts instantly rather than after
            # FOCUS_POLL_INTERVAL seconds.
            if self.lost_focus:
                self._on_status("Paused - switch back to target window...")
                while self.lost_focus and not self._stop_event.is_set():
                    time.sleep(TypingConfig.FOCUS_POLL_INTERVAL)
                if self._stop_event.is_set():
                    break
                self._on_status("Resumed typing...")

            character = text[idx]

            # ---- Humanization: mistake injection ----
            # FUTURE: a speed-profile hook would also live here — e.g. slow down
            # before punctuation, pause after sentences.
            make_mistake = (
                mistake_rate > 0
                and character.isalpha()
                and random.random() < mistake_rate
            )

            if make_mistake:
                # Pick a wrong character that differs from the intended one
                choices = [c for c in _ALPHABET if c != character.lower()]
                wrong_char = random.choice(choices)
                if character.isupper():
                    wrong_char = wrong_char.upper()

                # Type wrong → humanized pause → backspace → humanized pause → correct
                pyautogui.write(wrong_char, interval=0)
                self._human_delay(interval, wrong_char)
                pyautogui.press("backspace")
                self._human_delay(interval, character)
                pyautogui.write(character, interval=0)
                self._human_delay(interval, character)

            else:
                pyautogui.write(character, interval=0)
                self._human_delay(interval, character)

            idx += 1

        # ---- Finish ----
        if not self._stop_event.is_set():
            log.info("Typing completed successfully")
            self._on_status("Done!")
        else:
            log.info("Typing stopped by user")

        self._on_finished()
