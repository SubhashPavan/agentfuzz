"""AutoGen v0.4+ adapter.

AutoGen v0.4+ ships a different tool model from CrewAI and LangChain:
`autogen_core.tools.FunctionTool` builds its OpenAI-function-call schema
from the *typed signature* of the wrapped Python function. There is no
`_run` override hook; the framework calls the underlying `func` directly.

Wrap strategy:

  * Instead of subclassing, we build a new `FunctionTool` whose underlying
    callable is a proxy that has the same signature as the user's tool
    (achieved via `functools.wraps`, which AutoGen's
    `inspect.signature(..., follow_wrapped=True)` honors).
  * The proxy routes every invocation through agentfuzz's fault chain
    using the contextvar runtime (`agentfuzz.core.runtime.active_run`).

Both sync and async tools are supported — the proxy is async when the
original is async, sync otherwise.

Usage
-----
    from autogen_agentchat.agents import AssistantAgent
    from autogen_core.tools import FunctionTool
    from agentfuzz import Harness, faults
    from agentfuzz.adapters.autogen import AutoGenAdapter, wrap_tools

    fuzzed = wrap_tools([FunctionTool(my_func, description="...")])
    agent = AssistantAgent("helper", model_client=my_llm, tools=fuzzed)

    wrapped = AutoGenAdapter(agent).wrap()
    harness = Harness(wrapped, scenarios=[{"prompt": "..."}])
    harness.add(faults.ToolTimeout(rate=0.2))
    result = harness.run(iterations=50)

Status: alpha. wrap_tools is exercised by tests. The full AutoGenAdapter
agent-loop path requires a tool-calling model client; the deterministic
fake-client integration test is a v0.3.x follow-up.
"""

from __future__ import annotations

import asyncio
import functools
import inspect
import time
from collections.abc import Sequence
from typing import Any

from agentfuzz.adapters.base import Adapter, AgentCallable
from agentfuzz.core.context import ToolCall, ToolResult
from agentfuzz.core.fault import Fault
from agentfuzz.core.harness import compose_tool_call, compose_tool_result
from agentfuzz.core.runtime import active_run, current_ctx, current_faults


def _require_autogen() -> Any:
    try:
        from autogen_core.tools import FunctionTool
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "agentfuzz's AutoGen adapter requires autogen-core. "
            "Install with: pip install 'agentfuzz[autogen]'"
        ) from exc
    return FunctionTool


def wrap_tools(tools: Sequence[Any]) -> list[Any]:
    """Return fault-instrumented versions of the given AutoGen FunctionTools.

    Each returned tool has the same name, description, and schema as the
    original; the only difference is that invocation flows through
    agentfuzz's fault chain. Pass these to your `AssistantAgent(tools=...)`
    exactly as you would the originals.
    """
    return [_build_autogen_proxy(t) for t in tools]


class AutoGenAdapter(Adapter):
    framework_name = "autogen"

    def __init__(self, agent: Any) -> None:
        """Wrap an AutoGen agent or team for the harness.

        Args:
            agent: Anything that exposes an async `run(task=...)` method
                returning a `TaskResult` (so AssistantAgent, RoundRobinGroupChat,
                SocietyOfMindAgent, etc. all work).
        """
        self.agent = agent

    @classmethod
    def is_available(cls) -> bool:
        try:
            import autogen_agentchat  # noqa: F401
            import autogen_core  # noqa: F401
        except ImportError:
            return False
        return True

    def wrap(self, *, faults: Sequence[Fault] | None = None) -> AgentCallable:
        del faults  # interface symmetry; faults come from the state dict
        agent = self.agent

        def driven(state: dict[str, Any]) -> dict[str, Any]:
            ctx = state["_agentfuzz_ctx"]
            active_faults: Sequence[Fault] = state["_agentfuzz_faults"]
            prompt = state.get("prompt", "")

            with active_run(ctx, active_faults):
                # AutoGen's run is async-only; bridge to sync via asyncio.run.
                # If we're already in an event loop, run on it.
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        # Edge case: harness called from inside an async context.
                        # Schedule and wait via run_until_complete fails, so use
                        # a fresh loop in a thread (rare path; tests don't hit it).
                        result = asyncio.run_coroutine_threadsafe(
                            agent.run(task=prompt), loop
                        ).result()
                    else:
                        result = asyncio.run(agent.run(task=prompt))
                except RuntimeError:
                    result = asyncio.run(agent.run(task=prompt))

            text = _task_result_text(result)
            ctx.record("final_output", text=text)
            ctx.token_usage = _task_result_tokens(result)
            return {
                **state,
                "answer": text,
                "token_usage": ctx.token_usage,
                "task_result": result,
            }

        return driven


