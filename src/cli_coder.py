from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import sys
import threading
from typing import Any, List, Optional

from rich import box

# Rich for modern, colorful CLI and Markdown rendering
from rich.console import Console
from rich.markdown import Markdown
from rich.text import Text
from rich.padding import Padding
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

from src.container import container

# -------- Appearance helpers (no external deps) --------


class _Style:
    def __init__(self, enable_color: bool, enable_icons: bool) -> None:
        self.enable_color = enable_color
        self.enable_icons = enable_icons

        # ANSI sequences
        self.RESET = "\033[0m" if enable_color else ""
        self.BOLD = "\033[1m" if enable_color else ""
        self.DIM = "\033[2m" if enable_color else ""
        self.RED = "\033[31m" if enable_color else ""
        self.GREEN = "\033[32m" if enable_color else ""
        self.YELLOW = "\033[33m" if enable_color else ""
        self.BLUE = "\033[34m" if enable_color else ""
        self.MAGENTA = "\033[35m" if enable_color else ""
        self.CYAN = "\033[36m" if enable_color else ""

    def c(self, s: str, color: str) -> str:
        return f"{color}{s}{self.RESET}" if self.enable_color else s

    def icon(self, name: str) -> str:
        if not self.enable_icons:
            return {
                "call": "->",
                "ok": "OK",
                "err": "ERR",
                "info": "i",
                "save": "*",
                "assistant": "AI",
                "user": ">",
            }.get(name, "")
        return {
            "call": "▶",
            "ok": "✅",
            "err": "⚠",
            "info": "ℹ️",
            "save": "💾",
            "assistant": "🤖",
            "user": "🧑",
        }.get(name, "")


CODER_PROFILE_SYSTEM = (
    "You are a coding agent with access to domain selection tools (domain.*) "
    "and domain tools: files.*, project.*, git.*, system.*, web.*.\n"
    "When the user asks to create or modify files, always: \n"
    "1) Select the 'files' domain (domain.files) if not already active.\n"
    "2) Use files.mkdir and files.write with absolute paths under the user's workspace.\n"
    "3) Do not print code snippets as plain text; write them to files.\n"
    "4) When done, call assistant.final with a short summary.\n"
    "For web questions, select 'web' (domain.web) and use web.scrape with CSS selectors."
)


def _supports_color() -> bool:
    if os.getenv("NO_COLOR"):
        return False
    return sys.stdout.isatty()


def _clear_screen() -> None:
    try:
        os.system("cls" if os.name == "nt" else "clear")
    except Exception:
        pass


def _print_help(st: _Style) -> None:
    print(
        "\n" + st.c("Commands", st.BOLD) + ":\n"
        f"  {st.c('/help', st.CYAN):<24} Show this help\n"
        f"  {st.c('/system <text>', st.CYAN):<24} Set/override system message\n"
        f"  {st.c('/temp <float>', st.CYAN):<24} Set temperature\n"
        f"  {st.c('/steps <int>', st.CYAN):<24} Set max tool steps per turn\n"
        f"  {st.c('/final <on|off>', st.CYAN):<24} Toggle require assistant.final\n"
        f"  {st.c('/cwd [path]', st.CYAN):<24} Show or change working directory\n"
        f"  {st.c('/status', st.CYAN):<24} Show current settings\n"
        f"  {st.c('/color <on|off>', st.CYAN):<24} Toggle colors\n"
        f"  {st.c('/icons <on|off>', st.CYAN):<24} Toggle icons\n"
        f"  {st.c('/cls', st.CYAN):<24} Clear the screen\n"
        f"  {st.c('/save <file.json>', st.CYAN):<24} Save conversation and last steps\n"
        f"  {st.c('/clear', st.CYAN):<24} Clear conversation\n"
        f"  {st.c('/exit', st.CYAN):<24} Exit\n"
    )


def _parse_slash(line: str) -> tuple[str, list[str]]:
    parts = line.strip().split()
    cmd = parts[0][1:].lower()
    args = parts[1:]
    return cmd, args


def _term_width(default: int = 120) -> int:
    try:
        w = shutil.get_terminal_size((default, 20)).columns
        return max(40, min(w, 240))
    except Exception:
        return default


