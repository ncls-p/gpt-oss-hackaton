from gpt_oss_hackathon.adapters.fs_adapter import LocalFSAdapter
from gpt_oss_hackathon.adapters.llm_adapter import create_llm_adapter
from gpt_oss_hackathon.adapters.fn_llm_adapter import (
    create_function_calling_llm_adapter,
)
from gpt_oss_hackathon.usecases import LsUseCase, NaturalLanguageListUseCase


def main():
    import sys

    # Ensure .env is loaded early if present
    try:
        from dotenv import load_dotenv

        _ = load_dotenv()
    except Exception:
        pass

    # Modes:
    # - default: expects "ls <path>" (structured)
    # - --nl: natural language, e.g. "list the files in /Users/me"
    use_nl = False
    argv = [a for a in sys.argv[1:] if a != "--nl"]
    if len(sys.argv) > 1 and "--nl" in sys.argv[1:]:
        use_nl = True

    fs = LocalFSAdapter()
    user_input = " ".join(argv) if argv else input("Enter command or query: ")
    # Auto-switch to NL mode if the input doesn't start with 'ls'
    if not user_input.strip().startswith("ls"):
        use_nl = True
    if use_nl:
        llm_fc = create_function_calling_llm_adapter()
        uc = NaturalLanguageListUseCase(llm_fc, fs)
    else:
        llm = create_llm_adapter()
        uc = LsUseCase(llm, fs)

    try:
        res = uc.execute(user_input)
        print(f"Listing {res.path}:")
        for e in res.entries:
            print(e)
    except Exception as exc:
        print("Error:", exc)


if __name__ == "__main__":
    main()
