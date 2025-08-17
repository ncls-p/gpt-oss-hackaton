from .domain import Command, LsResult
from .ports import FileSystemPort, FunctionCallingLLMPort, LLMPort


class LsUseCase:
    """Use case to interpret a user instruction via LLM and execute safe ls."""

    llm: LLMPort
    fs: FileSystemPort

    def __init__(self, llm: LLMPort, fs: FileSystemPort):
        self.llm = llm
        self.fs = fs

    def execute(self, user_input: str) -> LsResult:
        cmd: Command = self.llm.interpret(user_input)
        if not cmd.is_ls():
            raise ValueError("Only 'ls' commands are supported in this demo.")
        path = cmd.target_path()
        return self.fs.list_dir(path)


class NaturalLanguageListUseCase:
    """Use case that lets user ask in natural language; LLM extracts the path (tool-calling style)."""

    llm: FunctionCallingLLMPort
    fs: FileSystemPort

    def __init__(self, llm: FunctionCallingLLMPort, fs: FileSystemPort):
        self.llm = llm
        self.fs = fs

    def execute(self, user_input: str) -> LsResult:
        path = self.llm.extract_list_dir_path(user_input)
        return self.fs.list_dir(path)
