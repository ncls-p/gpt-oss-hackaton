from ..domain import Command


class OpenAIAdapter:
    """LLM adapter placeholder.

    For this initial step, we don't call an external LLM; we simply parse the
    user input directly into a domain Command. This keeps the adapter fully
    typed and static-analysis friendly. Later we can swap in a real OpenAI
    client behind the same port.
    """

    model: str

    def __init__(self, model: str = "fallback"):
        self.model = model

    def interpret(self, user_input: str) -> Command:
        return Command(user_input)


# Provide a factory that callers can use in wiring without depending on openai at import time
def create_llm_adapter() -> OpenAIAdapter:
    return OpenAIAdapter()
