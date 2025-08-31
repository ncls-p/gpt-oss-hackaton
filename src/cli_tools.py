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

    args = parser.parse_args(argv)

    from src.adapters.llm.openai_tools_adapter import OpenAIToolsAdapter

    llm_tools = container.get_llm_tools_adapter()
    if not isinstance(llm_tools, OpenAIToolsAdapter):
        print("Tools-enabled LLM adapter is not available", file=sys.stderr)
        return 2

    result: dict[str, Any] = llm_tools.run_with_trace(
        prompt=args.prompt,
        system_message=args.system,
        temperature=args.temp,
        max_tokens=args.max_tokens,
        tool_max_steps=args.steps,
        require_final_tool=args.final_required,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
