"""LangGraph adapter.

Design
------
LangGraph doesn't give us a state hook at tool invocation time, so we use a
contextvar (see `agentfuzz.core.runtime`) to share the active `FaultContext`
between the harness and tool wrappers. Three pieces:

  * `wrap_tools(tools)` returns a list of LangChain `BaseTool` instances that
    proxy through the agentfuzz fault chain. Users build their graph with
    these instead of the originals — they have the same name, schema, and
    description, so `create_react_agent` / `ToolNode` accept them unchanged.

  * `LangGraphAdapter(graph)` adapts a compiled LangGraph runnable to the
    harness's `AgentCallable` interface. It sets the contextvar on entry,
    invokes the graph, records the final message text, and unbinds on exit.

  * Async tools are supported transparently — the proxy's `_arun` routes
    through `ainvoke` on the underlying tool when available.

Usage
-----
    from langgraph.prebuilt import create_react_agent
    from agentfuzz import Harness, faults
    from agentfuzz.adapters.langgraph import LangGraphAdapter, wrap_tools

    fuzzed = wrap_tools([search, lookup_order])
    graph = create_react_agent(model, tools=fuzzed)

    wrapped = LangGraphAdapter(graph).wrap()
    harness = Harness(wrapped, scenarios=[{"prompt": "..."}])
    harness.add(faults.ToolTimeout(rate=0.2))
    result = harness.run(iterations=50)
"""

from __future__ import annotations

import asyncio
import inspect
import time
from collections.abc import Sequence
from typing import Any

from agentfuzz.adapters.base import Adapter, AgentCallable
from agentfuzz.core.context import ToolCall, ToolResult
from agentfuzz.core.fault import Fault
from agentfuzz.core.harness import compose_tool_call, compose_tool_result
from agentfuzz.core.runtime import active_run, current_ctx, current_faults


def _require_langchain_core() -> Any:
    try:
        from langchain_core.tools import BaseTool
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "agentfuzz's LangGraph adapter requires langchain-core. "
            "Install with: pip install 'agentfuzz[langgraph]'"
        ) from exc
    return BaseTool


def wrap_tools(tools: Sequence[Any]) -> list[Any]:
    """Return fault-instrumented versions of the given LangChain tools.

    Each returned tool has the same `name`, `description`, and `args_schema`
    as the original; the only difference is that invocation flows through
    agentfuzz's fault chain. Pass these to `create_react_agent`, `ToolNode`,
    or any other LangGraph construction the same way you'd pass the originals.
    """
    return [_build_fuzzed_subclass(t) for t in tools]


class LangGraphAdapter(Adapter):
    framework_name = "langgraph"

    def __init__(self, graph: Any) -> None:
        self.graph = graph

    @classmethod
    def is_available(cls) -> bool:
        try:
            import langchain_core  # noqa: F401
            import langgraph  # noqa: F401
        except ImportError:
            return False
        return True

    def wrap(self, *, faults: Sequence[Fault] | None = None) -> AgentCallable:
        # Faults come from the harness via the state dict on every iteration,
        # so the argument is accepted for interface symmetry but unused.
        del faults
        graph = self.graph

        def driven(state: dict[str, Any]) -> dict[str, Any]:
            ctx = state["_agentfuzz_ctx"]
            active_faults: Sequence[Fault] = state["_agentfuzz_faults"]
            prompt = state.get("prompt", "")

            messages_in = [{"role": "user", "content": prompt}]
            with active_run(ctx, active_faults):
                out = graph.invoke({"messages": messages_in})

            text = _final_message_text(out)
            ctx.record("final_output", text=text)
            ctx.token_usage = _sum_token_usage(out)
            return {
                **state,
                "answer": text,
                "messages": out.get("messages", []),
                "token_usage": ctx.token_usage,
            }

        return driven


def _final_message_text(graph_out: dict[str, Any]) -> str:
    msgs = graph_out.get("messages") or []
    if not msgs:
        return ""
    last = msgs[-1]
    content = getattr(last, "content", None)
    if content is None and isinstance(last, dict):
        content = last.get("content", "")
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict):
                parts.append(str(block.get("text", "")))
            else:
                parts.append(str(block))
        return "".join(parts)
    return str(content or "")


