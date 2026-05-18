from __future__ import annotations

from typing import Any

from agentfuzz import Harness, faults
from agentfuzz.adapters import CallableAdapter


def _build_agent() -> Any:
    def lookup(order_id: str) -> dict[str, Any]:
        return {"order_id": order_id, "status": "shipped", "amount": 50.0}

    def agent(state: dict[str, Any]) -> dict[str, Any]:
        info = state["call_tool"]("lookup", order_id="x")
        return {**state, "answer": str(info), "token_usage": 100}

    return CallableAdapter(tools={"lookup": lookup}).wrap(agent)


def test_runs_clean_when_no_faults() -> None:
    harness = Harness(_build_agent(), scenarios=[{"prompt": "p"}])
    result = harness.run(iterations=5)
    assert result.total == 5
    assert result.passed == 5
    assert result.pass_rate == 1.0


def test_timeout_fault_blocks_some_calls() -> None:
    harness = Harness(_build_agent(), scenarios=[{"prompt": "p"}])
    harness.add(faults.ToolTimeout(rate=1.0))  # 100% timeout
    result = harness.run(iterations=10)
    # The agent doesn't crash on a timeout dict, so the iterations still
    # "pass" in the no-explicit-success-predicate sense — but every iteration
    # should have ToolTimeout attributed as a triggered fault.
    triggered = [it for it in result.iterations if "ToolTimeout" in it.triggered_faults]
    assert len(triggered) == 10


def test_cost_spiral_tags_infinite_loop() -> None:
    def loopy(state: dict[str, Any]) -> dict[str, Any]:
        for _ in range(10):
            state["call_tool"]("lookup", order_id="x")
        return {**state, "answer": "done", "token_usage": 100}

    wrapped = CallableAdapter(
        tools={"lookup": lambda order_id: {"ok": True, "id": order_id}}
    ).wrap(loopy)
    harness = Harness(wrapped, scenarios=[{"prompt": "p"}])
    harness.add(faults.CostSpiral(max_tokens=10_000, max_repeated_calls=5))
    result = harness.run(iterations=3)
    assert result.failed == 3
    for it in result.iterations:
        assert "infinite_loop_suspect" in it.tags


def test_malformed_response_mutates_results() -> None:
    harness = Harness(_build_agent(), scenarios=[{"prompt": "p"}])
    harness.add(faults.MalformedToolResponse(rate=1.0))
    result = harness.run(iterations=10)
    assert any("MalformedToolResponse" in it.triggered_faults for it in result.iterations)


def test_prompt_injection_canary_detection() -> None:
    def leaky_agent(state: dict[str, Any]) -> dict[str, Any]:
        # A naïve agent that echoes the prompt — this WILL leak any canary.
        return {**state, "answer": state["prompt"], "token_usage": 50}

    wrapped = CallableAdapter().wrap(leaky_agent)
    harness = Harness(wrapped, scenarios=[{"prompt": "hello"}])
    harness.add(faults.PromptInjection(suite="owasp-llm01", rate=1.0))
    result = harness.run(iterations=5)
    assert any("injection_leak_suspect" in it.tags for it in result.iterations)


def test_deterministic_with_seed() -> None:
    h1 = Harness(_build_agent(), scenarios=[{"prompt": "p"}], seed=7)
    h1.add(faults.ToolTimeout(rate=0.5))
    r1 = h1.run(iterations=20)

    h2 = Harness(_build_agent(), scenarios=[{"prompt": "p"}], seed=7)
    h2.add(faults.ToolTimeout(rate=0.5))
    r2 = h2.run(iterations=20)

    triggers_1 = [tuple(it.triggered_faults) for it in r1.iterations]
    triggers_2 = [tuple(it.triggered_faults) for it in r2.iterations]
    assert triggers_1 == triggers_2
