from __future__ import annotations

import time
from collections.abc import Callable, Sequence
from typing import Any

from agentfuzz.adapters.base import Adapter, AgentCallable
from agentfuzz.core.context import FaultContext, ToolCall, ToolResult
from agentfuzz.core.fault import Fault
from agentfuzz.core.harness import compose_tool_call, compose_tool_result


class CallableAdapter(Adapter):
    """The minimal adapter — for agents you've already shaped as a callable.

    Use this when you want to test a Python function directly without bringing
    in a full framework. Your agent receives the state dict (with `prompt` and
    any scenario fields) plus a `call_tool(name, **args)` helper that routes
    through agentfuzz, so faults can intervene.

    Example:
        def my_agent(state):
            answer = state["call_tool"]("search", query=state["prompt"])
            return {**state, "answer": answer}

        Harness(CallableAdapter(tools).wrap(my_agent))
    """

    framework_name = "callable"

    def __init__(self, tools: dict[str, Callable[..., Any]] | None = None) -> None:
        self.tools = tools or {}

    @classmethod
    def is_available(cls) -> bool:
        return True

    def wrap(self, agent: Any, *, faults: Sequence[Fault] | None = None) -> AgentCallable:
        # CallableAdapter reads the live fault list from the FaultContext each
        # iteration, so the `faults` argument is accepted for interface
        # symmetry with other adapters but isn't used here.
        del faults
        tools = self.tools

        def driven(state: dict[str, Any]) -> dict[str, Any]:
            ctx: FaultContext = state["_agentfuzz_ctx"]
            active_faults: Sequence[Fault] = state["_agentfuzz_faults"]

            def call_tool(name: str, **arguments: Any) -> Any:
                call = ToolCall(name=name, arguments=arguments, call_id=f"c{len(ctx.tool_calls)}")
                call, short_circuit = compose_tool_call(active_faults, ctx, call)
                if short_circuit is not None:
                    ctx.tool_results.append(short_circuit)
                    return short_circuit.content
                if name not in tools:
                    raise KeyError(f"unknown tool: {name}")
                t0 = time.perf_counter()
                content = tools[name](**call.arguments)
                elapsed = (time.perf_counter() - t0) * 1000
                result = ToolResult(
                    call_id=call.call_id, content=content, is_error=False, elapsed_ms=elapsed
                )
                result = compose_tool_result(active_faults, ctx, call, result)
                ctx.tool_results.append(result)
                return result.content

            state = {**state, "call_tool": call_tool}
            out = agent(state)

            # Record a final_output event for observer faults to inspect.
            text = out.get("answer") or out.get("output") or ""
            ctx.record("final_output", text=str(text))
            if "token_usage" in out:
                ctx.token_usage = int(out["token_usage"])
            return out

        return driven