def _task_result_text(task_result: Any) -> str:
    """Extract the final string from an AutoGen TaskResult."""
    messages = getattr(task_result, "messages", None) or []
    if not messages:
        return ""
    last = messages[-1]
    content = getattr(last, "content", None)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(str(c) for c in content)
    return str(last)


def _task_result_tokens(task_result: Any) -> int:
    """Sum token usage from an AutoGen TaskResult when reported."""
    total = 0
    for m in getattr(task_result, "messages", None) or []:
        usage = getattr(m, "models_usage", None)
        if usage is not None:
            prompt_tokens = getattr(usage, "prompt_tokens", 0) or 0
            completion_tokens = getattr(usage, "completion_tokens", 0) or 0
            total += int(prompt_tokens) + int(completion_tokens)
    return total


def _build_autogen_proxy(underlying: Any) -> Any:
    """Build a new FunctionTool whose underlying callable proxies through
    the agentfuzz fault chain. Preserves name, description, and schema."""
    FunctionTool = _require_autogen()

    if not isinstance(underlying, FunctionTool):
        raise TypeError(
            f"wrap_tools expects autogen_core.tools.FunctionTool instances, "
            f"got {type(underlying).__name__}. Build one with "
            f"FunctionTool(your_func, description='...')."
        )

    # Read the underlying Python function. The attribute is technically
    # private but the only access path AutoGen provides.
    original_func = underlying._func
    tool_name = underlying.name
    is_async = asyncio.iscoroutinefunction(original_func)

    # We always emit an async proxy regardless of whether the original is
    # sync or async. AutoGen's FunctionTool routes sync funcs through
    # `loop.run_in_executor`, which does NOT propagate contextvars to the
    # executor thread — so our fault context would be invisible. Making the
    # proxy async keeps the call in the originating task and the contextvar
    # works. Sync underlying funcs are invoked directly inside our proxy;
    # they'll block the loop for their own duration, but that's the same
    # behavior as any sync call inside an async coroutine.
    @functools.wraps(original_func)
    async def proxy(**kwargs: Any) -> Any:
        return await _invoke_fuzzed_async(original_func, tool_name, kwargs, is_async=is_async)

    return FunctionTool(
        proxy,
        description=underlying.description,
        name=tool_name,
    )


async def _invoke_fuzzed_async(
    original_func: Any, tool_name: str, kwargs: dict[str, Any], *, is_async: bool
) -> Any:
    ctx = current_ctx()
    faults = current_faults()
    if ctx is None:
        if is_async:
            return await original_func(**kwargs)
        return original_func(**kwargs)

    call = ToolCall(
        name=tool_name,
        arguments=dict(kwargs),
        call_id=f"c{len(ctx.tool_calls)}",
    )
    call, short_circuit = compose_tool_call(faults, ctx, call)
    if short_circuit is not None:
        ctx.tool_results.append(short_circuit)
        return short_circuit.content

    t0 = time.perf_counter()
    if is_async:
        content = await original_func(**call.arguments)
    else:
        content = original_func(**call.arguments)
    elapsed_ms = (time.perf_counter() - t0) * 1000

    result = ToolResult(
        call_id=call.call_id, content=content, is_error=False, elapsed_ms=elapsed_ms
    )
    result = compose_tool_result(faults, ctx, call, result)
    ctx.tool_results.append(result)
    return result.content


# Make the proxy machinery importable for use by `inspect.signature` introspection.
_ = inspect  # keep ruff happy about the import (used at module init)
