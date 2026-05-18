from __future__ import annotations

import time
import traceback
from collections.abc import Callable, Sequence
from random import Random
from typing import Any

from agentfuzz.core.context import FaultContext, ToolCall, ToolResult
from agentfuzz.core.fault import Fault, FaultOutcome
from agentfuzz.core.result import HarnessResult, IterationResult

# An agent is anything callable that takes a state dict (with at least a
# "prompt" key) and returns a state dict. Framework adapters wrap real agents
# behind this interface.
AgentCallable = Callable[[dict[str, Any]], dict[str, Any]]

# A success predicate takes the final state and returns whether the iteration
# passed. Default is "no exception raised". Users can supply a stricter check.
SuccessPredicate = Callable[[dict[str, Any]], bool]


def _default_success(state: dict[str, Any]) -> bool:
    return state.get("error") is None


class Harness:
    """Drive an agent through many fault-injected iterations.

    Lifecycle of one iteration:
        1. Build a FaultContext for this iteration (deterministic via seed).
        2. Notify every fault: on_iteration_start.
        3. Run prompt mutations: every fault.on_prompt in order.
        4. Invoke the agent. Tool calls flow through compose_tool_call /
           compose_tool_result, which let each fault inspect & mutate.
        5. Notify every fault: on_iteration_end (lets faults tag failures
           detected post-hoc, e.g. cost spirals).
        6. Decide pass/fail using the success predicate.

    The harness does not catch fault-induced exceptions silently — it records
    them as failures with the offending fault attributed.
    """

    def __init__(
        self,
        agent: AgentCallable,
        *,
        scenarios: Sequence[dict[str, Any]] | str | None = None,
        success: SuccessPredicate = _default_success,
        seed: int = 0xA9E47,
    ) -> None:
        self.agent = agent
        self.scenarios = _resolve_scenarios(scenarios)
        self.success = success
        self.seed = seed
        self._faults: list[Fault] = []

    def add(self, fault: Fault) -> Harness:
        self._faults.append(fault)
        return self

    def remove(self, fault: Fault | str) -> None:
        if isinstance(fault, str):
            self._faults = [f for f in self._faults if f.name != fault]
        else:
            self._faults.remove(fault)

    @property
    def faults(self) -> list[Fault]:
        return list(self._faults)

    def run(
        self,
        *,
        iterations: int = 50,
        scenarios: Sequence[dict[str, Any]] | str | None = None,
    ) -> HarnessResult:
        scenarios_used = _resolve_scenarios(scenarios) if scenarios is not None else self.scenarios
        master_rng = Random(self.seed)
        results: list[IterationResult] = []

        for i in range(iterations):
            iter_seed = master_rng.randrange(2**31)
            scenario = scenarios_used[i % len(scenarios_used)] if scenarios_used else {}
            results.append(self._run_one(i, iter_seed, scenario))

        return HarnessResult(iterations=results, fault_names=[f.name for f in self._faults])

    def _run_one(self, iteration: int, seed: int, scenario: dict[str, Any]) -> IterationResult:
        ctx = FaultContext(iteration=iteration, seed=seed)
        for f in self._faults:
            f.on_iteration_start(ctx)

        start = time.perf_counter()
        passed = False
        failure_reason: str | None = None

        try:
            prompt = scenario.get("prompt", "")
            for f in self._faults:
                prompt = f.on_prompt(ctx, prompt)

            state: dict[str, Any] = {
                **scenario,
                "prompt": prompt,  # mutated prompt must override scenario's original
                "_agentfuzz_ctx": ctx,
                "_agentfuzz_faults": self._faults,
            }
            final = self.agent(state)
            passed = bool(self.success(final))
            if not passed:
                failure_reason = str(final.get("error") or "success predicate returned False")
        except Exception as exc:
            failure_reason = f"{type(exc).__name__}: {exc}"
            ctx.record("exception", traceback=traceback.format_exc())

        for f in self._faults:
            f.on_iteration_end(ctx)

        # If a fault tagged this as a failure (cost spiral, infinite loop,
        # injection success), respect that even if the agent didn't raise.
        if "fault_triggered_failure" in ctx.tags:
            passed = False

        duration_ms = (time.perf_counter() - start) * 1000
        triggered = sorted(
            {
                ev["fault"]
                for ev in ctx.events
                if ev.get("type") in {"fault_mutated", "fault_blocked"} and "fault" in ev
            }
        )

        return IterationResult(
            iteration=iteration,
            seed=seed,
            passed=passed,
            duration_ms=duration_ms,
            token_usage=ctx.token_usage,
            tags=set(ctx.tags),
            triggered_faults=triggered,
            failure_reason=failure_reason,
            events=ctx.events,
        )


# Public helpers used by adapters to push tool calls / results through the
# fault chain. Keeping these here (not in fault.py) avoids circular imports
# and makes the lifecycle visible in one place.


def compose_tool_call(
    faults: Sequence[Fault], ctx: FaultContext, call: ToolCall
) -> tuple[ToolCall, ToolResult | None]:
    """Run a tool call through every fault's on_tool_call hook.

    Returns (call, short_circuit_result). If short_circuit_result is not None,
    the adapter must NOT execute the real tool; it should use the synthesized
    result directly. This is how timeouts, blocked calls, and malformed
    pre-execution responses are simulated.
    """
    current_call = call
    for f in faults:
        decision = f.on_tool_call(ctx, current_call)
        if decision.outcome is FaultOutcome.PASSTHROUGH:
            continue
        if decision.outcome is FaultOutcome.MUTATED and decision.mutated_arguments is not None:
            current_call = ToolCall(
                name=current_call.name,
                arguments=decision.mutated_arguments,
                call_id=current_call.call_id,
            )
            ctx.record("fault_mutated", fault=f.name, reason=decision.reason)
        elif decision.outcome is FaultOutcome.BLOCKED:
            ctx.record("fault_blocked", fault=f.name, reason=decision.reason)
            return current_call, decision.mutated_result
    return current_call, None


def compose_tool_result(
    faults: Sequence[Fault], ctx: FaultContext, call: ToolCall, result: ToolResult
) -> ToolResult:
    """Run a tool result through every fault's on_tool_result hook."""
    current = result
    for f in faults:
        decision = f.on_tool_result(ctx, call, current)
        if decision.outcome is FaultOutcome.PASSTHROUGH:
            continue
        if decision.mutated_result is not None:
            current = decision.mutated_result
            ctx.record("fault_mutated", fault=f.name, reason=decision.reason)
    return current


def _resolve_scenarios(
    scenarios: Sequence[dict[str, Any]] | str | None,
) -> list[dict[str, Any]]:
    if scenarios is None:
        return []
    if isinstance(scenarios, str):
        from agentfuzz.scenarios import load_scenarios

        return load_scenarios(scenarios)
    return list(scenarios)
