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
        "--steps", type=int, default=4, help="Maximum tool-calling steps"
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

            console = Console()
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
                        )
                    )
                    text = ""
            except Exception:
                pass
            if text:
                # Wrap Markdown in Padding so long paragraphs wrap correctly inside Panel
                console.print(
                    Panel(
                        Padding(Markdown(text), (0, 1)),
                        title="assistant",
                        box=box.ROUNDED,
                        border_style="magenta",
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