def _shorten(obj: Any, width: Optional[int] = None) -> str:
    if width is None:
        width = _term_width()
    s = str(obj).replace("\n", " ")
    return s if len(s) <= width else (s[: width - 1] + "…")


def _render_markdown_or_json(
    console: Console, title: str, text: str, st: _Style, *, plain: bool = False
) -> None:
    """Render assistant text. If JSON, pretty-print; else render as Markdown."""
    to_render = text
    try:
        obj = json.loads(text)
        if isinstance(obj, dict) and obj.get("final_text"):
            to_render = str(obj.get("final_text"))
        else:
            console.print(
                Panel(
                    Syntax(json.dumps(obj, ensure_ascii=False, indent=2), "json"),
                    title=title,
                    border_style="magenta",
                    box=box.ROUNDED,
                )
            )
            return
    except Exception:
        pass
    # Normalize non-breaking spaces to allow wrapping
    to_render = to_render.replace("\u00a0", " ").replace("\u202f", " ")

    # Hard-wrap very long paragraphs as a safety net when terminals mis-handle
    # soft wrapping (esp. with wide glyphs/emoji). Avoid wrapping fenced code.
    try:
        import re
        import shutil
        import textwrap

        term_w = shutil.get_terminal_size((120, 20)).columns
        # Panel borders + padding + style margins can consume ~10 cols
        wrap_w = max(40, min(term_w - 12, 200))

        import unicodedata as _ud
        try:
            from wcwidth import wcwidth as _wcw  # more accurate terminal cell width
        except Exception:  # pragma: no cover - optional dep
            _wcw = None

        def _cell_w(ch: str) -> int:
            if _wcw is not None:
                w = _wcw(ch)
                return 0 if w < 0 else w
            # Combining marks have zero width
            if _ud.combining(ch):
                return 0
            # Treat East Asian wide/fullwidth as 2
            if _ud.east_asian_width(ch) in ("W", "F"):
                return 2
            # Most emojis are wide; naive heuristic
            if ord(ch) >= 0x1F300:
                return 2
            # Variation selectors & zero-width joiners
            if ch in ("\u200d", "\ufe0f"):
                return 0
            return 1

        def _visible_width(s: str) -> int:
            return sum(_cell_w(c) for c in s)

        def _wrap_cells(line: str, width: int) -> list[str]:
            if not line:
                return [""]
            import re as _re

            parts = _re.split(r"(\s+)", line)
            out: list[str] = []
            cur = ""
            curw = 0
            for p in parts:
                if not p:
                    continue
                pw = _visible_width(p)
                if p.isspace():
                    # only add space if there's already content
                    if curw + pw <= width:
                        cur += p
                        curw += pw
                    else:
                        out.append(cur.rstrip())
                        cur, curw = "", 0
                    continue
                if curw + pw <= width:
                    cur += p
                    curw += pw
                    continue
                # need to break p itself
                chunk = ""
                chunkw = 0
                for ch in p:
                    w = _cell_w(ch)
                    if chunkw + w > width:
                        # flush current line
                        if cur:
                            out.append(cur.rstrip())
                            cur, curw = "", 0
                        out.append(chunk)
                        chunk, chunkw = "", 0
                    chunk += ch
                    chunkw += w
                if cur:
                    out.append(cur.rstrip())
                    cur, curw = "", 0
                cur = chunk
                curw = chunkw
            if cur:
                out.append(cur.rstrip())
            return out or [""]

        def _hard_wrap_noncode(md: str) -> str:
            parts = re.split(r"(```[\s\S]*?```)", md)
            out: list[str] = []
            for chunk in parts:
                if chunk.startswith("```"):
                    out.append(chunk)
                    continue
                # Split by paragraphs to preserve blank lines
                segs = re.split(r"(\n\s*\n)", chunk)
                for seg in segs:
                    if seg.startswith("\n") or not seg.strip():
                        out.append(seg)
                        continue
                    # Wrap each line using terminal cell width
                    new_lines: list[str] = []
                    for line in seg.splitlines():
                        if re.match(r"^\s*([-*]|\d+[.)])\s+", line):
                            # keep list markers at start but still wrap by cells
                            new_lines.extend(_wrap_cells(line, wrap_w))
                        else:
                            new_lines.extend(_wrap_cells(line, wrap_w))
                    out.append("\n".join(new_lines))
            return "".join(out)

        to_render = _hard_wrap_noncode(to_render)
    except Exception:
        pass
    if plain:
        # Plain text rendering avoids any panel/markdown layout issues in rare terminals
        console.print(to_render)
        return

    # Prefer robust Text wrapping unless we detect Markdown structures
    md_like = any(
        s in to_render
        for s in (
            "```",
            "\n- ",
            "\n* ",
            "\n1. ",
            "\n#",
            "[",
            "](",
            "http://",
            "https://",
        )
    )
    if not md_like:
        txt = Text(to_render, no_wrap=False, overflow="fold")
        console.print(
            Panel(
                Padding(txt, (0, 1)),
                title=title,
                border_style="magenta",
                box=box.ROUNDED,
                expand=True,
            )
        )
        return

    # Fallback to Markdown rendering for content that likely uses MD features
    console.print(
        Panel(
            Padding(Markdown(to_render), (0, 1)),
            title=title,
            border_style="magenta",
            box=box.ROUNDED,
            expand=True,  # ensure wrapping uses the full terminal width
        )
    )


