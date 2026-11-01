from uuid import uuid4

from langchain_core.tools import tool
from langgraph.config import get_store


def build_memory_tools():
    @tool
    async def remember_fact(fact: str) -> str:
        """Store a lasting free-text preference or fact about the user (e.g. "always
        round results to 2 decimals"). NOT for numeric definitions - those are custom
        constants and belong in set_constant."""
        store = get_store()
        key = uuid4().hex[:8]
        await store.aput(("memories",), key, {"fact": fact})
        return f"Remembered (key={key})."

    @tool
    async def forget_fact(key: str) -> str:
        """Delete a stored user fact by its key, as shown in the "Known facts about
        the user" section (e.g. key=a1b2c3d4)."""
        store = get_store()
        await store.adelete(("memories",), key)
        return f"Forgot fact with key={key}."

    return [remember_fact, forget_fact]
