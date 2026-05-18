from __future__ import annotations

from abc import ABC
from dataclasses import dataclass
from enum import Enum
from typing import Any

from agentfuzz.core.context import FaultContext, ToolCall, ToolResult


class FaultOutcome(Enum):
    """What a tool-level fault did to a single tool call."""

    PASSTHROUGH = "passthrough"
    MUTATED = "mutated"
    BLOCKED = "blocked"


@dataclass
class FaultDecision:
    """A fault's response to a tool call.

    `outcome` says what category of intervention happened. `mutated_*` carry the
    replacement values when the outcome is MUTATED or BLOCKED. `reason` is a
    short human label that surfaces in the report.
    """

    outcome: FaultOutcome
    mutated_arguments: dict[str, Any] | None = None
    mutated_result: ToolResult | None = None
    reason: str = ""

    @classmethod
    def passthrough(cls) -> FaultDecision:
        return cls(FaultOutcome.PASSTHROUGH)


class Fault(ABC):
    """Base class for a fault injector.

    A fault is a small, focused thing that may:
      * mutate a tool call's arguments before execution
      * replace a tool call's result after execution
      * block a tool call entirely (raise / return an error result)
      * inject text into a prompt
      * observe and tag the run (e.g. detect cost spirals)

    Subclasses override only the hooks they care about. The default
    implementations are passthrough.
    """

    name: str = ""

    def __init__(self, *, name: str | None = None) -> None:
        self.name = name or self.__class__.__name__

    def on_iteration_start(self, ctx: FaultContext) -> None:
        """Called once at the start of each iteration."""

    def on_tool_call(self, ctx: FaultContext, call: ToolCall) -> FaultDecision:
        """Inspect or mutate a tool call before it executes.

        Return PASSTHROUGH to let the call proceed unchanged. Return MUTATED
        with `mutated_arguments` to change the arguments. Return BLOCKED with
        `mutated_result` to short-circuit with a synthesized result (used to
        simulate timeouts, malformed responses, etc.).
        """
        return FaultDecision.passthrough()

    def on_tool_result(self, ctx: FaultContext, call: ToolCall, result: ToolResult) -> FaultDecision:
        """Inspect or mutate a tool result after it executes.

        Used by faults that corrupt successful responses (malformed JSON,
        partial failure, schema drift).
        """
        return FaultDecision.passthrough()

    def on_prompt(self, ctx: FaultContext, prompt: str) -> str:
        """Mutate the user-facing prompt. Default: passthrough."""
        return prompt

    def on_iteration_end(self, ctx: FaultContext) -> None:
        """Called once at the end of each iteration. Use to tag failures
        detected post-hoc (e.g. cost spirals)."""
