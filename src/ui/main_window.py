from __future__ import annotations

import difflib
import html as _html
import json
import textwrap
from pathlib import Path
import os
from typing import Any, List, Optional, cast

from PySide6.QtCore import QObject, Qt, QThread, Signal, Slot
from PySide6.QtGui import QAction, QIcon, QPalette, QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QTextBrowser,
    QTextEdit,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from src.container import container

from .theme import ThemeName, toggle_theme


class ChatInput(QTextEdit):
    sendRequested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAcceptRichText(False)
        self.setPlaceholderText(
            "Type a message…  (Enter to send • Shift+Enter for newline)"
        )
        # Auto-resize between min/max heights
        self._min_h = 48
        self._max_h = 180
        self.setMinimumHeight(self._min_h)
        self.setMaximumHeight(self._max_h)
        try:
            self.document().contentsChanged.connect(self._auto_resize)
        except Exception:
            pass

    def keyPressEvent(self, event) -> None:  # type: ignore[override]
        try:
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                    # Insert newline
                    return super().keyPressEvent(event)
                # Submit
                self.sendRequested.emit()
                return
        except Exception:
            pass
        return super().keyPressEvent(event)

    def _auto_resize(self) -> None:
        try:
            doc_h = int(self.document().size().height()) + 10
            new_h = max(self._min_h, min(self._max_h, doc_h))
            if new_h != self.height():
                self.setFixedHeight(new_h)
        except Exception:
            pass


class _ChatWorker(QObject):
    started = Signal()
    finished = Signal(dict)
    error = Signal(str)
    step = Signal(dict)

    def __init__(
        self,
        messages: Optional[List[dict]],
        user_text: str,
        system_message: Optional[str],
        temperature: float,
        max_tokens: int,
        tool_max_steps: int,
        require_final_tool: bool,
        allow_exec_custom: bool = False,
    ) -> None:
        super().__init__()
        self.messages = messages or []
        self.user_text = user_text
        self.system_message = system_message
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.tool_max_steps = tool_max_steps
        self.require_final_tool = require_final_tool
        self.allow_exec_custom = bool(allow_exec_custom)
        # Cooperative cancellation flag
        try:
            from threading import Event

            self._cancel_event = Event()
        except Exception:
            self._cancel_event = None  # type: ignore[assignment]

    def request_cancel(self) -> None:
        try:
            if self._cancel_event is not None:
                self._cancel_event.set()
        except Exception:
            pass

    @Slot()
    def run(self) -> None:
        self.started.emit()
        try:
            from src.adapters.llm.openai_tools_adapter import OpenAIToolsAdapter

            llm_tools = container.get_llm_tools_adapter()
            if not isinstance(llm_tools, OpenAIToolsAdapter):
                raise RuntimeError("Tools-enabled LLM adapter is not available")

            def _emit_step(ev: dict) -> None:
                try:
                    self.step.emit(ev)
                except Exception:
                    pass

            def _confirm_tool(name: str, arguments: dict[str, Any]):
                try:
                    if name == "system.exec_custom" and not self.allow_exec_custom:
                        # Intercept and deny for safety
                        payload = {
                            "status": "denied",
                            "message": "system.exec_custom is disabled in UI (Allow exec_custom unchecked)",
                        }
                        import json as _json

                        return {"handled": True, "result": _json.dumps(payload, ensure_ascii=False)}
                except Exception:
                    pass
                # Approve all other tools by default
                return True

            result = llm_tools.run_chat_turn_with_trace(
                messages=self.messages,
                user_text=self.user_text,
                system_message=self.system_message,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                tool_max_steps=self.tool_max_steps,
                require_final_tool=self.require_final_tool,
                on_step=_emit_step,
                confirm_tool=_confirm_tool,
                should_cancel=(
                    self._cancel_event.is_set if self._cancel_event else None
                ),
            )
            self.finished.emit(result)
        except Exception as e:  # pragma: no cover
            self.error.emit(str(e))


