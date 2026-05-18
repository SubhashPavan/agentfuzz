"""A minimal example: a toy support-triage agent under fault injection.

The "agent" here is a 10-line Python function — agentfuzz works on anything
shaped like a callable. The point is to show the fault-injection lifecycle
without dragging in a framework.

Run:
    python examples/toy_support_agent.py
"""
from __future__ import annotations

import random
from pathlib import Path
from typing import Any

from agentfuzz import Harness, faults
from agentfuzz.adapters import CallableAdapter


def lookup_order(order_id: str) -> dict[str, Any]:
    """Pretend tool: returns a fake order record."""
    return {
        "order_id": order_id,
        "status": random.choice(["shipped", "processing", "delayed"]),
        "amount": 89.99,
        "customer_email": "jane@example.com",
    }


def issue_refund(order_id: str, amount: float) -> dict[str, Any]:
    return {"refund_id": f"r_{random.randrange(10_000)}", "order_id": order_id, "amount": amount}


def _require(d: Any, *keys: str) -> dict[str, Any]:
    """Strict tool-result parser. Real agents have this kind of check; the
    failures it surfaces are exactly what agentfuzz is designed to find."""
    if not isinstance(d, dict):
        raise TypeError(f"expected dict tool result, got {type(d).__name__}")
    for k in keys:
        if k not in d:
            raise KeyError(f"missing required field {k!r}")
    return d


def support_agent(state: dict[str, Any]) -> dict[str, Any]:
    """Toy agent: pick a tool based on prompt keywords, call it, return.

    Built defensively against a known tool contract — which means it actually
    breaks (visibly) when agentfuzz violates the contract."""
    call_tool = state["call_tool"]
    prompt = (state.get("prompt") or "").lower()

    try:
        if "refund" in prompt:
            order = _require(call_tool("lookup_order", order_id="44892"), "status", "amount")
            if order["status"] != "shipped":
                return {**state, "answer": "Cannot refund unshipped order.", "token_usage": 320}
            refund = _require(
                call_tool("issue_refund", order_id="44892", amount=order["amount"]),
                "refund_id",
            )
            return {**state, "answer": f"Refund issued: {refund['refund_id']}", "token_usage": 410}

        if "order" in prompt or "ship" in prompt:
            info = _require(call_tool("lookup_order", order_id="44892"), "status")
            return {**state, "answer": f"Order status: {info['status']}", "token_usage": 280}

        return {**state, "answer": "I can help with orders and refunds.", "token_usage": 180}
    except (TypeError, KeyError, ValueError) as exc:
        return {**state, "error": f"{type(exc).__name__}: {exc}", "token_usage": 320}


def main() -> None:
    tools = {"lookup_order": lookup_order, "issue_refund": issue_refund}
    wrapped = CallableAdapter(tools=tools).wrap(support_agent)

    harness = Harness(wrapped, scenarios="support-triage", seed=42)
    harness.add(faults.ToolTimeout(rate=0.15))
    harness.add(faults.MalformedToolResponse(rate=0.15))
    harness.add(faults.PartialToolFailure(rate=0.05))
    harness.add(faults.LatencyJitter(p50_ms=80, p99_ms=2_000))
    harness.add(faults.PromptInjection(suite="owasp-llm01", rate=0.3))
    harness.add(faults.CostSpiral(max_tokens=10_000, max_repeated_calls=6))
    harness.add(faults.RateLimitBurst(burst_probability=0.04, burst_length=3))

    result = harness.run(iterations=40)
    print(result.summary())

    out = Path("agentfuzz_reports/toy.html")
    out.parent.mkdir(parents=True, exist_ok=True)
    result.html(out)
    print(f"\nHTML report: {out}")


if __name__ == "__main__":
    main()
