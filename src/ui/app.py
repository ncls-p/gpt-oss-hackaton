from __future__ import annotations

import os
import sys
from typing import Optional

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

from .main_window import MainWindow
from .theme import apply_theme


def _apply_fusion_dark(app: QApplication) -> None:
    app.setStyle("Fusion")
    palette = QPalette()
    # Base colors
    cr = QPalette.ColorRole
    cg = QPalette.ColorGroup
    palette.setColor(cr.Window, QColor(37, 37, 38))
    palette.setColor(cr.WindowText, QColor(255, 255, 255))
    palette.setColor(cr.Base, QColor(30, 30, 30))
    palette.setColor(cr.AlternateBase, QColor(45, 45, 48))
    palette.setColor(cr.ToolTipBase, QColor(255, 255, 255))
    palette.setColor(cr.ToolTipText, QColor(255, 255, 255))
    palette.setColor(cr.Text, QColor(255, 255, 255))
    palette.setColor(cr.Button, QColor(45, 45, 48))
    palette.setColor(cr.ButtonText, QColor(255, 255, 255))
    palette.setColor(cr.BrightText, QColor(255, 0, 0))

    # Highlight
    palette.setColor(cr.Highlight, QColor(14, 99, 156))
    palette.setColor(cr.HighlightedText, QColor(255, 255, 255))

    # Disabled
    palette.setColor(cg.Disabled, cr.Text, QColor(127, 127, 127))
    palette.setColor(cg.Disabled, cr.ButtonText, QColor(127, 127, 127))
    app.setPalette(palette)


def main(argv: Optional[list[str]] = None) -> int:
    argv = argv if argv is not None else sys.argv

    app = QApplication(argv)
    # Apply modern theme (env HACK_UI_THEME can be 'light' or 'dark')
    try:
        apply_theme(app)
    except Exception:
        # Fallback to legacy dark palette
        if os.getenv("HACK_UI_THEME", "dark").lower() != "light":
            _apply_fusion_dark(app)

    win = MainWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
