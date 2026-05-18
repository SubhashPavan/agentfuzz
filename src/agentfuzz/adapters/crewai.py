"""CrewAI adapter.

CrewAI ships its own `BaseTool` (`crewai.tools.BaseTool`) — not LangChain's
— so we need a separate wrap path. Same shape as the LangGraph adapter:

  * `wrap_tools(tools)` returns proxy `crewai.tools.BaseTool` instances that
    route every invocation through agentfuzz's fault chain. Pass them to
    your `Agent(tools=[...])` instead of the originals.

  * `CrewAIAdapter(crew)` invokes the crew via `crew.kickoff(inputs=...)`,
    threading the active `FaultContext` through the contextvar-based
    runtime in `agentfuzz.core.runtime`.

Async tools are supported via `_arun`. The integration is intentionally
small — CrewAI's `run()` is just a thin wrapper over `_run`, so overriding
that one method puts every dispatch through our hook.

Usage
-----
    from crewai import Agent, Crew, Task
    from agentfuzz import Harness, faults
    from agentfuzz.adapters.crewai import CrewAIAdapter, wrap_tools

    fuzzed = wrap_tools([my_crewai_tool])
    agent = Agent(role="...", goal="...", backstory="...", tools=fuzzed, llm=my_llm)
    crew = Crew(agents=[agent], tasks=[Task(...)])

    wrapped = CrewAIAdapter(crew).wrap()
    harness = Harness(wrapped, scenarios=[{"prompt": "..."}])
    harness.add(faults.MalformedToolResponse(rate=0.1))
    result = harness.run(iterations=50)

Status: alpha. The wrap_tools path is exercised by tests; the full
CrewAIAdapter crew-loop path is structurally complete but the end-to-end
integration test (with a deterministic fake LLM in CrewAI's LiteLLM layer)
is a follow-up. Run it against a real LLM and file issues if behavior
drifts from the LangGraph adapter.
"""

from __future__ import annotations

import time
from collections.abc import Sequence
from typing import Any

from agentfuzz.adapters.base import Adapter, AgentCallable
from agentfuzz.core.context import ToolCall, ToolResult
from agentfuzz.core.fault import Fault
from agentfuzz.core.harness import compose_tool_call, compose_tool_result
from agentfuzz.core.runtime import active_run, current_ctx, current_faults


def _require_crewai() -> Any:
    try:
        from crewai.tools import BaseTool
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "agentfuzz's CrewAI adapter requires crewai. "
            "Install with: pip install 'agentfuzz[crewai]'"
        ) from exc
    return BaseTool


def wrap_tools(tools: Sequence[Any]) -> list[Any]:
    """Return fault-instrumented versions of the given CrewAI tools.

    Each returned tool has the same `name`, `description`, and `args_schema`
    as the original; the only difference is that invocation flows through
    agentfuzz's fault chain. Pass these to `Agent(tools=...)` exactly as
    you would the originals.
    """
    return [_build_crewai_proxy(t) for t in tools]


class CrewAIAdapter(Adapter):
    framework_name = "crewai"

    def __init__(self, crew: Any, *, prompt_key: str = "prompt") -> None:
        """Wrap a CrewAI Crew for the harness.

        Args:
            crew: A `crewai.Crew` instance whose tasks reference `{prompt_key}`
                in their description templates.
            prompt_key: The variable name to substitute the harness prompt
                under, when calling `crew.kickoff(inputs=...)`.
        """
        self.crew = crew
        self.prompt_key = prompt_key

    @classmethod
    def is_available(cls) -> bool:
        try:
            import crewai  # noqa: F401
        except ImportError:
            return False
        return True

    def wrap(self, *, faults: Sequence[Fault] | None = None) -> AgentCallable:
        del faults  # interface symmetry; faults come from the state dict
        crew = self.crew
        prompt_key = self.prompt_key

        def driven(state: dict[str, Any]) -> dict[str, Any]:
            ctx = state["_agentfuzz_ctx"]
            active_faults: Sequence[Fault] = state["_agentfuzz_faults"]
            prompt = state.get("prompt", "")

            with active_run(ctx, active_faults):
                out = crew.kickoff(inputs={prompt_key: prompt})

            text = _result_text(out)
            ctx.record("final_output", text=text)
            ctx.token_usage = _result_tokens(out)
            return {
                **state,
                "answer": text,
                "token_usage": ctx.token_usage,
                "crew_output": out,
            }

        return driven


