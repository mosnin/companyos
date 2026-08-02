# Company OS Operator Command Center

## Product thesis

An autonomous company cannot be operated from raw JSON, scattered agent
threads, or activity logs. The operator needs one calm surface that answers:

1. What outcome are we pursuing?
2. Where are we in the governed journey?
3. Why did the system stop?
4. What is the one move that advances it?
5. Which work, agents, evidence, cost, and authority support that decision?

The command center is therefore a decision product, not a prettier audit dump.
It turns authoritative state into a compact human view and a versioned agent
handoff without becoming another source of truth.

## Current product signals

- OpenAI describes the Codex app as a command center for supervising multiple
  agents, reviewing progress and decisions, and organizing separate threads by
  project. This supports project isolation plus a supervisory view, not one
  giant context stream: https://openai.com/index/introducing-the-codex-app/
- ChatGPT Work lets an operator review progress, change direction, approve
  important actions, use voice, and run scheduled or triggered work. The
  command center must therefore be useful in a conversation and machine
  readable by a scheduled monitor: https://help.openai.com/en/articles/20001275-chatgpt-work-and-codex
- Workspace agent permissions remain separate from instructions; apps and
  writes retain explicit role and approval controls. A status surface must not
  imply authority or expose credentials: https://help.openai.com/en/articles/20001143

The resulting design is vision-led and evidence-informed: it borrows the
supervisory primitives while keeping Company OS's distinctive phase gates,
one-next-move discipline, evidence boundary, and fractal manager model.

## Experience contract

`company_os_controller.py brief --project <root>` renders:

- the latest governed changes and why they matter before static status;
- exactly one prioritized next action with owner, output, done condition, and
  verification;
- an outcome compass: north star, current outcome, and success metric;
- a named seven-stage track whose meaning does not depend on glyphs or color;
- only quality exceptions, with an explicit no-applicable-gate state;
- active primary and secondary work with user-visible outcomes;
- manager and agent-run accountability including phase, decision, requested
  versus observed model, and budget exceptions;
- schedule, lease, cancellation, decision authority, and certification posture;
- protected project-record update and readable-copy parity;
- immutable evidence coverage;
- aggregate cycles and coverage-aware tokens, cost, and lead time that never
  convert unknown or invalid observations into zero;
- classified blockers; and
- explicit non-claims separating requested models, local verification,
  provider evidence, and protected scheduling.

Markdown is optimized for a ChatGPT Work check-in or a terminal. JSON uses the
versioned `company-os.operator-brief.v1` schema for master/manager handoff and
monitors. Self-contained HTML provides the responsive, keyboard-operable visual
command center without a hosted service or client-side script. `--strict`
prints the same full view but exits nonzero if a governed gate is blocked.

## Safety and trust

- SQLite remains authority whenever present, even if exports are tampered.
- The projection is curated; it never serializes arbitrary control state.
- Signed grants, grant nonces, issuer material, raw provider envelopes, and
  private paths are omitted.
- Project-controlled strings are escaped into inert single-line Markdown.
- Rendering is read-only and cannot create a revision or event.
- A clean view is never represented as runtime, deployment, or production
  acceptance.

## Operator journey

1. Open the project and invoke the Company OS skill.
2. The agent reads the JSON brief rather than every skill or raw state.
3. The user sees the Markdown brief or visual HTML command center: direction,
   current stage, and one move.
4. A master delegates only the named outcome and preserves project isolation.
5. Managers report through governed phase barriers; the brief compresses their
   state without inventing progress.
6. If evidence, quality, authority, or control fails, that blocker outranks
   scheduling or new work.
7. The next check-in compares authoritative revisions and leads with what
   changed, why it matters, and the next decision.

## Deliberate constraints

- No hosted dashboard, writable UI, or multi-agent room in this slice. The
  delivery surfaces are ChatGPT Work/terminal Markdown and JSON plus a
  self-contained, responsive HTML projection with restrained motion.
- No provider launch or scheduler enablement.
- No Chippy or client integration.
- No score is rounded up because the Markdown looks polished; the independent
  quality gate must evaluate the actual journey and behavior.
