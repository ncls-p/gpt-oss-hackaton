import argparse
import json
import sys
from typing import Any

from src.container import container


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="hack-tools",
        description=(
            "Run a tools-enabled assistant once and print the final text with a step trace."
        ),
    )
    parser.add_argument("--prompt", required=True, help="User prompt to run")
    parser.add_argument(
        "--system",
        default=None,
        help="Optional system message (default: generic assistant)",
    )
    parser.add_argument("--temp", type=float, default=0.7, help="Temperature")
    parser.add_argument(
        "--max-tokens", type=int, default=800, help="Max tokens for the reply"
    )
    parser.add_argument(
        "--steps", type=int, default=100, help="Maximum tool-calling steps"
    )
    parser.add_argument(
        "--final-required",
        action="store_true",
        help="Require assistant.final to end the run",
    )
    parser.add_argument(
        "--no-final-required",
        dest="final_required",
        action="store_false",
        help="Allow ending on a plain assistant message",
    )
    # Default to requiring assistant.final so the model actually uses tools
    parser.set_defaults(final_required=True)
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty print output (Markdown/JSON) with colors",
    )
    parser.add_argument(
        "--profile",
        choices=["default", "code"],
        default="default",
        help="Preset system guidance (code uses files.* etc.)",
    )
    parser.add_argument(
        "--plain",
        action="store_true",
        help="When used with --pretty, render plain text (no Markdown/Panel)",
    )

    args = parser.parse_args(argv)

    from src.adapters.llm.openai_tools_adapter import OpenAIToolsAdapter

    llm_tools = container.get_llm_tools_adapter()
    if not isinstance(llm_tools, OpenAIToolsAdapter):
        print("Tools-enabled LLM adapter is not available", file=sys.stderr)
        return 2

    system_msg = args.system
    if not system_msg and args.profile == "code":
        system_msg = (
            "You are a coding agent. Prefer domain.files -> files.mkdir/files.write to create files. "
            "Use absolute paths. Do not print code inline; write files instead. Finish with assistant.final."
        )

    result: dict[str, Any] = llm_tools.run_with_trace(
        prompt=args.prompt,
        system_message=system_msg,
        temperature=args.temp,
        max_tokens=args.max_tokens,
        tool_max_steps=args.steps,
        require_final_tool=args.final_required,
    )
    if args.pretty:
        try:
            from rich import box
            from rich.console import Console
            from rich.markdown import Markdown
            from rich.padding import Padding
            from rich.panel import Panel
            from rich.syntax import Syntax
            from rich.text import Text

            # Enable soft wrapping so long paragraphs (single line without newlines)
            # wrap instead of being visually truncated.
            console = Console(soft_wrap=True)
            text = result.get("text", "") or ""
            try:
                obj = json.loads(text)
                if isinstance(obj, dict) and obj.get("final_text"):
                    text = obj.get("final_text") or ""
                else:
                    console.print(
                        Panel(
                            Syntax(
                                json.dumps(obj, ensure_ascii=False, indent=2), "json"
                            ),
                            title="assistant",
                            box=box.ROUNDED,
                            border_style="magenta",
                            expand=True,
                        )
                    )
                    text = ""
            except Exception:
                pass
            if text:
                # Normalize non-breaking spaces to allow wrapping
                text = text.replace("\u00a0", " ").replace("\u202f", " ")
                # Hard-wrap very long paragraphs as a safety net (avoid code blocks)
                try:
                    import re
                    import shutil
                    import unicodedata as _ud
                    try:
                        from wcwidth import wcwidth as _wcw
                    except Exception:  # pragma: no cover
                        _wcw = None

                    def _cell_w(ch: str) -> int:
                        if _wcw is not None:
                            w = _wcw(ch)
                            return 0 if w < 0 else w
                        if _ud.combining(ch):
                            return 0
                        if _ud.east_asian_width(ch) in ("W", "F"):
                            return 2
                        if ord(ch) >= 0x1F300:
                            return 2
                        if ch in ("\u200d", "\ufe0f"):
                            return 0
                        return 1

                    def _visible_width(s: str) -> int:
                        return sum(_cell_w(c) for c in s)

                    def _wrap_cells(line: str, width: int) -> list[str]:
                        if not line:
                            return [""]
                        parts = re.split(r"(\s+)", line)
                        out: list[str] = []
                        cur = ""
                        curw = 0
                        for p in parts:
                            if not p:
                                continue
                            pw = _visible_width(p)
                            if p.isspace():
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
                            # break token by cells
                            chunk = ""
                            chunkw = 0
                            for ch in p:
                                w = _cell_w(ch)
                                if chunkw + w > width:
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

                    term_w = shutil.get_terminal_size((120, 20)).columns
                    wrap_w = max(40, min(term_w - 12, 200))
                    parts = re.split(r"(```[\s\S]*?```)", text)
                    new_parts: list[str] = []
                    for chunk in parts:
                        if chunk.startswith("```"):
                            new_parts.append(chunk)
                            continue
                        segs = re.split(r"(\n\s*\n)", chunk)
                        for seg in segs:
                            if seg.startswith("\n") or not seg.strip():
                                new_parts.append(seg)
                                continue
                            lines: list[str] = []
                            for line in seg.splitlines():
                                lines.extend(_wrap_cells(line, wrap_w))
                            new_parts.append("\n".join(lines))
                    wrapped = "".join(new_parts)
                    # Convert single newlines to Markdown hard-breaks so wrapping is preserved
                    def _apply_hardbreaks(md_text: str) -> str:
                        # Preserve code blocks untouched
                        code_pat = re.compile(r"```([A-Za-z0-9_+-]+)?\n([\s\S]*?)\n```", re.DOTALL)
                        out: list[str] = []
                        last = 0
                        for m in code_pat.finditer(md_text):
                            before = md_text[last:m.start()]
                            out.append(_hardbreaks_in_paragraphs(before))
                            out.append(md_text[m.start():m.end()])
                            last = m.end()
                        out.append(_hardbreaks_in_paragraphs(md_text[last:]))
                        return "".join(out)

                    def _hardbreaks_in_paragraphs(chunk: str) -> str:
                        paras = re.split(r"(\n\s*\n+)", chunk)
                        out: list[str] = []
                        for seg in paras:
                            if re.match(r"\n\s*\n+", seg):
                                out.append(seg)
                            else:
                                lines = seg.splitlines()
                                out.append("  \n".join(lines) if lines else seg)
                        return "".join(out)

                    text = _apply_hardbreaks(wrapped)
                except Exception:
                    pass
                if args.plain:
                    console.print(text)
                else:
                    console.print(
                        Panel(
                            Padding(Markdown(text), (0, 1)),
                            title="assistant",
                            box=box.ROUNDED,
                            border_style="magenta",
                            expand=True,
                        )
                    )
            # steps table
            if result.get("steps"):
                console.print_json(data=result.get("steps"))
        except Exception:
            print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
