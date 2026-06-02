"""
services/ai_service.py

All NVIDIA NIM AI logic lives here.
The UI (AutoTyper.py) imports from this module and calls the service
instead of making API requests directly.

Architecture decision: AIWorker is kept as a QThread here because it
needs to communicate results back to the UI via PyQt signals. Ideally a
service module would be pure Python with no framework dependency, but
changing that would require redesigning how results flow back to the UI.
That's noted as future technical debt.

The .env file is loaded in AutoTyper.py (the entry point) before any UI
or service code runs. By the time AIWorker.run() is called, the API key
is already in os.environ, so this module just reads it from there.
"""

from __future__ import annotations

import os
import requests

from PyQt6.QtCore import QThread, pyqtSignal

from config import APIConfig
from utils.logger import get_logger

log = get_logger(__name__)


# --- Model registry ---
# Add or remove models here without touching the UI code.
# Each entry is (display_name, model_string, description).
NIM_MODELS: list[tuple[str, str, str]] = [
    (
        "Mistral Medium 3.5",
        "mistralai/mistral-medium-3.5-128b",
        "Best all-rounder. Fast, smart, great for chat and writing.",
    ),
    (
        "Mistral Small 4",
        "mistralai/mistral-small-4-119b-2603",
        "Lighter and faster than Medium. Good for quick back-and-forth.",
    ),
    (
        "GLM 4.7",
        "z-ai/glm-4.7",
        "Strong at reasoning and tool use. Good for technical questions.",
    ),
    (
        "MiniMax M2.7",
        "minimaxai/minimax-m2.7",
        "Huge 230B model. Most capable but can be slower.",
    ),
    (
        "Nemotron Super 120B",
        "nvidia/nemotron-3-super-120b-a12b",
        "NVIDIA's own model. Good for coding and planning tasks.",
    ),
]

# Default model - the first entry in the registry above.
NIM_MODEL: str = NIM_MODELS[0][1]


def build_payload(messages: list[dict], model: str) -> dict:
    """
    Construct the request payload for the NIM API.
    Kept as a standalone function so it can be tested independently
    of the threading layer.
    """
    return {
        "model": model,
        "messages": messages,
        "max_tokens": APIConfig.MAX_TOKENS,
        "temperature": APIConfig.TEMPERATURE,
    }


def parse_response(data: dict) -> str:
    """
    Extract the reply text from the API response.

    Some NIM models (e.g. nemotron reasoning models) return their output
    in a 'reasoning' field instead of 'content', leaving content blank.
    This function handles both cases and returns a fallback message if
    neither field has content.
    """
    message = data["choices"][0]["message"]
    reply = message.get("content", "").strip()
    if not reply:
        # Fallback: check reasoning field used by some NIM models
        reply = message.get("reasoning", "").strip()
    if not reply:
        reply = "(No response received. Try rephrasing your message.)"
    return reply


class AIWorker(QThread):
    """
    Background thread that sends a message to the NIM API and emits
    the response back to the UI via signals.

    Accepts:
        messages  - full conversation history as a list of role/content dicts
        api_key   - NIM API key (read from os.environ in AIChatPanel)
        model     - model string from NIM_MODELS (defaults to NIM_MODEL)

    Signals:
        response_ready(str) - emitted with the reply text on success
        error(str)          - emitted with the error message on failure
    """

    response_ready = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, messages: list[dict], api_key: str, model: str = NIM_MODEL):
        super().__init__()
        self.messages = messages
        self.api_key = api_key
        self.model = model
        self._cancelled = False

    def cancel(self) -> None:
        """
        Cancel the in-flight request.
        Sets a flag so signals aren't emitted after cancellation,
        then terminates the thread.
        """
        self._cancelled = True
        self.terminate()

    def run(self) -> None:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = build_payload(self.messages, self.model)
        log.info("Sending request to NIM API (model=%s, messages=%d)", self.model, len(self.messages))
        try:
            response = requests.post(
                APIConfig.URL, headers=headers, json=payload, timeout=APIConfig.TIMEOUT
            )
            response.raise_for_status()
            reply = parse_response(response.json())
            log.info("NIM API responded (%d chars)", len(reply))
            if not self._cancelled:
                self.response_ready.emit(reply)
        except Exception as e:
            log.error("NIM API error: %s", e)
            if not self._cancelled:
                self.error.emit(str(e))
