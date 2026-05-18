from __future__ import annotations

from agentfuzz.core.context import FaultContext
from agentfuzz.core.fault import Fault

# Template-driven mutations. No LLM dependency — this keeps the fault
# deterministic and runnable without network access.
_PREFIXES = (
    "",
    "hey, ",
    "quick question — ",
    "umm, ",
    "yo, ",
    "Hi there. ",
    "Please help: ",
)
_SUFFIXES = (
    "",
    " thanks!!",
    " 🙏",
    " plz",
    " — urgent",
    " (sorry if this is the wrong place)",
)
_SUBSTITUTIONS: dict[str, list[str]] = {
    "please": ["pls", "plz"],
    "order": ["odrr", "ordr"],
    "where is": ["wheres", "where's"],
    "what is": ["whats", "what's"],
    "cannot": ["can't", "cant"],
    "I am": ["I'm", "im"],
}


class PromptParaphrase(Fault):
    """Mutate the user prompt the way real users mangle messages.

    Most agents are evaluated on clean, well-formed prompts. Production
    prompts arrive with typos, missing punctuation, casual filler, and
    multi-language code-switching. Agents that work on the eval set but
    require the user to phrase things "just so" fail silently in
    production — the user just gets a worse answer and walks away.

    This fault doesn't call an LLM (deliberately — keeps the harness
    deterministic and offline). It applies template-driven mutations:
    prefix/suffix filler, casual contractions, and optional typo
    substitutions on common phrases.

    Args:
        rate: Probability of mutating any given iteration's prompt.
        add_prefix: Whether to add a casual prefix.
        add_suffix: Whether to add a casual suffix / emoji.
        casual_substitutions: Whether to swap "please" → "pls", etc.
    """

    def __init__(
        self,
        *,
        rate: float = 0.5,
        add_prefix: bool = True,
        add_suffix: bool = True,
        casual_substitutions: bool = True,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name)
        if not 0.0 <= rate <= 1.0:
            raise ValueError(f"rate must be in [0,1], got {rate}")
        self.rate = rate
        self.add_prefix = add_prefix
        self.add_suffix = add_suffix
        self.casual_substitutions = casual_substitutions

    def on_prompt(self, ctx: FaultContext, prompt: str) -> str:
        if ctx.rng.random() >= self.rate:
            return prompt

        mutated = prompt
        if self.add_prefix:
            mutated = ctx.rng.choice(_PREFIXES) + mutated
        if self.add_suffix:
            mutated = mutated + ctx.rng.choice(_SUFFIXES)
        if self.casual_substitutions:
            for needle, replacements in _SUBSTITUTIONS.items():
                if needle in mutated.lower() and ctx.rng.random() < 0.4:
                    replacement = ctx.rng.choice(replacements)
                    # Replace case-insensitively, preserving the rest.
                    idx = mutated.lower().find(needle)
                    if idx >= 0:
                        mutated = mutated[:idx] + replacement + mutated[idx + len(needle) :]

        ctx.record("prompt_paraphrased", fault=self.name, original=prompt, mutated=mutated)
        return mutated
