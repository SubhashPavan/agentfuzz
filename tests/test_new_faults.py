"""Tests for the v0.2 fault additions: AuthExpiry, NetworkPartition, PromptParaphrase."""

from __future__ import annotations

from typing import Any

import pytest

from agentfuzz import Harness, faults
from agentfuzz.adapters import CallableAdapter


def _agent_with_lookup() -> Any:
    def lookup(order_id: str) -> dict[str, Any]:
        return {"order_id": order_id, "status": "shipped"}

    def agent(state: dict[str, Any]) -> dict[str, Any]:
        info = state["call_tool"]("lookup", order_id="x")
        return {**state, "answer": str(info), "token_usage": 50}

    return CallableAdapter(tools={"lookup": lookup}).wrap(agent)


def test_auth_expiry_returns_401_envelope() -> None:
    harness = Harness(_agent_with_lookup(), scenarios=[{"prompt": "p"}])
    harness.add(faults.AuthExpiry(rate=1.0, status=401))
    result = harness.run(iterations=10)
    assert all("AuthExpiry" in it.triggered_faults for it in result.iterations)


def test_auth_expiry_supports_403() -> None:
    fault = faults.AuthExpiry(rate=1.0, status=403)
    assert fault.status == 403


def test_auth_expiry_rejects_bad_status() -> None:
    with pytest.raises(ValueError):
        faults.AuthExpiry(rate=1.0, status=500)


def test_network_partition_raises_by_default() -> None:
    harness = Harness(_agent_with_lookup(), scenarios=[{"prompt": "p"}])
    harness.add(faults.NetworkPartition(rate=1.0))
    result = harness.run(iterations=5)
    for it in result.iterations:
        assert not it.passed
        assert it.failure_reason is not None
        assert "ConnectionError" in it.failure_reason


def test_network_partition_as_result_envelope() -> None:
    harness = Harness(_agent_with_lookup(), scenarios=[{"prompt": "p"}])
    harness.add(faults.NetworkPartition(rate=1.0, as_result=True))
    result = harness.run(iterations=5)
    # In as_result mode, the agent gets a dict with 'error': 'connection refused'
    # — it doesn't crash, but NetworkPartition is attributed to the iteration.
    assert all("NetworkPartition" in it.triggered_faults for it in result.iterations)


def test_prompt_paraphrase_mutates_prompt() -> None:
    seen_mutations: list[str] = []

    def echo_agent(state: dict[str, Any]) -> dict[str, Any]:
        seen_mutations.append(state["prompt"])
        return {**state, "answer": state["prompt"], "token_usage": 10}

    wrapped = CallableAdapter().wrap(echo_agent)
    harness = Harness(wrapped, scenarios=[{"prompt": "Where is my order please"}])
    harness.add(faults.PromptParaphrase(rate=1.0))
    harness.run(iterations=10)
    # At least some iterations should have been mutated away from the original.
    assert any(m != "Where is my order please" for m in seen_mutations)


def test_prompt_paraphrase_records_event() -> None:
    def agent(state: dict[str, Any]) -> dict[str, Any]:
        return {**state, "answer": "ok", "token_usage": 10}

    wrapped = CallableAdapter().wrap(agent)
    harness = Harness(wrapped, scenarios=[{"prompt": "please help"}])
    harness.add(faults.PromptParaphrase(rate=1.0))
    result = harness.run(iterations=5)
    paraphrased_events = [
        ev for it in result.iterations for ev in it.events if ev["type"] == "prompt_paraphrased"
    ]
    assert len(paraphrased_events) >= 1
