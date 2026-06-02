"""
utils/theme.py

All theme definitions and stylesheet generation live here.
AutoTyper.py imports THEMES and build_style from this module.

Architecture decision: keeping themes separate from the UI means you can
add, remove, or tweak themes without touching any application logic.
build_style() is a pure function - same input always gives same output,
easy to test and reason about.
"""

from __future__ import annotations

from config import UIConfig

# --- Theme definitions ---
# Each theme is a dict of color tokens.
# To add a new theme, just add a new entry here - no other file needs changing.
THEMES: dict[str, dict[str, str]] = {
    "Soft Pink": {
        "DARK_BG":       "#fdf6f8",
        "PANEL_BG":      "#f5e6eb",
        "ACCENT":        "#c4677a",
        "ACCENT_DIM":    "#a04f62",
        "TEXT_PRIMARY":  "#3d1a26",
        "TEXT_DIM":      "#a07080",
        "DANGER":        "#b03030",
        "BORDER":        "#e8c4cc",
        "INPUT_BG":      "#ffffff",
    },
    "Dark Mode": {
        "DARK_BG":       "#1a1a1a",
        "PANEL_BG":      "#252525",
        "ACCENT":        "#c084fc",
        "ACCENT_DIM":    "#9b59d0",
        "TEXT_PRIMARY":  "#f0f0f0",
        "TEXT_DIM":      "#888888",
        "DANGER":        "#ff5555",
        "BORDER":        "#3a3a3a",
        "INPUT_BG":      "#2e2e2e",
    },
    "Soft Blue": {
        "DARK_BG":       "#f0f4ff",
        "PANEL_BG":      "#e0eaff",
        "ACCENT":        "#5b7fcf",
        "ACCENT_DIM":    "#3a5db0",
        "TEXT_PRIMARY":  "#1a2540",
        "TEXT_DIM":      "#7090b0",
        "DANGER":        "#b03030",
        "BORDER":        "#b8cff0",
        "INPUT_BG":      "#ffffff",
    },
    "Soft Green": {
        "DARK_BG":       "#f0faf4",
        "PANEL_BG":      "#dff2e8",
        "ACCENT":        "#4a9e72",
        "ACCENT_DIM":    "#2e7a52",
        "TEXT_PRIMARY":  "#1a3028",
        "TEXT_DIM":      "#6a9a80",
        "DANGER":        "#b03030",
        "BORDER":        "#b0dfc0",
        "INPUT_BG":      "#ffffff",
    },
}

# Default theme used on first launch - single source of truth is UIConfig.DEFAULT_THEME
DEFAULT_THEME = UIConfig.DEFAULT_THEME


def build_style(t: dict) -> str:
    """
    Build the full QSS stylesheet string from a theme dict.
    Called by main() on startup and by MainWindow.apply_theme() on theme change.
    """
    return f"""
QMainWindow, QWidget {{
    background-color: {t['DARK_BG']};
    color: {t['TEXT_PRIMARY']};
    font-family: 'Helvetica Neue', 'Arial Rounded MT Bold', sans-serif;
}}
QPushButton {{
    background-color: {t['PANEL_BG']};
    color: {t['ACCENT']};
    border: 1.5px solid {t['ACCENT']};
    border-radius: 20px;
    padding: 8px 22px;
    font-size: 13px;
    font-weight: bold;
}}
QPushButton:hover {{
    background-color: {t['ACCENT']};
    color: white;
}}
QPushButton:disabled {{
    color: {t['TEXT_DIM']};
    border-color: {t['BORDER']};
    background-color: {t['PANEL_BG']};
    border-radius: 20px;
}}
QPushButton#danger {{
    color: {t['ACCENT']};
    border-color: {t['ACCENT']};
    border-radius: 20px;
}}
QPushButton#danger:hover {{
    background-color: {t['ACCENT']};
    color: white;
}}
QPushButton#toggle {{
    border-radius: 0px;
    border: none;
    border-bottom: 2px solid transparent;
    padding: 10px 28px;
    font-size: 14px;
    background-color: transparent;
    color: {t['TEXT_DIM']};
}}
QPushButton#toggle:checked {{
    color: {t['ACCENT']};
    border-bottom: 2px solid {t['ACCENT']};
}}
QTextEdit {{
    background-color: {t['INPUT_BG']};
    color: {t['TEXT_PRIMARY']};
    border: 1.5px solid {t['BORDER']};
    border-radius: 12px;
    padding: 10px;
    font-size: 13px;
    font-family: 'Helvetica Neue', sans-serif;
}}
QLabel {{
    color: {t['TEXT_DIM']};
    font-size: 12px;
}}
QLabel#heading {{
    color: {t['TEXT_PRIMARY']};
    font-size: 15px;
    font-weight: bold;
}}
QLabel#accent {{
    color: {t['ACCENT']};
    font-size: 12px;
    font-weight: bold;
}}
QDoubleSpinBox, QSpinBox {{
    background-color: {t['INPUT_BG']};
    color: {t['TEXT_PRIMARY']};
    border: 1.5px solid {t['BORDER']};
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
    color: {t['TEXT_PRIMARY']};
    font-size: 13px;
    spacing: 8px;
}}
QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border: 1.5px solid {t['ACCENT']};
    border-radius: 8px;
    background-color: {t['INPUT_BG']};
}}
QCheckBox::indicator:checked {{
    background-color: {t['ACCENT']};
}}
QFrame#separator {{
    background-color: {t['BORDER']};
    max-height: 1px;
}}
QScrollArea {{
    border: none;
    background-color: transparent;
}}
QLineEdit {{
    background-color: {t['INPUT_BG']};
    color: {t['TEXT_PRIMARY']};
    border: 1.5px solid {t['BORDER']};
    border-radius: 12px;
    padding: 10px 14px;
    font-size: 13px;
    font-family: 'Helvetica Neue', sans-serif;
}}
QComboBox {{
    background-color: {t['INPUT_BG']};
    color: {t['TEXT_PRIMARY']};
    border: 1.5px solid {t['BORDER']};
    border-radius: 12px;
    padding: 6px 12px;
    font-size: 12px;
}}
QComboBox::drop-down {{
    border: none;
    padding-right: 8px;
}}
QComboBox QAbstractItemView {{
    background-color: {t['INPUT_BG']};
    color: {t['TEXT_PRIMARY']};
    border: 1.5px solid {t['BORDER']};
    selection-background-color: {t['PANEL_BG']};
    selection-color: {t['ACCENT']};
}}
QLabel#helpHeading {{
    color: {t['ACCENT']};
    font-size: 14px;
    font-weight: bold;
    margin-top: 6px;
}}
QLabel#helpBody {{
    color: {t['TEXT_PRIMARY']};
    font-size: 13px;
}}
QLabel#modelDesc {{
    color: {t['TEXT_DIM']};
    font-size: 11px;
    padding-left: 2px;
}}
QLabel#versionLabel {{
    color: {t['TEXT_DIM']};
    font-size: 11px;
}}
"""
