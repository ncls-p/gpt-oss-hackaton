from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import sys
import threading
from typing import Any, List, Optional

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
    "and domain tools: files.*, project.*, git.*, system.*.\n"
    "When the user asks to create or modify files, always: \n"
    "1) Select the 'files' domain (domain.files) if not already active.\n"
    "2) Use files.mkdir and files.write with absolute paths under the user's workspace.\n"
    "3) Do not print code snippets as plain text; write them to files.\n"
    "4) When done, call assistant.final with a short summary."
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
    parser.set_defaults(final_required=True)
    parser.add_argument(
        "--cwd",
        default=None,
        help="Set working directory for files.* relative paths (default: current)",
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

    # Banner
    print(
        st.c("\nHack Coder", st.BOLD), st.c("— interactive tools-enabled agent", st.DIM)
    )
    print(st.c("Type /help for commands. Ctrl+C cancels the current turn.", st.DIM))
    if system_message:
        print(st.c("System preset active. Use /system to override.", st.DIM))

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
            prompt = input(st.c(f"{st.icon('user')} you> ", st.CYAN)).strip()
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
                _print_help(st)
                continue
            if cmd == "system":
                system_message = " ".join(sargs) if sargs else None
                msg = (
                    st.c("System set.", st.GREEN)
                    if system_message
                    else st.c("System cleared.", st.YELLOW)
                )
                print(msg)
                continue
            if cmd == "temp" and sargs:
                try:
                    args.temp = float(sargs[0])
                    print(st.c(f"Temperature = {args.temp}", st.BLUE))
                except ValueError:
                    print(st.c("Invalid temp", st.RED))
                continue
            if cmd == "steps" and sargs:
                try:
                    args.steps = int(sargs[0])
                    print(st.c(f"Tool steps = {args.steps}", st.BLUE))
                except ValueError:
                    print(st.c("Invalid steps", st.RED))
                continue
            if cmd == "final" and sargs:
                v = sargs[0].lower()
                args.final_required = v in ("on", "true", "1", "yes")
                print(st.c(f"final_required = {args.final_required}", st.BLUE))
                continue
            if cmd == "color" and sargs:
                v = sargs[0].lower()
                color_on = v in ("on", "true", "1", "yes")
                st = _Style(color_on, icons_on)
                print(st.c("Colors updated.", st.GREEN))
                continue
            if cmd == "icons" and sargs:
                v = sargs[0].lower()
                icons_on = v in ("on", "true", "1", "yes")
                st = _Style(color_on, icons_on)
                print(st.c("Icons updated.", st.GREEN))
                continue
            if cmd == "status":
                print(
                    f"cwd: {os.getcwd()}\n"
                    f"temperature: {args.temp}\n"
                    f"steps: {args.steps}\n"
                    f"final_required: {args.final_required}\n"
                    f"colors: {color_on}\n"
                    f"icons: {icons_on}\n"
                )
                continue
            if cmd == "cwd":
                if not sargs:
                    print(st.c(os.getcwd(), st.DIM))
                else:
                    try:
                        os.chdir(sargs[0])
                        print(st.c(os.getcwd(), st.DIM))
                    except Exception as e:
                        print(st.c(f"Failed to chdir: {e}", st.RED))
                continue
            if cmd == "cls":
                _clear_screen()
                continue
            if cmd == "clear":
                messages.clear()
                last_steps = []
                last_text = ""
                print(st.c("Conversation cleared.", st.YELLOW))
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
                    print(f"{st.icon('save')} " + st.c(f"Saved to {path}", st.GREEN))
                except Exception as e:
                    print(st.c(f"Save failed: {e}", st.RED))
                continue
            if cmd in ("exit", "quit", "q"):
                break
            print(st.c("Unknown command. /help for list.", st.RED))
            continue

        # Reset cancel flag for this turn
        cancel_event.clear()

        def _on_step(ev: dict[str, Any]) -> None:
            phase = str(ev.get("phase") or "")
            name = str(ev.get("name") or "?")
            if phase == "call":
                args_str = _shorten(ev.get("arguments"))
                print(
                    st.c("tool> ", st.DIM)
                    + st.c(f"{st.icon('call')} {name} ", st.CYAN)
                    + st.c(args_str, st.DIM)
                )
            elif phase == "result":
                res_str = _shorten(ev.get("result"))
                print(
                    st.c("tool> ", st.DIM)
                    + st.c(f"{st.icon('ok')} {name} — ", st.GREEN)
                    + res_str
                )
            elif phase == "error":
                err = _shorten(ev.get("error"))
                print(
                    st.c("tool> ", st.DIM) + st.c(f"{st.icon('err')} {err}", st.YELLOW)
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
            print(st.c("Cancelled.", st.YELLOW))
            continue
        except Exception as e:
            print(st.c(f"Error: {e}", st.RED))
            continue

        # Update history from backend for continuity
        messages = list(result.get("messages", []) or [])
        last_steps = list(result.get("steps", []) or [])
        last_text = str(result.get("text", ""))

        # Render assistant text (simple)
        if last_text:
            print(st.c(f"{st.icon('assistant')} assistant> ", st.MAGENTA) + last_text)

    return 0


def main(argv: Optional[list[str]] = None) -> int:  # pragma: no cover
    return interactive_main(argv)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
