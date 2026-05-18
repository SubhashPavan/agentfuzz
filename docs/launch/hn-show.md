# Hacker News — Show HN draft

**Title** (HN cuts off around 80 chars — keep tight):

> Show HN: agentfuzz – Chaos engineering for AI agents

(Alternatives if the above feels played out: *"Show HN: Chaos Monkey for AI
agents"*, *"Show HN: I broke my multi-agent system on purpose so you don't
have to"*.)

**URL field:**
https://github.com/SubhashPavan/agentfuzz

**Body** (HN allows ~2000 chars; tighter is better. The first 2 sentences
are what people see in the feed — don't waste them):

---

Your agent works in the demo. In production it breaks because a tool times
out, an API returns garbage JSON, a user injects a prompt, or it enters an
infinite tool-call loop burning $200 in tokens. agentfuzz finds those
failures before your users do.

It's the Chaos Monkey idea — Netflix's tool for deliberately killing prod
services to make systems resilient — applied to AI agents. You wrap your
agent (LangGraph or any callable), pick a fault profile (timeouts, malformed
JSON, prompt-injection payloads, cost spirals, schema drift, cascading
429s), and run a few hundred iterations. You get a per-fault breakdown of
what broke and why.

What's there in v0.1:
- 8 fault types informed by what I've actually seen go wrong at production
  scale across thousands of sites
- LangGraph adapter — `wrap_tools()` returns drop-in StructuredTools that
  route through the fault chain
- Plain-Python callable adapter for framework-free agents
- OWASP LLM01 prompt-injection catalog with canary-phrase leak detection
- HTML reports with per-iteration replay traces
- Deterministic (seeded), no API keys required for the demo

Why I built it: I've spent the last decade architecting AI for enterprises,
including multi-agent platforms running across 2,600+ sites. The failures
that actually hurt are almost never the ones the unit tests check for —
they're the partial, half-degraded ones in the seams between systems. I
wanted the tool I'd been wishing existed.

Apache 2.0. CrewAI / AutoGen / PydanticAI adapters are next. Feedback and
PRs very welcome.

---

**Timing:** Tuesday–Thursday, 8–10am US East / 1–3pm UK. Avoid Mondays
(weekend stories still on the page) and Fridays (low engagement).

**First-hour playbook:**
1. Post.
2. Reply to the first 3 comments within 10 minutes, even one-liners. HN
   ranks heavily on early comment velocity.
3. Don't ask friends to upvote — HN detects this and you'll be flagged.
4. If you're going to share to X / LinkedIn, do it AFTER the HN post so the
   link in those threads is the HN link, not the GitHub link directly.
   Cross-pollination feeds back into HN ranking.

**What to NOT do:**
- Don't mention "I'm doing this for a visa." HN can smell self-promotion.
  The work has to stand on its own. (Reviewers won't see the HN post; the
  endorsement letter cites stars / press / citations, not the launch tactic.)
- Don't oversell the v0.1. "Alpha" is fine. The README already sets
  expectations honestly.

**If it lands on the front page:**
- Expect 10–30k uniques in 24 hours.
- Be at your laptop replying for 4–6 hours after posting.
- Triage feedback into GitHub Issues live — visible activity drives stars.

**If it doesn't land:**
- Don't re-post the same title. HN moderates duplicates.
- Wait 2 weeks, refine the pitch based on private feedback, try once more
  with a different angle (e.g. "show HN: I ran agentfuzz against [popular
  agent library] and here's what broke" — that kind of follow-up often
  does better than the original launch).
