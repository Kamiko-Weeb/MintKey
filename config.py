"""
config.py

Single source of truth for all hardcoded constants in Mintkey.
Import the relevant class wherever you need a value:

    from config import APIConfig, AppConfig, TypingConfig, UIConfig

Rules:
- This file has NO imports from the rest of the project.
- Runtime values (e.g. platform detection, version.txt) stay in their
  original modules - only true constants live here.
- .env / environment variables are NOT replaced; APIConfig.KEY_ENV just
  names the variable so it's never a stray string literal.
"""


class APIConfig:
    """NVIDIA NIM API connection and request parameters."""

    # REST endpoint for chat completions
    URL = "https://integrate.api.nvidia.com/v1/chat/completions"

    # Name of the environment variable holding the API key (.env must set this)
    KEY_ENV = "NIM_API_KEY"

    # Seconds before a chat request times out
    TIMEOUT = 60

    # Maximum tokens the model may return per response
    MAX_TOKENS = 1024

    # Sampling temperature: 0 = deterministic, 1 = very creative
    TEMPERATURE = 0.7

    # Default system prompt injected at the start of every conversation
    SYSTEM_PROMPT = "You are a helpful assistant."


class AppConfig:
    """Application-level URLs, update checker, and launch behaviour."""

    # Raw URL used to fetch the latest version number from GitHub
    VERSION_CHECK_URL = (
        "https://raw.githubusercontent.com/Kamiko-Weeb/MintKey/main/version.txt"
    )

    # Page opened in the browser when the user accepts an update
    DOWNLOAD_URL = "https://kamiko-weeb.github.io/MintKey"

    # Seconds before the version-check HTTP request times out
    VERSION_CHECK_TIMEOUT = 5

    # Milliseconds to wait after the window is shown before running the
    # update check - gives the UI time to fully paint before hitting the network
    UPDATE_CHECK_DELAY_MS = 2000


class TypingConfig:
    """Typing engine behaviour and default values for all typing controls."""

    # Characters that constitute one "word" - used to convert WPM → char/sec
    CHARS_PER_WORD = 5

    # --- Defaults shown in the UI on first launch ---
    DEFAULT_WPM = 1000.0
    DEFAULT_DELAY = 10          # seconds the user has to switch windows
    DEFAULT_MISTAKE_RATE = 0.0  # 0 = no mistakes, 1 = mistake every char

    # Spinbox step size for the mistake-rate control
    MISTAKE_STEP = 0.05

    # --- Allowed ranges for spinboxes ---
    WPM_MIN = 10
    WPM_MAX = 50_000

    DELAY_MIN = 0
    DELAY_MAX = 60              # seconds

    MISTAKE_RATE_MIN = 0.0
    MISTAKE_RATE_MAX = 1.0

    # Seconds between focus checks while typing is paused (window lost focus)
    FOCUS_POLL_INTERVAL = 0.2

    # --- Humanization timing (applies when max_speed is False) ---
    # These control rhythm variation so the timing pattern looks human, not robotic.

    # Gaussian std-dev as a fraction of the base interval.
    # 0.35 = ±35% jitter — matches natural fast-typist variation.
    TIMING_VARIANCE = 0.35

    # Multiplier applied to the interval on space characters.
    # Humans pause slightly longer at word boundaries.
    WORD_PAUSE_MULT = 2.5

    # Multiplier applied after sentence-ending punctuation (. ! ?).
    # Simulates the natural pause between sentences.
    SENTENCE_PAUSE_MULT = 6.0

    # Per-character probability of inserting a short hesitation pause.
    # Simulates micro-pauses humans make when recalling or reading ahead.
    MICRO_PAUSE_CHANCE = 0.02

    # Maximum duration (seconds) of a micro-pause.
    MICRO_PAUSE_MAX = 0.4


class UIConfig:
    """Window geometry and UI-level defaults (no widgets, pure constants)."""

    # Main application window
    WINDOW_MIN_WIDTH = 680
    WINDOW_MIN_HEIGHT = 620

    # Settings panel (opened via the gear icon)
    SETTINGS_MIN_WIDTH = 420

    # Floating debug terminal
    DEBUG_MIN_WIDTH = 680
    DEBUG_MIN_HEIGHT = 440

    # Minimum pixel height for the text-input area in AutoTyperPanel
    TEXT_INPUT_MIN_HEIGHT = 140

    # Theme applied on first launch and used as fallback when a saved
    # theme name is missing. Must match a key in utils/theme.py THEMES dict.
    DEFAULT_THEME = "Soft Pink"
