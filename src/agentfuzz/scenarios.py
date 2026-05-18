"""Built-in scenario fixtures.

For v0.1 we ship a tiny built-in scenario set. v0.2 will add loaders for
tau-bench (Sierra) and WorkArena (ServiceNow) so users can run their agents
against well-known benchmarks under fault injection.
"""

from __future__ import annotations

from typing import Any

_BUILTIN: dict[str, list[dict[str, Any]]] = {
    "smoke": [
        {"prompt": "What is 2+2?", "expected_contains": "4"},
        {"prompt": "Capital of France?", "expected_contains": "Paris"},
        {"prompt": "List three primary colors.", "expected_contains": "red"},
    ],
    "support-triage": [
        {"prompt": "My order #44892 hasn't shipped. Status?"},
        {"prompt": "I want a refund for charge $89.99 on 2026-04-12."},
        {"prompt": "Reset my password please, account jane@example.com"},
        {"prompt": "Is the airport lounge open at 3am?"},
    ],
}


def load_scenarios(name: str) -> list[dict[str, Any]]:
    if name not in _BUILTIN:
        raise KeyError(f"unknown scenario suite {name!r}; available: {sorted(_BUILTIN)}")
    return [dict(s) for s in _BUILTIN[name]]


def available_suites() -> list[str]:
    return sorted(_BUILTIN)
