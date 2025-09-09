from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

ThemeName = Literal["dark", "light"]


def _styles_dir() -> Path:
    return Path(__file__).with_suffix("").parent / "styles"


def available_themes() -> list[ThemeName]:
    return ["dark", "light"]


def _load_qss(theme: ThemeName) -> str:
    path = _styles_dir() / f"{theme}.qss"
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""


def _apply_palette(app: QApplication, theme: ThemeName) -> None:
    # Start from Fusion for consistent cross‑platform rendering
    app.setStyle("Fusion")
    pal = QPalette()

    if theme == "dark":
        bg = QColor(17, 18, 23)  # #111217
        base = QColor(22, 24, 31)  # inputs
        alt = QColor(27, 30, 39)
        text = QColor(235, 238, 246)
        sub = QColor(170, 178, 207)
        btn = QColor(39, 43, 56)
        hi = QColor(108, 156, 255)

        cr = QPalette.ColorRole
        cg = QPalette.ColorGroup
        pal.setColor(cr.Window, bg)
        pal.setColor(cr.WindowText, text)
        pal.setColor(cr.Base, base)
        pal.setColor(cr.AlternateBase, alt)
        pal.setColor(cr.ToolTipBase, alt)
        pal.setColor(cr.ToolTipText, text)
        pal.setColor(cr.Text, text)
        pal.setColor(cr.Button, btn)
        pal.setColor(cr.ButtonText, text)
        pal.setColor(cr.BrightText, QColor(255, 107, 107))
        pal.setColor(cr.Highlight, hi)
        pal.setColor(cr.HighlightedText, QColor(0, 0, 0))
        pal.setColor(cg.Disabled, cr.Text, sub)
        pal.setColor(cg.Disabled, cr.ButtonText, sub)
    else:
        bg = QColor(248, 249, 251)
        base = QColor(255, 255, 255)
        alt = QColor(244, 246, 250)
        text = QColor(24, 28, 37)
        sub = QColor(102, 112, 133)
        btn = QColor(255, 255, 255)
        hi = QColor(62, 121, 247)

        cr = QPalette.ColorRole
        cg = QPalette.ColorGroup
        pal.setColor(cr.Window, bg)
        pal.setColor(cr.WindowText, text)
        pal.setColor(cr.Base, base)
        pal.setColor(cr.AlternateBase, alt)
        pal.setColor(cr.ToolTipBase, base)
        pal.setColor(cr.ToolTipText, text)
        pal.setColor(cr.Text, text)
        pal.setColor(cr.Button, btn)
        pal.setColor(cr.ButtonText, text)
        pal.setColor(cr.BrightText, QColor(216, 68, 68))
        pal.setColor(cr.Highlight, hi)
        pal.setColor(cr.HighlightedText, QColor(255, 255, 255))
        pal.setColor(cg.Disabled, cr.Text, sub)
        pal.setColor(cg.Disabled, cr.ButtonText, sub)

    app.setPalette(pal)


def apply_theme(app: QApplication, theme: ThemeName | None = None) -> ThemeName:
    """Apply light/dark theme and return the active theme."""
    name = (theme or os.getenv("HACK_UI_THEME", "dark")).lower()
    if name not in available_themes():
        name = "dark"

    _apply_palette(app, name)  # type: ignore[arg-type]
    qss = _load_qss(name)  # type: ignore[arg-type]
    if qss:
        app.setStyleSheet(qss)
    try:
        app.setProperty("activeTheme", name)
    except Exception:
        pass
    return name  # type: ignore[return-value]


def toggle_theme(app: QApplication, current: ThemeName) -> ThemeName:
    nxt: ThemeName = "light" if current == "dark" else "dark"
    return apply_theme(app, nxt)