ASSETS_DIR = Path(__file__).with_name("assets") / "icons"


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("GPT OSS Hackathon — Tools Chat UI")
        self.setMinimumSize(950, 600)

        self._build_actions()
        self._build_toolbar()
        self._build_layout()
        # Chat state
        self._chat_history: List[dict[str, Any]] = []
        self._last_final_raw: str = ""
        self._last_steps: List[dict[str, Any]] = []
        self._live_steps: List[dict[str, Any]] = []
        try:
            app = QApplication.instance()
            prop = app.property("activeTheme") if app else None  # type: ignore[attr-defined]
            if isinstance(prop, str) and prop in ("dark", "light"):
                self._theme = prop  # type: ignore[assignment]
            else:
                win_col = self.palette().color(QPalette.ColorRole.Window)
                self._theme = "dark" if win_col.lightness() < 128 else "light"  # type: ignore[assignment]
        except Exception:
            self._theme = "dark"  # type: ignore[assignment]

    # UI building
    def _build_actions(self) -> None:
        send_icon = QIcon(str(ASSETS_DIR / "send.svg"))
        save_icon = QIcon(str(ASSETS_DIR / "save.svg"))
        clear_icon = QIcon(str(ASSETS_DIR / "clear.svg"))
        stop_icon = QIcon(str(ASSETS_DIR / "stop.svg"))

        self.action_run = QAction(send_icon, "Send", self)
        self.action_run.triggered.connect(self._on_send_clicked)

        self.action_save = QAction(save_icon, "Save Conversation…", self)
        self.action_save.triggered.connect(self._on_save_clicked)

        self.action_clear = QAction(clear_icon, "Clear", self)
        self.action_clear.triggered.connect(self._on_clear_clicked)

        self.action_toggle_theme = QAction("Toggle Theme", self)
        self.action_toggle_theme.triggered.connect(self._on_toggle_theme)

        self.action_stop = QAction(stop_icon, "Stop", self)
        self.action_stop.triggered.connect(self._on_cancel_clicked)
        self.action_stop.setEnabled(False)

    def _build_toolbar(self) -> None:
        tb = QToolBar("Main", self)
        tb.setMovable(False)
        tb.addAction(self.action_run)
        tb.addAction(self.action_save)
        tb.addAction(self.action_stop)
        tb.addAction(self.action_clear)
        tb.addSeparator()
        tb.addAction(self.action_toggle_theme)
        self.addToolBar(tb)

    def _build_layout(self) -> None:
        central = QWidget(self)
        self.setCentralWidget(central)

        splitter = QSplitter(Qt.Orientation.Horizontal, central)

        # Left: Settings
        left = QWidget(splitter)
        left.setObjectName("sidePanel")
        form = QFormLayout(left)
        form.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        try:
            form.setHorizontalSpacing(12)
            form.setVerticalSpacing(10)
        except Exception:
            pass
        form.setContentsMargins(12, 12, 12, 12)

        self.system_edit = QLineEdit(left)
        self.system_edit.setPlaceholderText("You are a computer assistant… (optional)")

        self.temp_spin = QDoubleSpinBox(left)
        self.temp_spin.setDecimals(2)
        self.temp_spin.setRange(0.0, 2.0)
        self.temp_spin.setSingleStep(0.1)
        self.temp_spin.setValue(0.7)

        self.max_tokens_spin = QSpinBox(left)
        self.max_tokens_spin.setRange(16, 32000)
        self.max_tokens_spin.setValue(800)

        self.steps_spin = QSpinBox(left)
        self.steps_spin.setRange(1, 10)
        self.steps_spin.setValue(4)

        self.final_required_chk = QCheckBox("Require assistant.final to end", left)
        self.final_required_chk.setChecked(False)

        self.allow_exec_custom_chk = QCheckBox("Allow exec_custom (run custom commands)", left)
        self.allow_exec_custom_chk.setChecked(False)

        self.workspace_safety_chk = QCheckBox("Enforce workspace safety (restrict file ops to WORKSPACE_ROOT)", left)
        self.workspace_safety_chk.setChecked(False)
        try:
            self.workspace_safety_chk.stateChanged.connect(self._on_toggle_workspace_safety)
        except Exception:
            pass

        run_btn = QPushButton("Send", left)
        run_btn.setObjectName("primary")
        try:
            run_btn.setIcon(QIcon(str(ASSETS_DIR / "send.svg")))
        except Exception:
            pass
        run_btn.clicked.connect(self._on_send_clicked)

        self.progress = QProgressBar(left)
        self.progress.setRange(0, 0)
        self.progress.setVisible(False)

        form.addRow(QLabel("System:"), self.system_edit)
        form.addRow(QLabel("Temperature:"), self.temp_spin)
        form.addRow(QLabel("Max tokens:"), self.max_tokens_spin)
        form.addRow(QLabel("Tool steps:"), self.steps_spin)
        form.addRow(self.final_required_chk)
        form.addRow(self.allow_exec_custom_chk)
        form.addRow(self.workspace_safety_chk)
        form.addRow(run_btn)
        form.addRow(self.progress)

        # Right: Chat + Steps
        right = QWidget(splitter)
        right_vlayout = QVBoxLayout(right)

        # Vertical splitter to allow resizing chat vs steps
        right_splitter = QSplitter(Qt.Orientation.Vertical, right)

        # Top: Chat area
        chat_area = QWidget(right_splitter)
        chat_area.setObjectName("card")
        chat_layout = QVBoxLayout(chat_area)
        chat_layout.setContentsMargins(12, 12, 12, 12)
        self.chat_view = QTextBrowser(chat_area)
        self.chat_view.setOpenExternalLinks(True)
        self.chat_view.setReadOnly(True)
        self.chat_view.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )

        # input row
        input_row = QHBoxLayout()
        self.input_edit = ChatInput(chat_area)
        self.input_edit.setObjectName("chatInput")
        self.input_edit.sendRequested.connect(self._on_send_clicked)
        self.send_btn = QPushButton("Send", chat_area)
        self.send_btn.setObjectName("primary")
        try:
            self.send_btn.setIcon(QIcon(str(ASSETS_DIR / "send.svg")))
        except Exception:
            pass
        self.send_btn.clicked.connect(self._on_send_clicked)
        self.stop_btn = QPushButton("Stop", chat_area)
        try:
            self.stop_btn.setIcon(QIcon(str(ASSETS_DIR / "stop.svg")))
        except Exception:
            pass
        self.stop_btn.clicked.connect(self._on_cancel_clicked)
        self.stop_btn.setEnabled(False)
        input_row.addWidget(self.input_edit)
        input_row.addWidget(self.send_btn)
        input_row.addWidget(self.stop_btn)

        title_lbl = QLabel("Conversation")
        title_lbl.setStyleSheet(
            "font-weight: 600; font-size: 13.5pt; margin-bottom: 2px;"
        )
        chat_layout.addWidget(title_lbl)
        chat_layout.addWidget(self.chat_view)
        chat_layout.addLayout(input_row)

        # Bottom: Steps area
        steps_area = QWidget(right_splitter)
        steps_area.setObjectName("card")
        steps_layout = QVBoxLayout(steps_area)
        steps_layout.setContentsMargins(12, 12, 12, 12)
        self.steps_list = QListWidget(steps_area)
        self.steps_list.itemDoubleClicked.connect(self._show_step_details)

        steps_title = QLabel("Tool Steps (double-click for details)")
        steps_title.setStyleSheet(
            "font-weight: 600; font-size: 12.5pt; margin-bottom: 2px;"
        )
        steps_layout.addWidget(steps_title)
        steps_layout.addWidget(self.steps_list)

        right_splitter.addWidget(chat_area)
        right_splitter.addWidget(steps_area)
        right_splitter.setStretchFactor(0, 3)
        right_splitter.setStretchFactor(1, 2)
        right_vlayout.addWidget(right_splitter)

        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)

        outer = QHBoxLayout(central)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(12)
        outer.addWidget(splitter)

        # Apply initial workspace safety env based on checkbox (default unchecked -> disabled)
        try:
            self._on_toggle_workspace_safety()
        except Exception:
            pass

    # Slots
    @Slot()
    def _on_toggle_theme(self) -> None:
        app = QApplication.instance()
        if app is None:
            return
        # Ensure type for static checkers
        app_qt = cast(QApplication, app)
        try:
            current_prop = app_qt.property("activeTheme")
            current: ThemeName
            if isinstance(current_prop, str) and current_prop in ("dark", "light"):
                current = current_prop
            else:
                current = self._theme if self._theme in ("dark", "light") else "dark"
            new_theme = toggle_theme(app_qt, current)
            self._theme = new_theme
        except Exception:
            pass

    @Slot()
    def _on_send_clicked(self) -> None:
        user_text = self.input_edit.toPlainText().strip()
        if not user_text:
            QMessageBox.warning(self, "Missing message", "Please type a message first.")
            return

        system = self.system_edit.text().strip() or None
        temp = float(self.temp_spin.value())
        max_tokens = int(self.max_tokens_spin.value())
        steps = int(self.steps_spin.value())
        final_required = bool(self.final_required_chk.isChecked())

        # Clear input and show progress; history will update after backend turn
        self.input_edit.clear()

        # Threaded worker
        self.progress.setVisible(True)
        # disable input while running
        try:
            self.input_edit.setEnabled(False)
            self.send_btn.setEnabled(False)
            self.stop_btn.setEnabled(True)
            self.action_stop.setEnabled(True)
        except Exception:
            pass
        self.steps_list.clear()
        self._live_steps = []

        self._thread = QThread(self)
        # pass a shallow copy of history to the worker
        messages_copy: List[dict] = list(self._chat_history)
        self._worker = _ChatWorker(
            messages_copy,
            user_text,
            system,
            temp,
            max_tokens,
            steps,
            final_required,
            allow_exec_custom=bool(self.allow_exec_custom_chk.isChecked()),
        )
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_chat_finished)
        self._worker.error.connect(self._on_chat_error)
        self._worker.step.connect(self._on_step_event)
        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)

        self._thread.start()

    @Slot()
    def _on_cancel_clicked(self) -> None:
        # Request cooperative cancel on running worker
        w = getattr(self, "_worker", None)
        if w is None:
            return
        try:
            w.request_cancel()
        except Exception:
            pass
        # UI feedback for stopping
        try:
            self.action_stop.setEnabled(False)
            self.stop_btn.setEnabled(False)
        except Exception:
            pass

    @Slot(dict)
    def _on_chat_finished(self, result: dict) -> None:
        self.progress.setVisible(False)
        try:
            self.input_edit.setEnabled(True)
            self.send_btn.setEnabled(True)
            self.input_edit.setFocus()
            self.stop_btn.setEnabled(False)
            self.action_stop.setEnabled(False)
        except Exception:
            pass
        # Update history from backend
        self._chat_history = list(result.get("messages", []) or [])
        text_raw = str(result.get("text", ""))
        self._last_final_raw = text_raw
        self._render_conversation()

        # If we didn't receive live steps (no tools used), render the result steps once
        steps = result.get("steps", []) or []
        self._last_steps = steps
        if not getattr(self, "_live_steps", None) and steps:
            for idx, step in enumerate(steps, start=1):
                name = step.get("name") or "?"
                res = step.get("result") or ""
                snippet = textwrap.shorten(str(res).replace("\n", " "), width=120)
                item = QListWidgetItem(f"{idx}. {name} — {snippet}")
                item.setData(Qt.ItemDataRole.UserRole, step)
                self.steps_list.addItem(item)

    @Slot(str)
    def _on_chat_error(self, message: str) -> None:  # pragma: no cover
        self.progress.setVisible(False)
        try:
            self.input_edit.setEnabled(True)
            self.send_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
            self.action_stop.setEnabled(False)
        except Exception:
            pass
        QMessageBox.critical(self, "Chat error", message)

    @Slot(QListWidgetItem)
    def _show_step_details(self, item: QListWidgetItem) -> None:
        step = item.data(Qt.ItemDataRole.UserRole) or {}
        pretty = json.dumps(step, ensure_ascii=False, indent=2)
        dlg = QMessageBox(self)
        dlg.setWindowTitle("Step details")
        dlg.setIcon(QMessageBox.Icon.Information)
        dlg.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
            | Qt.TextInteractionFlag.TextSelectableByKeyboard
        )
        dlg.setText(pretty)
        dlg.exec()

    @Slot()
    def _on_save_clicked(self) -> None:
        # Save the full conversation and last steps
        if not self._chat_history and self.steps_list.count() == 0:
            QMessageBox.information(
                self, "Nothing to save", "Start a conversation first."
            )
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Save conversation", filter="JSON (*.json)"
        )
        if not path:
            return
        steps = []
        for i in range(self.steps_list.count()):
            steps.append(self.steps_list.item(i).data(Qt.ItemDataRole.UserRole))
        with open(path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "conversation": self._chat_history,
                    "last_text": self._last_final_raw,
                    "last_steps": steps,
                },
                f,
                ensure_ascii=False,
                indent=2,
            )

    @Slot()
    def _on_clear_clicked(self) -> None:
        self.chat_view.clear()
        self.steps_list.clear()
        self._chat_history.clear()
        self._last_final_raw = ""
        self._last_steps = []
        self._live_steps = []

    # Helpers
    def _render_conversation(self) -> None:
        # Rebuild the conversation view using chat bubbles (assistant left, user right)
        blocks: list[tuple[str, str]] = []  # (speaker, content)

        def _norm(s: str) -> str:
            try:
                return " ".join(s.strip().split()).lower()
            except Exception:
                return s.strip().lower()

        for m in self._chat_history:
            role = str(m.get("role", ""))
            if role not in ("user", "assistant"):
                continue
            content = str(m.get("content", ""))
            # Skip assistant interim messages that only carry tool_calls metadata
            if role == "assistant" and m.get("tool_calls"):
                continue

            # Compact special JSON notices (like tool_call_error)
            try:
                obj = json.loads(content)
                if isinstance(obj, dict) and obj.get("notice") == "tool_call_error":
                    err = str(obj.get("error") or "Tool call error")
                    tools = obj.get("available_tools") or []
                    names = []
                    if isinstance(tools, list):
                        for t in tools:
                            try:
                                name = t.get("name")
                                if isinstance(name, str):
                                    names.append(name)
                            except Exception:
                                pass
                    tools_str = (" — tools: " + ", ".join(names)) if names else ""
                    disp = f"Tool error: {err}{tools_str}"
                else:
                    disp = self._extract_display_text(content)
            except Exception:
                disp = self._extract_display_text(content)

            speaker = "You" if role == "user" else "Assistant"

            # Merge near-duplicate consecutive assistant messages by replacement
            if blocks and speaker == "Assistant":
                last_speaker, last_text = blocks[-1]
                if last_speaker == "Assistant":
                    a, b = _norm(last_text), _norm(disp)
                    same = (
                        a == b
                        or (a in b and len(a) / max(len(b), 1) >= 0.75)
                        or (b in a and len(b) / max(len(a), 1) >= 0.75)
                    )
                    if not same:
                        try:
                            ratio = difflib.SequenceMatcher(None, a, b).ratio()
                            same = ratio >= 0.90
                        except Exception:
                            same = False
                    if same:
                        blocks[-1] = (speaker, disp)
                        continue

            blocks.append((speaker, disp))

        # Build themed CSS for bubbles
        theme = getattr(self, "_theme", "dark")
        if theme not in ("dark", "light"):
            theme = "dark"
        if theme == "dark":
            bg_assist = "#1B1E27"
            border_assist = "#272C3A"
            text_assist = "#D8DEEC"
            bg_user = "#6C9CFF"
            text_user = "#0B0F1A"
            time_col = "#AAB2CF"
            page_bg = "transparent"
            pre_bg = "#0F1117"
            pre_border = "#272C3A"
        else:
            bg_assist = "#FFFFFF"
            border_assist = "#E5E9F2"
            text_assist = "#2D3340"
            bg_user = "#3E79F7"
            text_user = "#FFFFFF"
            time_col = "#667085"
            page_bg = "transparent"
            pre_bg = "#F4F6FA"
            pre_border = "#E5E9F2"

        css = f"""
        .chat {{
          background: {page_bg};
          font-size: 12.5pt;
          line-height: 1.35;
        }}
        .row {{ display: flex; margin: 8px 0; }}
        .left {{ justify-content: flex-start; }}
        .right {{ justify-content: flex-end; }}
        .bubble {{
          max-width: 78%;
          padding: 10px 12px;
          border-radius: 14px;
          /* Robust wrapping even when there are long tokens or NBSP */
          white-space: pre-wrap;
          word-wrap: break-word;           /* legacy */
          overflow-wrap: anywhere;         /* modern */
          word-break: break-word;          /* best-effort for Qt rich text */
        }}
        .bubble ul, .bubble ol {{ white-space: normal; margin: 8px 0 8px 24px; overflow-wrap: anywhere; word-break: break-word; }}
        .assistant {{ background: {bg_assist}; color: {text_assist}; border: 1px solid {border_assist}; }}
        .user {{ background: {bg_user}; color: {text_user}; border: 0; }}
        .label {{ font-size: 10pt; opacity: 0.75; margin-bottom: 4px; color: {time_col}; }}
        a {{ color: inherit; text-decoration: underline; }}
        code {{ background: {pre_bg}; padding: 2px 4px; border-radius: 6px; border: 1px solid {pre_border}; white-space: pre-wrap; overflow-wrap: anywhere; word-break: break-word; }}
        pre {{ background: {pre_bg}; padding: 10px; border-radius: 10px; overflow-x: auto; border: 1px solid {pre_border}; }}
        """

        def _build_anchor(label: str, url: str) -> str:
            try:
                safe_label = _html.escape(label)
                # only allow http/https links
                href = url.strip()
                if not (href.startswith("http://") or href.startswith("https://")):
                    return safe_label
                safe_href = _html.escape(href, quote=True)
                return f'<a href="{safe_href}">{safe_label}</a>'
            except Exception:
                return _html.escape(label)

        def _markdown_to_html(text: str) -> str:
            # Lightweight, safe-ish Markdown: code blocks, inline code, links, bold/italic, simple lists
            s = text or ""
            # Convert non-breaking spaces to regular spaces so wrapping works
            try:
                s = s.replace("\u00A0", " ")
            except Exception:
                pass
            # Normalize newlines
            s = s.replace("\r\n", "\n").replace("\r", "\n")
            import re

            code_pat = re.compile(r"```([A-Za-z0-9_+-]+)?\n(.*?)\n```", re.DOTALL)
            placeholders: list[str] = []

            def _add_placeholder(html: str) -> str:
                key = f"[[[[BLOCK_{len(placeholders)}]]]]"
                placeholders.append(html)
                return key

            # Extract fenced code blocks
            out_parts: list[str] = []
            pos = 0
            for m in code_pat.finditer(s):
                out_parts.append(s[pos : m.start()])
                lang = (m.group(1) or "").strip()
                code = m.group(2)
                code_esc = _html.escape(code)
                lang_cls = f" lang-{_html.escape(lang)}" if lang else ""
                html_cb = (
                    f'<pre><code class="{lang_cls.strip()}">{code_esc}</code></pre>'
                )
                out_parts.append(_add_placeholder(html_cb))
                pos = m.end()
            out_parts.append(s[pos:])
            s_no_code = "".join(out_parts)

            # Convert links in non-code text to placeholders
            link_pat = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")

            def _link_repl(m: re.Match) -> str:
                return _add_placeholder(_build_anchor(m.group(1), m.group(2)))

            s_no_code_links = link_pat.sub(_link_repl, s_no_code)

            # Escape the remainder
            safe = _html.escape(s_no_code_links)

            # Inline code `...`
            safe = re.sub(r"`([^`]+)`", lambda m: f"<code>{m.group(1)}</code>", safe)

            # Bold and italic (very simple, non-nested)
            safe = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", safe)
            safe = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", safe)

            # Simple lists: lines starting with - or * or 1. 2. ...
            def _lists_to_html(block: str) -> str:
                lines = block.split("\n")
                res: list[str] = []
                i = 0
                bullet_re = re.compile(r"^\s*[-*]\s+(.*)")
                num_re = re.compile(r"^\s*\d+[.)]\s+(.*)")
                while i < len(lines):
                    line = lines[i]
                    m1 = bullet_re.match(line)
                    m2 = num_re.match(line)
                    if m1:
                        items: list[str] = []
                        while i < len(lines):
                            mm = bullet_re.match(lines[i])
                            if not mm:
                                break
                            items.append(f"<li>{mm.group(1)}</li>")
                            i += 1
                        res.append("<ul>" + "".join(items) + "</ul>")
                        continue
                    if m2:
                        items = []
                        while i < len(lines):
                            mm = num_re.match(lines[i])
                            if not mm:
                                break
                            items.append(f"<li>{mm.group(1)}</li>")
                            i += 1
                        res.append("<ol>" + "".join(items) + "</ol>")
                        continue
                    # normal line
                    res.append(line)
                    i += 1
                return "\n".join(res)

            safe = _lists_to_html(safe)

            # Convert remaining newlines to <br>
            safe = safe.replace("\n", "<br>")

            # Re-insert placeholders
            for idx, html in enumerate(placeholders):
                safe = safe.replace(f"[[[[BLOCK_{idx}]]]]", html)
            return safe

        parts: list[str] = [f"<style>{css}</style>", '<div class="chat">']
        for speaker, tx in blocks:
            cls = "right user" if speaker == "You" else "left assistant"
            bubble_cls = "bubble user" if speaker == "You" else "bubble assistant"
            label = "You" if speaker == "You" else "Assistant"
            align = "flex-end" if speaker == "You" else "flex-start"
            parts.append(
                f'<div class="row {cls}"><div style="display:flex;flex-direction:column;align-items:{align};">'
                f'<div class="label">{_html.escape(label)}</div>'
                f'<div class="{bubble_cls}">{_markdown_to_html(tx)}</div>'
                f"</div></div>"
            )
        parts.append("</div>")
        html_doc = "".join(parts)

        try:
            self.chat_view.setHtml(html_doc)
        except Exception:
            # Fallback to plain text if HTML not supported
            self.chat_view.setPlainText(
                "\n\n".join(f"{sp}:\n{tx}" for sp, tx in blocks)
            )
        # Auto-scroll to bottom on new content
        try:
            cursor = self.chat_view.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            self.chat_view.setTextCursor(cursor)
            self.chat_view.ensureCursorVisible()
        except Exception:
            pass

    @Slot(dict)
    def _on_step_event(self, ev: dict) -> None:
        # Live update of tool usage
        self._live_steps = getattr(self, "_live_steps", [])
        phase = str(ev.get("phase") or "")
        name = str(ev.get("name") or "?")
        if phase == "call":
            args = ev.get("arguments")
            snippet = textwrap.shorten(str(args), width=120)
            label = f"▶ {name} {snippet}"
            step = {"name": name, "arguments": args, "result": None}
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, step)
            self.steps_list.addItem(item)
            try:
                self.steps_list.scrollToBottom()
            except Exception:
                pass
            self._live_steps.append(step)
        elif phase == "result":
            res = ev.get("result")
            snippet = textwrap.shorten(str(res).replace("\n", " "), width=120)
            label = f"✓ {name} — {snippet}"
            step = {"name": name, "arguments": None, "result": res}
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, step)
            self.steps_list.addItem(item)
            try:
                self.steps_list.scrollToBottom()
            except Exception:
                pass
            self._live_steps.append(step)
        elif phase == "error":
            err = ev.get("error")
            snippet = textwrap.shorten(str(err).replace("\n", " "), width=120)
            label = f"⚠ tool error — {snippet}"
            step = {"name": "error", "arguments": None, "result": str(err)}
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, step)
            self.steps_list.addItem(item)
            try:
                self.steps_list.scrollToBottom()
            except Exception:
                pass
            self._live_steps.append(step)

    def _extract_display_text(self, text: str) -> str:
        # If backend returned a JSON object as string, extract a useful field
        s = text or ""
        try:
            obj = json.loads(s)
            if isinstance(obj, dict):
                for key in ("final_text", "text", "content", "message"):
                    val = obj.get(key)
                    if isinstance(val, str) and val.strip():
                        return val
                # If nothing obvious, pretty‑print JSON minimally
                return json.dumps(obj, ensure_ascii=False)
        except Exception:
            pass
        return s

    # --- Quick System Controls handlers ---
    def _append_assistant_text(self, text: str) -> None:
        try:
            self._chat_history.append({"role": "assistant", "content": text})
            self._render_conversation()
        except Exception:
            pass

    def _post_tool_result(self, name: str, arguments: dict, result: str) -> None:
        try:
            step = {"name": name, "arguments": arguments, "result": result}
            try:
                snippet_src = " ".join(result.splitlines())
            except Exception:
                snippet_src = str(result)
            snippet = textwrap.shorten(snippet_src, width=120)
            item = QListWidgetItem(f"✓ {name} — {snippet}")
            item.setData(Qt.ItemDataRole.UserRole, step)
            self.steps_list.addItem(item)
            self.steps_list.scrollToBottom()
        except Exception:
            pass
        # Also echo to chat for visibility
        try:
            pretty = result
            try:
                obj = json.loads(result)
                pretty = json.dumps(obj, ensure_ascii=False, indent=2)
            except Exception:
                pass
            self._append_assistant_text(f"```")
            self._append_assistant_text(pretty)
            self._append_assistant_text(f"```")
        except Exception:
            pass

    def _sys_handler(self):
        # Lazy import to avoid UI import costs
        from src.use_cases.tools.system_tools import SystemToolsHandler

        if not hasattr(self, "_sys_tools_handler"):
            try:
                self._sys_tools_handler = SystemToolsHandler()
            except Exception:
                self._sys_tools_handler = None
        return getattr(self, "_sys_tools_handler", None)

    @Slot()
    def _on_toggle_workspace_safety(self) -> None:
        try:
            enforced = bool(self.workspace_safety_chk.isChecked())
        except Exception:
            enforced = False
        try:
            os.environ["HACK_WORKSPACE_ENFORCE"] = "1" if enforced else "0"
        except Exception:
            pass

    @Slot()
    def _on_sys_set_volume(self) -> None:
        h = self._sys_handler()
        if not h:
            return
        level = int(getattr(self, "vol_slider", None).value()) if hasattr(self, "vol_slider") else 50
        try:
            res = h.dispatch("system.set_volume", {"level": level})
            self._post_tool_result("system.set_volume", {"level": level}, str(res))
        except Exception as e:
            QMessageBox.critical(self, "Volume", str(e))

    @Slot()
    def _on_sys_set_brightness(self) -> None:
        h = self._sys_handler()
        if not h:
            return
        level = float(getattr(self, "brightness_spin", None).value()) if hasattr(self, "brightness_spin") else 0.5
        try:
            res = h.dispatch("system.set_brightness", {"level": level})
            self._post_tool_result("system.set_brightness", {"level": level}, str(res))
        except Exception as e:
            QMessageBox.critical(self, "Brightness", str(e))

    @Slot()
    def _on_sys_set_idle(self) -> None:
        h = self._sys_handler()
        if not h:
            return
        try:
            enable = bool(self.idle_enable_chk.isChecked())
            timeout = int(self.idle_timeout_spin.value())
        except Exception:
            enable, timeout = False, 300
        try:
            res = h.dispatch("system.set_idle", {"enable": enable, "timeout": timeout})
            self._post_tool_result("system.set_idle", {"enable": enable, "timeout": timeout}, str(res))
        except Exception as e:
            QMessageBox.critical(self, "Idle/Sleep", str(e))

    @Slot()
    def _on_sys_network_info(self) -> None:
        h = self._sys_handler()
        if not h:
            return
        try:
            res = h.dispatch("system.network_info", {})
            self._post_tool_result("system.network_info", {}, str(res))
        except Exception as e:
            QMessageBox.critical(self, "Network Info", str(e))

    @Slot()
    def _on_sys_battery_info(self) -> None:
        h = self._sys_handler()
        if not h:
            return
        try:
            res = h.dispatch("system.battery_info", {})
            self._post_tool_result("system.battery_info", {}, str(res))
        except Exception as e:
            QMessageBox.critical(self, "Battery Info", str(e))

    @Slot()
    def _on_sys_process_list(self) -> None:
        h = self._sys_handler()
        if not h:
            return
        try:
            limit = int(self.proc_limit_spin.value()) if hasattr(self, "proc_limit_spin") else 10
        except Exception:
            limit = 10
        try:
            res = h.dispatch("system.process_list", {"limit": limit})
            self._post_tool_result("system.process_list", {"limit": limit}, str(res))
        except Exception as e:
            QMessageBox.critical(self, "Processes", str(e))