def _sum_token_usage(graph_out: dict[str, Any]) -> int:
    total = 0
    for m in graph_out.get("messages") or []:
        usage = getattr(m, "usage_metadata", None)
        if isinstance(usage, dict):
            total += int(usage.get("total_tokens", 0))
    return total


def _build_fuzzed_subclass(underlying: Any) -> Any:
    """Build a StructuredTool that proxies to `underlying` through the fault chain.

    Using StructuredTool (vs. subclassing BaseTool) sidesteps a Python class-
    body scoping issue with default-valued annotations and gives us native
    sync + async support out of the box.
    """
    BaseTool = _require_langchain_core()

    if not isinstance(underlying, BaseTool):
        raise TypeError(
            f"wrap_tools expects langchain_core BaseTool instances, "
            f"got {type(underlying).__name__}. If you have a plain function, "
            f"decorate it with @tool first."
        )

    from langchain_core.tools import StructuredTool

    def _sync_proxy(**kwargs: Any) -> Any:
        return _invoke_fuzzed(underlying, (), kwargs)

    async def _async_proxy(**kwargs: Any) -> Any:
        return await _invoke_fuzzed_async(underlying, (), kwargs)

    return StructuredTool(
        name=underlying.name,
        description=underlying.description,
        args_schema=underlying.args_schema,
        func=_sync_proxy,
        coroutine=_async_proxy,
        return_direct=underlying.return_direct,
    )


def _invoke_fuzzed(underlying: Any, args: tuple[Any, ...], kwargs: dict[str, Any]) -> Any:
    ctx = current_ctx()
    faults = current_faults()
    invoke_input = _compose_invoke_input(args, kwargs)
    if ctx is None:
        # Tool invoked outside a harness run — passthrough.
        return underlying.invoke(invoke_input)

    call = ToolCall(
        name=underlying.name,
        arguments=invoke_input,
        call_id=f"c{len(ctx.tool_calls)}",
    )
    call, short_circuit = compose_tool_call(faults, ctx, call)
    if short_circuit is not None:
        ctx.tool_results.append(short_circuit)
        return short_circuit.content

    t0 = time.perf_counter()
    result_content = underlying.invoke(call.arguments)
    elapsed_ms = (time.perf_counter() - t0) * 1000

    result = ToolResult(
        call_id=call.call_id, content=result_content, is_error=False, elapsed_ms=elapsed_ms
    )
    result = compose_tool_result(faults, ctx, call, result)
    ctx.tool_results.append(result)
    return result.content


async def _invoke_fuzzed_async(
    underlying: Any, args: tuple[Any, ...], kwargs: dict[str, Any]
) -> Any:
    ctx = current_ctx()
    faults = current_faults()
    invoke_input = _compose_invoke_input(args, kwargs)
    if ctx is None:
        if hasattr(underlying, "ainvoke") and inspect.iscoroutinefunction(underlying.ainvoke):
            return await underlying.ainvoke(invoke_input)
        return underlying.invoke(invoke_input)

    call = ToolCall(
        name=underlying.name,
        arguments=invoke_input,
        call_id=f"c{len(ctx.tool_calls)}",
    )
    call, short_circuit = compose_tool_call(faults, ctx, call)
    if short_circuit is not None:
        ctx.tool_results.append(short_circuit)
        return short_circuit.content

    t0 = time.perf_counter()
    if hasattr(underlying, "ainvoke"):
        content = await underlying.ainvoke(call.arguments)
    else:
        content = await asyncio.get_running_loop().run_in_executor(
            None, lambda: underlying.invoke(call.arguments)
        )
    elapsed_ms = (time.perf_counter() - t0) * 1000

    result = ToolResult(
        call_id=call.call_id, content=content, is_error=False, elapsed_ms=elapsed_ms
    )
    result = compose_tool_result(faults, ctx, call, result)
    ctx.tool_results.append(result)
    return result.content


def _compose_invoke_input(args: tuple[Any, ...], kwargs: dict[str, Any]) -> dict[str, Any]:
    """LangChain `BaseTool._run` is called by the parent's `invoke`, which
    has already validated the dict against `args_schema` and unpacked it as
    kwargs. Positional args generally won't appear, but handle them defensively.
    """
    if args and not kwargs:
        if len(args) == 1 and isinstance(args[0], dict):
            return dict(args[0])
        return {"__positional__": list(args)}
    return dict(kwargs)
