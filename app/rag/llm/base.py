from typing import Protocol, runtime_checkable


class LLMError(Exception):
    """The LLM provider failed after its own retries. Treat as transient."""


@runtime_checkable
class LLM(Protocol):
    async def generate(self, *, system: str, prompt: str) -> str: ...
