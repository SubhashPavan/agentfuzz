"""The fault library — what to inject into your agent.

Faults are deliberately small. A `Fault` only overrides the hooks it needs.
Compose multiple faults on one harness to simulate realistic production
blast patterns (a flaky tool *plus* latency jitter *plus* injection attempts).
"""

from agentfuzz.faults.auth_expiry import AuthExpiry
from agentfuzz.faults.cost_spiral import CostSpiral
from agentfuzz.faults.latency_jitter import LatencyJitter
from agentfuzz.faults.malformed import MalformedToolResponse
from agentfuzz.faults.network_partition import NetworkPartition
from agentfuzz.faults.partial_failure import PartialToolFailure
from agentfuzz.faults.prompt_injection import PromptInjection
from agentfuzz.faults.prompt_paraphrase import PromptParaphrase
from agentfuzz.faults.rate_limit import RateLimitBurst
from agentfuzz.faults.schema_drift import SchemaDrift
from agentfuzz.faults.timeout import ToolTimeout

__all__ = [
    "AuthExpiry",
    "CostSpiral",
    "LatencyJitter",
    "MalformedToolResponse",
    "NetworkPartition",
    "PartialToolFailure",
    "PromptInjection",
    "PromptParaphrase",
    "RateLimitBurst",
    "SchemaDrift",
    "ToolTimeout",
]
