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

# Framework adapters are imported lazily so importing this package doesn't
# pull langchain_core / crewai / autogen until the user actually uses them.
__all__ = [
    "AutoGenAdapter",
    "CallableAdapter",
    "CrewAIAdapter",
    "LangGraphAdapter",
    "wrap_autogen_tools",
    "wrap_crewai_tools",
    "wrap_tools",
]


def __getattr__(name: str):
    if name in {"LangGraphAdapter", "wrap_tools"}:
        from agentfuzz.adapters import langgraph as _lg

        return getattr(_lg, name)
    if name == "CrewAIAdapter":
        from agentfuzz.adapters import crewai as _crewai

        return _crewai.CrewAIAdapter
    if name == "wrap_crewai_tools":
        from agentfuzz.adapters import crewai as _crewai

        return _crewai.wrap_tools
    if name == "AutoGenAdapter":
        from agentfuzz.adapters import autogen as _autogen

        return _autogen.AutoGenAdapter
    if name == "wrap_autogen_tools":
        from agentfuzz.adapters import autogen as _autogen

        return _autogen.wrap_tools
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
