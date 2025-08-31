from __future__ import annotations

import json
import textwrap
from typing import Optional

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
    QTextEdit,
    QToolBar,
    QWidget,
)

from src.container import container


class _RunWorker(QObject):
    started = Signal()
    finished = Signal(dict)
    error = Signal(str)

    def __init__(
        self,
        prompt: str,
        system_message: Optional[str],
        temperature: float,
        max_tokens: int,
        tool_max_steps: int,
        require_final_tool: bool,
    ) -> None:
        super().__init__()
        self.prompt = prompt
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

            result = llm_tools.run_with_trace(
                prompt=self.prompt,
                system_message=self.system_message,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                tool_max_steps=self.tool_max_steps,
                require_final_tool=self.require_final_tool,
            )
            self.finished.emit(result)
        except Exception as e:  # pragma: no cover
            self.error.emit(str(e))


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("GPT OSS Hackathon — Tools UI")
        self.setMinimumSize(950, 600)

        self._build_actions()
        self._build_toolbar()
        self._build_layout()

    # UI building
    def _build_actions(self) -> None:
        self.action_run = QAction(QIcon(), "Run", self)
        self.action_run.triggered.connect(self._on_run_clicked)

        self.action_save = QAction(QIcon(), "Save Result…", self)
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

        # Left: Inputs
        left = QWidget(splitter)
        form = QFormLayout(left)
        self.prompt_edit = QTextEdit(left)
        self.prompt_edit.setPlaceholderText(
            "What should I do? e.g. ‘Open Terminal and list *.py in ~/project then read README.md’"
        )
        self.prompt_edit.setAcceptRichText(False)

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

        run_btn = QPushButton("Run", left)
        run_btn.clicked.connect(self._on_run_clicked)

        self.progress = QProgressBar(left)
        self.progress.setRange(0, 0)
        self.progress.setVisible(False)

        form.addRow(QLabel("Prompt:"), self.prompt_edit)
        form.addRow(QLabel("System:"), self.system_edit)
        form.addRow(QLabel("Temperature:"), self.temp_spin)
        form.addRow(QLabel("Max tokens:"), self.max_tokens_spin)
        form.addRow(QLabel("Tool steps:"), self.steps_spin)
        form.addRow(self.final_required_chk)
        form.addRow(run_btn)
        form.addRow(self.progress)

        # Right: Outputs
        right = QWidget(splitter)
        right_layout = QGridLayout(right)

        self.final_text = QTextBrowser(right)
        self.final_text.setOpenExternalLinks(True)
        self.final_text.setPlaceholderText("Final assistant text will appear here… (Markdown supported)")

        self.steps_list = QListWidget(right)
        self.steps_list.itemDoubleClicked.connect(self._show_step_details)

        right_layout.addWidget(QLabel("Final Text"), 0, 0)
        right_layout.addWidget(self.final_text, 1, 0)
        right_layout.addWidget(QLabel("Tool Steps (double-click for details)"), 2, 0)
        right_layout.addWidget(self.steps_list, 3, 0)

        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)

        outer = QHBoxLayout(central)
        outer.addWidget(splitter)

    # Slots
    @Slot()
    def _on_run_clicked(self) -> None:
        prompt = self.prompt_edit.toPlainText().strip()
        if not prompt:
            QMessageBox.warning(self, "Missing prompt", "Please enter a prompt first.")
            return

        system = self.system_edit.text().strip() or None
        temp = float(self.temp_spin.value())
        max_tokens = int(self.max_tokens_spin.value())
        steps = int(self.steps_spin.value())
        final_required = bool(self.final_required_chk.isChecked())

        # Threaded worker
        self.progress.setVisible(True)
        self.final_text.clear()
        self.steps_list.clear()

        self._thread = QThread(self)
        self._worker = _RunWorker(
            prompt, system, temp, max_tokens, steps, final_required
        )
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_run_finished)
        self._worker.error.connect(self._on_run_error)
        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)

        self._thread.start()

    @Slot(dict)
    def _on_run_finished(self, result: dict) -> None:
        self.progress.setVisible(False)
        text = str(result.get("text", ""))
        # Keep original raw text for Save
        self._last_final_raw = text

        # If backend accidentally returned a JSON object containing final_text,
        # extract and render its Markdown; otherwise render the text as Markdown directly.
        md = text
        try:
            import json as _json

            obj = _json.loads(text)
            if isinstance(obj, dict):
                ft = obj.get("final_text") or obj.get("text") or obj.get("content")
                if isinstance(ft, str) and ft.strip():
                    md = ft
        except Exception:
            pass
        # QTextBrowser supports setMarkdown; it gracefully renders plain text too
        try:
            self.final_text.setMarkdown(md)
        except Exception:
            self.final_text.setPlainText(md)

        steps = result.get("steps", []) or []
        for idx, step in enumerate(steps, start=1):
            name = step.get("name") or "?"
            res = step.get("result") or ""
            snippet = textwrap.shorten(str(res).replace("\n", " "), width=120)
            item = QListWidgetItem(f"{idx}. {name} — {snippet}")
            item.setData(Qt.ItemDataRole.UserRole, step)
            self.steps_list.addItem(item)

    @Slot(str)
    def _on_run_error(self, message: str) -> None:  # pragma: no cover
        self.progress.setVisible(False)
        QMessageBox.critical(self, "Run error", message)

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
        # Preserve the exact raw text we received, not the rendered/plaintext version
        text = getattr(self, "_last_final_raw", self.final_text.toPlainText())
        if not text and self.steps_list.count() == 0:
            QMessageBox.information(self, "Nothing to save", "Run something first.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Save result", filter="JSON (*.json)"
        )
        if not path:
            return
        steps = []
        for i in range(self.steps_list.count()):
            steps.append(self.steps_list.item(i).data(Qt.ItemDataRole.UserRole))
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"text": text, "steps": steps}, f, ensure_ascii=False, indent=2)

    @Slot()
    def _on_clear_clicked(self) -> None:
        self.final_text.clear()
        self.steps_list.clear()
