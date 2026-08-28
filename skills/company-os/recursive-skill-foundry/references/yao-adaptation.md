# Yao Meta Skill Adaptation

The public `yaojingang/yao-meta-skill` repository was inspected at commit
`f5d8f681372edae1915991e2de0c23dc306dd30f`.

Company OS selectively adapts these mechanisms:

1. Description-first authoring. A trigger description is evaluated for routing
   quality before any packaging exists. In the foundry this runs as
   `eval-description` for manual authoring loops and as an automatic gate
   inside `forge`, where the candidate description is scored against the
   originating request's labeled example set before candidate acceptance.
2. Graded trigger evaluation across train, dev, and holdout splits. Authored
   examples form the train split, deterministic paraphrase, near-neighbor,
   generic, and unsafe variants form the dev split, and a fixed synthetic
   holdout split is never derived from authored examples, so repairs cannot
   overfit to it. Every split is reported with its own pass count and score,
   and a weighted `trigger_grade` summarizes the whole evaluation.
3. A deterministic maturity model for the skill lifecycle. `maturity` scores a
   skill from packaging quality, holdout triggering, installed byte integrity,
   accepted independent field receipts, and evidence diversity, and derives one
   level: `candidate`, `validated`, `project_approved`, `field_proven`,
   `core_eligible`, or `regressed` when rejected field evidence exists.

Company OS does not vendor the yao bundle, install its `yao.py` CLI, adopt its
network self-update mechanism, import its multi-platform export doctrine, or
treat its self-reported benchmark scores as evidence. The foundry keeps
Company OS validation, held-out simulation, promotion gates, content
addressing, project isolation, and authority boundaries as the controlling
layer. Maturity level `core_eligible` is a signal only: shared core promotion
still requires three independent projects, fresh independent review, and an
explicit integration change outside the foundry.
