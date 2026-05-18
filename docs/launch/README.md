# Launch assets

Drafts for the v0.1 launch — keep these as starting points, edit before
posting. None of these are linked from the main README; they live here so
they're version-controlled alongside the project.

- [`hn-show.md`](hn-show.md) — Show HN post (title, body, timing, playbook).
- [`x-thread.md`](x-thread.md) — 10-tweet launch thread.
- [`blog-post.md`](blog-post.md) — long-form "The failures that actually
  break AI agents in production" essay for the portfolio site / dev.to.
- [`discord-posts.md`](discord-posts.md) — LangChain Discord, r/LocalLLaMA,
  Slack groups; with the full posting-day sequence.

## Launch-day order (recap)

| Time (US East) | Channel | What |
|---|---|---|
| Tue 9:00am | HN | Show HN post |
| Tue 11:00am | X | Launch thread, link back to HN |
| Tue 1:00pm | LangChain Discord | Direct GitHub link |
| Tue 2:00pm | r/LocalLLaMA | Direct GitHub link |
| Wed | Portfolio + dev.to | Long-form blog post |
| Thu | LinkedIn | Professional framing |
| +1 week | X | Follow-up thread (stars, issues, surprising uses) |
| +2 weeks | Framework maintainers | Reach out re: adapters |

## Pre-launch checklist

- [ ] CI is green on `main`.
- [ ] v0.1.0 git tag pushed.
- [ ] GitHub Release published (auto-triggers PyPI publish workflow).
- [ ] PyPI page renders correctly (`pip install agentfuzz` works from a
      fresh venv).
- [ ] Repo description, topics, and homepage URL set in GitHub Settings.
- [ ] Social preview image uploaded to Settings → General.
- [ ] Issues and Discussions enabled.
- [ ] At least one friendly Issue and one Discussion thread seeded
      (questions you've been asked privately, posted publicly with
      answers) — empty Issues lists make a project look dead.
