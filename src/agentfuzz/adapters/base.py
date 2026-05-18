from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable, Sequence
from typing import Any

from agentfuzz.core.fault import Fault

AgentCallable = Callable[[dict[str, Any]], dict[str, Any]]


class Adapter(ABC):
    """Wrap a framework-specific agent into the harness's AgentCallable shape.

    Subclasses must:
      * route every tool invocation through `compose_tool_call` (pre) and
        `compose_tool_result` (post) so faults can intervene
      * write `final_output` events into the FaultContext so observer faults
        (e.g. PromptInjection) can analyze the result
      * record `token_usage` into the FaultContext when available
    """

    framework_name: str = "abstract"

    @classmethod
    @abstractmethod
    def is_available(cls) -> bool:
        """Return True if the framework is installed."""

    @abstractmethod
    def wrap(self, agent: Any, *, faults: Sequence[Fault]) -> AgentCallable:
        """Return an AgentCallable that drives the framework agent."""
