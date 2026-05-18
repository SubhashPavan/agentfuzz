from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class IterationResult:
    iteration: int
    seed: int
    passed: bool
    duration_ms: float
    token_usage: int
    tags: set[str] = field(default_factory=set)
    triggered_faults: list[str] = field(default_factory=list)
    failure_reason: str | None = None
    events: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["tags"] = sorted(self.tags)
        return d


@dataclass
class HarnessResult:
    iterations: list[IterationResult]
    fault_names: list[str]

    @property
    def total(self) -> int:
        return len(self.iterations)

    @property
    def passed(self) -> int:
        return sum(1 for i in self.iterations if i.passed)

    @property
    def failed(self) -> int:
        return self.total - self.passed

    @property
    def pass_rate(self) -> float:
        return self.passed / self.total if self.total else 0.0

    def failures_by_fault(self) -> dict[str, int]:
        counts: Counter[str] = Counter()
        for it in self.iterations:
            if it.passed:
                continue
            for f in it.triggered_faults:
                counts[f] += 1
        return dict(counts)

    def failures_by_tag(self) -> dict[str, int]:
        counts: Counter[str] = Counter()
        for it in self.iterations:
            if it.passed:
                continue
            for tag in it.tags:
                counts[tag] += 1
        return dict(counts)

    def token_spend(self) -> dict[str, float]:
        by_fault: dict[str, list[int]] = defaultdict(list)
        for it in self.iterations:
            key = ",".join(sorted(it.triggered_faults)) or "(none)"
            by_fault[key].append(it.token_usage)
        return {k: sum(v) / len(v) for k, v in by_fault.items()}

    def summary(self) -> str:
        lines = [f"agentfuzz: {self.passed}/{self.total} passed ({self.pass_rate:.0%})"]
        fbf = self.failures_by_fault()
        if fbf:
            lines.append("Failures by fault:")
            for fault, n in sorted(fbf.items(), key=lambda kv: -kv[1]):
                lines.append(f"  {fault}: {n}")
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "passed": self.passed,
            "failed": self.failed,
            "pass_rate": self.pass_rate,
            "fault_names": self.fault_names,
            "failures_by_fault": self.failures_by_fault(),
            "failures_by_tag": self.failures_by_tag(),
            "iterations": [it.to_dict() for it in self.iterations],
        }

    def json(self, path: str | Path) -> Path:
        p = Path(path)
        p.write_text(json.dumps(self.to_dict(), indent=2, default=str))
        return p

    def html(self, path: str | Path) -> Path:
        from agentfuzz.report.html import render_html_report

        return render_html_report(self, Path(path))