def _result_text(out: Any) -> str:
    """Extract the final string from a CrewAI kickoff result.

    CrewAI returns a `CrewOutput`-like object; `.raw` is the typical string
    field, but older versions exposed `.result` or just stringified the
    whole object. Be lenient.
    """
    for attr in ("raw", "result", "output"):
        val = getattr(out, attr, None)
        if isinstance(val, str) and val:
            return val
    return str(out)


def _result_tokens(out: Any) -> int:
    """Sum token usage from a CrewAI result, when reported."""
    usage = getattr(out, "token_usage", None)
    if usage is None:
        return 0
    total = getattr(usage, "total_tokens", None)
    if isinstance(total, int):
        return total
    if isinstance(usage, dict):
        return int(usage.get("total_tokens", 0))
    return 0


def _build_crewai_proxy(underlying: Any) -> Any:
    """Build a CrewAI BaseTool subclass that proxies to `underlying`.

    We define the proxy class inside a function and capture `underlying`
    via closure on the `_run` method — avoiding the class-body annotation
    scoping pitfall (the same one the LangGraph adapter sidesteps).
    """
    BaseTool = _require_crewai()

    if not isinstance(underlying, BaseTool):
        raise TypeError(
            f"wrap_tools expects crewai.tools.BaseTool instances, got "
            f"{type(underlying).__name__}. Use the @tool decorator from "
            f"crewai.tools, or pass an instance of crewai.tools.BaseTool."
        )

    def _run_impl(self: Any, *args: Any, **kwargs: Any) -> Any:
        return _invoke_fuzzed(underlying, args, kwargs)

    async def _arun_impl(self: Any, *args: Any, **kwargs: Any) -> Any:
        return await _invoke_fuzzed_async(underlying, args, kwargs)

    proxy_cls = type(
        f"Fuzzed_{type(underlying).__name__}",
        (BaseTool,),
        {"_run": _run_impl, "_arun": _arun_impl},
    )

    return proxy_cls(
        name=underlying.name,
        description=underlying.description,
        args_schema=underlying.args_schema,
    )


def _invoke_fuzzed(underlying: Any, args: tuple[Any, ...], kwargs: dict[str, Any]) -> Any:
    ctx = current_ctx()
    faults = current_faults()
    invoke_input = _compose_invoke_input(args, kwargs)
    if ctx is None:
        # Tool invoked outside a harness run — passthrough.
        return underlying.run(**invoke_input) if invoke_input else underlying.run()

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
    content = underlying.run(**call.arguments) if call.arguments else underlying.run()
    elapsed_ms = (time.perf_counter() - t0) * 1000

    result = ToolResult(
        call_id=call.call_id, content=content, is_error=False, elapsed_ms=elapsed_ms
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
        if hasattr(underlying, "arun"):
            return await underlying.arun(**invoke_input)
        return underlying.run(**invoke_input) if invoke_input else underlying.run()

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
    if hasattr(underlying, "arun"):
        content = await underlying.arun(**call.arguments)
    else:
        content = underlying.run(**call.arguments) if call.arguments else underlying.run()
    elapsed_ms = (time.perf_counter() - t0) * 1000

    result = ToolResult(
        call_id=call.call_id, content=content, is_error=False, elapsed_ms=elapsed_ms
    )
    result = compose_tool_result(faults, ctx, call, result)
    ctx.tool_results.append(result)
    return result.content


def _compose_invoke_input(args: tuple[Any, ...], kwargs: dict[str, Any]) -> dict[str, Any]:
    """Normalize CrewAI's `_run(*args, **kwargs)` call shape to a dict."""
    if args and not kwargs:
        if len(args) == 1 and isinstance(args[0], dict):
            return dict(args[0])
        return {"__positional__": list(args)}
    return dict(kwargs)
