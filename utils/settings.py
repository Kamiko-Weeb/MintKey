"""
utils/settings.py

Handles reading and writing persistent user settings to disk.
Settings are stored as JSON in ~/.mintkey_settings.json

Using the home directory with a dot prefix keeps the file hidden
and out of the way - same convention most Mac apps use for config files.

Architecture decision: keeping this in its own module means any part
of the app can import and use it without depending on the UI layer.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from config import TypingConfig, UIConfig
from utils.logger import get_logger

log = get_logger(__name__)

# Where settings are saved - hidden file in the user's home directory
SETTINGS_PATH = Path.home() / ".mintkey_settings.json"

# Default values used when no settings file exists yet.
# Values are sourced from config so there is one place to change them.
DEFAULTS: dict = {
    "theme":               UIConfig.DEFAULT_THEME,
    "default_wpm":         TypingConfig.DEFAULT_WPM,
    "default_delay":       TypingConfig.DEFAULT_DELAY,
    "default_mistake_rate": TypingConfig.DEFAULT_MISTAKE_RATE,
}


def load() -> dict:
    """
    Load settings from disk. Returns defaults if the file doesn't exist
    or is corrupted. Never raises - safe to call at startup.
    """
    try:
        with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        # Merge with defaults so new keys added in future versions
        # always have a fallback value
        merged = {**DEFAULTS, **data}
        log.debug("Settings loaded from %s", SETTINGS_PATH)
        return merged
    except FileNotFoundError:
        log.debug("No settings file found, using defaults")
        return dict(DEFAULTS)
    except Exception as e:
        log.warning("Failed to load settings (%s), using defaults", e)
        return dict(DEFAULTS)


def save(settings: dict) -> None:
    """
    Save settings to disk. Silently ignores errors - a settings save
    failure should never crash the app.
    """
    try:
        with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2)
        log.debug("Settings saved to %s", SETTINGS_PATH)
    except Exception as e:
        log.warning("Failed to save settings: %s", e)


def get(key: str, fallback=None):
    """Convenience function to read a single setting."""
    return load().get(key, fallback if fallback is not None else DEFAULTS.get(key))


def set(key: str, value) -> None:
    """Convenience function to update a single setting and save."""
    current = load()
    current[key] = value
    save(current)
