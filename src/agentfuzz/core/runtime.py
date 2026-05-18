"""Process-wide runtime hooks for adapters that can't thread state through.

When an adapter wraps a framework that doesn't let us pass a `state` dict down
to the tool layer (LangGraph, CrewAI, AutoGen, etc.), we instead stash the
current `FaultContext` and active fault list into a `contextvars.ContextVar`.
Wrapped tools read from these vars at call time.

`contextvars` propagates correctly across both sync and asyncio boundaries —
each iteration runs in its own context so concurrent iterations stay isolated.
"""
from __future__ import annotations

import contextvars
from collections.abc import Iterator, Sequence
from contextlib import contextmanager

from agentfuzz.core.context import FaultContext
from agentfuzz.core.fault import Fault

_ctx: contextvars.ContextVar[FaultContext | None] = contextvars.ContextVar(
    "agentfuzz_ctx", default=None
)
_faults: contextvars.ContextVar[tuple[Fault, ...] | None] = contextvars.ContextVar(
    "agentfuzz_faults", default=None
)


@contextmanager
def active_run(ctx: FaultContext, faults: Sequence[Fault]) -> Iterator[None]:
    """Bind the current FaultContext + faults for the duration of one iteration.

    Adapters call this in a `with` block around the framework agent invocation;
    wrapped tools call `current_ctx()` / `current_faults()` to read the values.
    """
    ctx_token = _ctx.set(ctx)
    faults_token = _faults.set(tuple(faults))
    try:
        yield
    finally:
        _ctx.reset(ctx_token)
        _faults.reset(faults_token)


def current_ctx() -> FaultContext | None:
    return _ctx.get()


def current_faults() -> tuple[Fault, ...]:
    return _faults.get() or ()