def interactive_main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="hack-coder",
        description="Interactive tools-enabled coder (terminal).",
    )
    parser.add_argument(
        "--profile",
        choices=["default", "code"],
        default="code",
        help="System preset (default: code)",
    )
    parser.add_argument("--system", default=None, help="Override system message")
    parser.add_argument("--temp", type=float, default=0.7, help="Temperature")
    parser.add_argument("--max-tokens", type=int, default=800, help="Max tokens")
    parser.add_argument("--steps", type=int, default=8, help="Max tool steps per turn")
    parser.add_argument(
        "--final-required",
        action="store_true",
        help="Require assistant.final to end turn",
    )
    parser.add_argument(
        "--no-final-required",
        dest="final_required",
        action="store_false",
        help="Allow ending on plain assistant message",
    )
    # Default to not requiring assistant.final in the interactive CLI to avoid
    # extra completion loops when a turn doesn't need tool calls.
    parser.set_defaults(final_required=False)
    parser.add_argument(
        "--cwd",
        default=None,
        help="Set working directory for files.* relative paths (default: current)",
    )
    parser.add_argument(
        "--plain",
        action="store_true",
        help="Render assistant messages as plain text (no Markdown/Panel)",
    )

    args = parser.parse_args(argv)

    # Optional cwd change
    if args.cwd:
        try:
            os.chdir(args.cwd)
        except Exception as e:
            print(f"Failed to chdir to {args.cwd}: {e}", file=sys.stderr)

    # System message preset
    if args.system:
        system_message: Optional[str] = args.system
    elif args.profile == "code":
        system_message = CODER_PROFILE_SYSTEM
    else:
        system_message = None

    # Conversation state (OpenAI-style message dicts)
    messages: List[dict[str, Any]] = []

    # Get tools-enabled adapter
    from src.adapters.llm.openai_tools_adapter import OpenAIToolsAdapter

    llm_tools = container.get_llm_tools_adapter()
    if not isinstance(llm_tools, OpenAIToolsAdapter):
        print("Tools-enabled LLM adapter is not available", file=sys.stderr)
        return 2

    # Styling config
    color_on = _supports_color()
    icons_on = True
    st = _Style(color_on, icons_on)
    console = Console(highlight=True, soft_wrap=True)

    # Banner (rich)
    console.print(
        Panel(
            "Hack Coder — interactive tools-enabled agent\n"
            "Type /help for commands. Ctrl+C cancels the current turn.",
            title="Hack Coder",
            border_style="cyan",
            box=box.ROUNDED,
        )
    )
    if system_message:
        console.print("[dim]System preset active. Use /system to override.[/dim]")

    cancel_event = threading.Event()

    def _sigint_handler(signum, frame):  # type: ignore[no-untyped-def]
        cancel_event.set()

    # Set SIGINT handler for cancel during a turn
    try:
        signal.signal(signal.SIGINT, _sigint_handler)
    except Exception:
        pass

    last_steps: list[dict[str, Any]] = []
    last_text: str = ""

    while True:
        try:
            console.print(f"[cyan]{st.icon('user')} you> [/cyan]", end="")
            prompt = input().strip()
        except EOFError:
            print()
            break
        except KeyboardInterrupt:
            print()
            break

        if not prompt:
            continue

        if prompt.startswith("/"):
            cmd, sargs = _parse_slash(prompt)
            if cmd in ("h", "help"):
                tbl = Table(title="Commands", box=box.MINIMAL_DOUBLE_HEAD)
                tbl.add_column("Command", style="cyan", no_wrap=True)
                tbl.add_column("Description")
                tbl.add_row("/help", "Show this help")
                tbl.add_row("/system <text>", "Set/override system message")
                tbl.add_row("/temp <float>", "Set temperature")
                tbl.add_row("/steps <int>", "Set max tool steps per turn")
                tbl.add_row("/final <on|off>", "Toggle require assistant.final")
                tbl.add_row("/cwd [path]", "Show or change working directory")
                tbl.add_row("/status", "Show current settings")
                tbl.add_row("/color <on|off>", "Toggle colors")
                tbl.add_row("/icons <on|off>", "Toggle icons")
                tbl.add_row("/workspace <on|off>", "Toggle WORKSPACE_ROOT enforcement")
                tbl.add_row("/workspace-root <path>", "Set WORKSPACE_ROOT env path")
                tbl.add_row("/load <file.json>", "Load saved conversation")
                tbl.add_row("/cls", "Clear the screen")
                tbl.add_row("/save <file.json>", "Save conversation and steps")
                tbl.add_row("/clear", "Clear conversation")
                tbl.add_row("/exit", "Exit")
                console.print(tbl)
                continue
            if cmd == "system":
                system_message = " ".join(sargs) if sargs else None
                msg = (
                    "[green]System set.[/green]"
                    if system_message
                    else "[yellow]System cleared.[/yellow]"
                )
                console.print(msg)
                continue
            if cmd == "temp" and sargs:
                try:
                    args.temp = float(sargs[0])
                    console.print(f"[blue]Temperature[/blue] = {args.temp}")
                except ValueError:
                    console.print("[red]Invalid temp[/red]")
                continue
            if cmd == "steps" and sargs:
                try:
                    args.steps = int(sargs[0])
                    console.print(f"[blue]Tool steps[/blue] = {args.steps}")
                except ValueError:
                    console.print("[red]Invalid steps[/red]")
                continue
            if cmd == "final" and sargs:
                v = sargs[0].lower()
                args.final_required = v in ("on", "true", "1", "yes")
                console.print(f"[blue]final_required[/blue] = {args.final_required}")
                continue
            if cmd == "color" and sargs:
                v = sargs[0].lower()
                color_on = v in ("on", "true", "1", "yes")
                st = _Style(color_on, icons_on)
                console.print("[green]Colors updated.[/green]")
                continue
            if cmd == "icons" and sargs:
                v = sargs[0].lower()
                icons_on = v in ("on", "true", "1", "yes")
                st = _Style(color_on, icons_on)
                console.print("[green]Icons updated.[/green]")
                continue
            if cmd == "status":
                stbl = Table(title="Status", box=box.SIMPLE_HEAVY)
                stbl.add_column("Key", style="magenta")
                stbl.add_column("Value")
                stbl.add_row("cwd", os.getcwd())
                stbl.add_row("temperature", str(args.temp))
                stbl.add_row("steps", str(args.steps))
                stbl.add_row("final_required", str(args.final_required))
                stbl.add_row("colors", str(color_on))
                stbl.add_row("icons", str(icons_on))
                stbl.add_row(
                    "HACK_WORKSPACE_ROOT", os.getenv("HACK_WORKSPACE_ROOT", "")
                )
                stbl.add_row(
                    "HACK_WORKSPACE_ENFORCE", os.getenv("HACK_WORKSPACE_ENFORCE", "1")
                )
                console.print(stbl)
                continue
            if cmd == "workspace" and sargs:
                v = sargs[0].lower()
                enabled = v in ("on", "true", "1", "yes")
                os.environ["HACK_WORKSPACE_ENFORCE"] = "1" if enabled else "0"
                console.print(
                    f"[green]WORKSPACE enforcement[/green] = {'on' if enabled else 'off'}"
                )
                continue
            if cmd == "workspace-root" and sargs:
                root = os.path.abspath(os.path.expanduser(" ".join(sargs)))
                os.environ["HACK_WORKSPACE_ROOT"] = root
                console.print(f"[green]WORKSPACE_ROOT[/green] = {root}")
                continue
            if cmd == "load" and sargs:
                path = sargs[0]
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    messages = list(data.get("conversation", []))
                    last_text = str(data.get("last_text", ""))
                    last_steps = list(data.get("last_steps", []))
                    console.print(f"[green]Loaded[/green] {path}")
                except Exception as e:
                    console.print(f"[red]Load failed:[/red] {e}")
                continue
            if cmd == "cwd":
                if not sargs:
                    console.print(f"[dim]{os.getcwd()}[/dim]")
                else:
                    try:
                        os.chdir(sargs[0])
                        console.print(f"[dim]{os.getcwd()}[/dim]")
                    except Exception as e:
                        console.print(f"[red]Failed to chdir:[/red] {e}")
                continue
            if cmd == "cls":
                _clear_screen()
                continue
            if cmd == "clear":
                messages.clear()
                last_steps = []
                last_text = ""
                console.print("[yellow]Conversation cleared.[/yellow]")
                continue
            if cmd == "save" and sargs:
                path = sargs[0]
                try:
                    with open(path, "w", encoding="utf-8") as f:
                        json.dump(
                            {
                                "conversation": messages,
                                "last_text": last_text,
                                "last_steps": last_steps,
                            },
                            f,
                            ensure_ascii=False,
                            indent=2,
                        )
                    console.print(f"{st.icon('save')} [green]Saved to[/green] {path}")
                except Exception as e:
                    console.print(f"[red]Save failed:[/red] {e}")
                continue
            if cmd in ("exit", "quit", "q"):
                break
            console.print("[red]Unknown command.[/red] Use /help for list.")
            continue

        # Reset cancel flag for this turn
        cancel_event.clear()

        def _on_step(ev: dict[str, Any]) -> None:
            phase = str(ev.get("phase") or "")
            name = str(ev.get("name") or "?")
            if phase == "call":
                args_str = _shorten(ev.get("arguments"))
                console.print(
                    f"[dim]tool>[/dim] [cyan]{st.icon('call')} {name}[/cyan] [dim]{args_str}[/dim]"
                )
            elif phase == "result":
                res_str = _shorten(ev.get("result"))
                console.print(
                    f"[dim]tool>[/dim] [green]{st.icon('ok')} {name} —[/green] {res_str}"
                )
            elif phase == "error":
                err = _shorten(ev.get("error"))
                console.print(
                    f"[dim]tool>[/dim] [yellow]{st.icon('err')} {err}[/yellow]"
                )

        # Execute one chat turn with tools
        try:
            result = llm_tools.run_chat_turn_with_trace(
                messages=messages,
                user_text=prompt,
                system_message=system_message,
                temperature=args.temp,
                max_tokens=args.max_tokens,
                tool_max_steps=args.steps,
                require_final_tool=args.final_required,
                on_step=_on_step,
                should_cancel=cancel_event.is_set,  # type: ignore[arg-type]
            )
        except KeyboardInterrupt:
            cancel_event.set()
            console.print("[yellow]Cancelled.[/yellow]")
            continue
        except Exception as e:
            console.print(f"[red]Error:[/red] {e}")
            continue

        # Update history from backend for continuity
        messages = list(result.get("messages", []) or [])
        last_steps = list(result.get("steps", []) or [])
        last_text = str(result.get("text", ""))

        # Render assistant text (Markdown aware)
        if last_text:
            _render_markdown_or_json(
                console,
                f"{st.icon('assistant')} assistant",
                last_text,
                st,
                plain=bool(args.plain),
            )

    return 0


def main(argv: Optional[list[str]] = None) -> int:  # pragma: no cover
    return interactive_main(argv)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
