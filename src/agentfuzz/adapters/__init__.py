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

__all__ = ["CallableAdapter"]
