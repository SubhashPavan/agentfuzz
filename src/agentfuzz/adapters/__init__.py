"""Framework adapters wrap real agent frameworks behind a uniform interface.

Each adapter exposes:
  * `wrap(agent, *, faults)` — returns an AgentCallable that the harness can
    invoke. It must route tool calls through `compose_tool_call` /
    `compose_tool_result` so faults can intervene.
  * `is_available()` — returns True when the underlying framework is importable.

Adapters are intentionally thin. The lifecycle is owned by the harness; the
adapter only knows how to drive its framework's particular call shape.
"""

from agentfuzz.adapters.callable import CallableAdapter

# LangGraphAdapter is imported lazily to avoid pulling langchain_core at
# import time when the user hasn't installed the optional extra.
__all__ = ["CallableAdapter", "LangGraphAdapter", "wrap_tools"]


def __getattr__(name: str):
    if name in {"LangGraphAdapter", "wrap_tools"}:
        from agentfuzz.adapters import langgraph as _lg

        return getattr(_lg, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
