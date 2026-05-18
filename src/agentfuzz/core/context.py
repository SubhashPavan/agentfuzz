from __future__ import annotations

import time
from dataclasses import dataclass, field
from random import Random
from typing import Any


@dataclass
class ToolCall:
    name: str
    arguments: dict[str, Any]
    call_id: str | None = None


@dataclass
class ToolResult:
    call_id: str | None
    content: Any
    is_error: bool = False
    elapsed_ms: float = 0.0


@dataclass
class FaultContext:
    """Per-iteration state shared with every fault.

    Faults read from this to decide what to do and write to it to record what
    they did. The harness owns the lifecycle; faults must not mutate fields
    other than `events` and `tags`.
    """

    iteration: int
    seed: int
    started_at: float = field(default_factory=time.time)
    rng: Random = field(init=False)
    events: list[dict[str, Any]] = field(default_factory=list)
    tags: set[str] = field(default_factory=set)
    token_usage: int = 0
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_results: list[ToolResult] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.rng = Random(self.seed)

    def record(self, event_type: str, **fields: Any) -> None:
        self.events.append({"type": event_type, "t": time.time() - self.started_at, **fields})
