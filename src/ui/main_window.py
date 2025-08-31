from __future__ import annotations

import json
import textwrap
from typing import Optional, Any, List

from PySide6.QtCore import QObject, Qt, QThread, Signal, Slot
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTextBrowser,
    QToolBar,
    QWidget,
)

from src.container import container


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
    ) -> None:
        super().__init__()
        self.messages = messages or []
        self.user_text = user_text
        self.system_message = system_message
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.tool_max_steps = tool_max_steps
        self.require_final_tool = require_final_tool

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

            result = llm_tools.run_chat_turn_with_trace(
                messages=self.messages,
                user_text=self.user_text,
                system_message=self.system_message,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                tool_max_steps=self.tool_max_steps,
                require_final_tool=self.require_final_tool,
                on_step=_emit_step,
            )
            self.finished.emit(result)
        except Exception as e:  # pragma: no cover
            self.error.emit(str(e))


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

    # UI building
    def _build_actions(self) -> None:
        self.action_run = QAction(QIcon(), "Send", self)
        self.action_run.triggered.connect(self._on_send_clicked)

        self.action_save = QAction(QIcon(), "Save Conversation…", self)
        self.action_save.triggered.connect(self._on_save_clicked)

        self.action_clear = QAction(QIcon(), "Clear", self)
        self.action_clear.triggered.connect(self._on_clear_clicked)

    def _build_toolbar(self) -> None:
        tb = QToolBar("Main", self)
        tb.setMovable(False)
        tb.addAction(self.action_run)
        tb.addAction(self.action_save)
        tb.addAction(self.action_clear)
        self.addToolBar(tb)

    def _build_layout(self) -> None:
        central = QWidget(self)
        self.setCentralWidget(central)

        splitter = QSplitter(Qt.Orientation.Horizontal, central)

        # Left: Settings
        left = QWidget(splitter)
        form = QFormLayout(left)

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
        self.final_required_chk.setChecked(True)

        run_btn = QPushButton("Send", left)
        run_btn.clicked.connect(self._on_send_clicked)

        self.progress = QProgressBar(left)
        self.progress.setRange(0, 0)
        self.progress.setVisible(False)

        form.addRow(QLabel("System:"), self.system_edit)
        form.addRow(QLabel("Temperature:"), self.temp_spin)
        form.addRow(QLabel("Max tokens:"), self.max_tokens_spin)
        form.addRow(QLabel("Tool steps:"), self.steps_spin)
        form.addRow(self.final_required_chk)
        form.addRow(run_btn)
        form.addRow(self.progress)

        # Right: Chat + Steps
        right = QWidget(splitter)
        right_layout = QGridLayout(right)
        self.chat_view = QTextBrowser(right)
        self.chat_view.setOpenExternalLinks(True)

        # input row
        input_row = QHBoxLayout()
        self.input_edit = QLineEdit(right)
        self.input_edit.setPlaceholderText("Type a message…")
        try:
            # Send on Enter
            self.input_edit.returnPressed.connect(self._on_send_clicked)
        except Exception:
            pass
        send_btn = QPushButton("Send", right)
        send_btn.clicked.connect(self._on_send_clicked)
        input_row.addWidget(self.input_edit)
        input_row.addWidget(send_btn)

        self.steps_list = QListWidget(right)
        self.steps_list.itemDoubleClicked.connect(self._show_step_details)

        right_layout.addWidget(QLabel("Conversation"), 0, 0)
        right_layout.addWidget(self.chat_view, 1, 0)
        right_layout.addLayout(input_row, 2, 0)
        right_layout.addWidget(QLabel("Tool Steps (double-click for details)"), 3, 0)
        right_layout.addWidget(self.steps_list, 4, 0)

        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)

        outer = QHBoxLayout(central)
        outer.addWidget(splitter)

    # Slots
    @Slot()
    def _on_send_clicked(self) -> None:
        user_text = self.input_edit.text().strip()
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
        self.steps_list.clear()
        self._live_steps = []

        self._thread = QThread(self)
        # pass a shallow copy of history to the worker
        messages_copy: List[dict] = list(self._chat_history)
        self._worker = _ChatWorker(
            messages_copy, user_text, system, temp, max_tokens, steps, final_required
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

    @Slot(dict)
    def _on_chat_finished(self, result: dict) -> None:
        self.progress.setVisible(False)
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
            QMessageBox.information(self, "Nothing to save", "Start a conversation first.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Save conversation", filter="JSON (*.json)")
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
        # Rebuild the conversation view using Markdown
        chunks: list[str] = []
        last_rendered: str | None = None
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
                    disp = f"_Tool error_: {err}{tools_str}"
                else:
                    disp = self._extract_display_text(content)
            except Exception:
                disp = self._extract_display_text(content)

            speaker = "You" if role == "user" else "Assistant"
            block = f"**{speaker}:**\n\n{disp}".strip()
            # Deduplicate consecutive identical blocks
            if last_rendered is not None and block == last_rendered:
                continue
            chunks.append(block)
            last_rendered = block
        md = "\n\n".join(chunks) if chunks else ""
        try:
            self.chat_view.setMarkdown(md)
        except Exception:
            # Fallback to plain text if Markdown not supported
            self.chat_view.setPlainText(md)

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
            self._live_steps.append(step)
        elif phase == "result":
            res = ev.get("result")
            snippet = textwrap.shorten(str(res).replace("\n", " "), width=120)
            label = f"✓ {name} — {snippet}"
            step = {"name": name, "arguments": None, "result": res}
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, step)
            self.steps_list.addItem(item)
            self._live_steps.append(step)
        elif phase == "error":
            err = ev.get("error")
            snippet = textwrap.shorten(str(err).replace("\n", " "), width=120)
            label = f"⚠ tool error — {snippet}"
            step = {"name": "error", "arguments": None, "result": str(err)}
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, step)
            self.steps_list.addItem(item)
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
