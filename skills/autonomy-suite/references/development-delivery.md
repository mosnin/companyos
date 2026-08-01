# Development delivery

## Change discipline

- One bounded outcome per branch or worktree; no overlapping writers on the same files without an owner.
- Require a task link, acceptance criteria, migration plan, test plan, feature flag decision, and rollback before consequential implementation.
- Keep generated artifacts, prompts, schemas, and tool policy changes reviewable and versioned.

## Review

- Use an author review, an independent evidence review, and a risk/security review for high-impact changes.
- Resolve merge conflicts by re-running affected tests and reconciling task assumptions, not by accepting the easiest diff.
- Treat migrations and integrations as separately reviewable changes.

## Rollout

- Prefer additive migrations, backward-compatible reads, feature flags, staged enablement, and measurable rollback triggers.
- Do not let automation deploy, message customers, mutate production data, or expand access without its configured approval.
- Record deployment receipt, observed health, rollback decision, and post-release follow-up in the ledger.
