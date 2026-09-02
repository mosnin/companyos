# The twelve models, in full

Each entry: what the model claims, the operational move an agent makes, the
failure it prevents, and where it binds in Company OS. The concepts are the
classic general-thinking set (as popularized by the Farnam Street *Great
Mental Models* series); every word of the operationalization below is
original to Company OS.

## 1. The map is not the territory

**Claim.** Every description of reality — a document, a metric, a context
bundle — is a compression, and compressions go stale.

**Move.** Treat the ledger as the best available map and reality as the
grader. When an observation contradicts a committed document, act on the
observation and commit the correction with a message saying what reality
showed.

**Prevents.** Executing confidently against a business model, ICP, or
architecture doc that the market has already falsified.

**Binds.** `bind_context` bundles (a bundle is a sealed *map*, not a
guarantee); `record-evidence` runtime observations outrank documents;
map-correction commits are first-class work.

## 2. Circle of competence

**Claim.** Knowing the boundary of what you know is worth more than what
you know.

**Move.** Declare capability honestly on the missing → partial → runnable →
connected → verified ladder, act only inside the declared state, and
escalate — to another worker, a manager, or a human — the moment the work
crosses the boundary. Never improvise past it to look capable.

**Prevents.** Confident garbage: the expensive failure mode of an agent
guessing in a domain where it cannot check itself.

**Binds.** The capability map and evidence ladder in
`$mission-execution-control`; work admission; worker replacement (repeatedly
operating outside the circle is a replacement offense).

## 3. Falsifiability (supporting idea)

**Claim.** A claim that no observation could disprove is not knowledge; it
is decoration.

**Move.** Phrase every "done," every evaluator, and every hypothesis with
its disproof condition attached: *this is true unless X is observed; here
is where X would show up.*

**Prevents.** Text-only completion theater — the report that says "works as
expected" and cannot be wrong.

**Binds.** Executed-evidence-only acceptance (`TEXT_ONLY_OBSERVATION` is
falsifiability enforced in code); evaluator design in the
`$build-outcome-evaluators` lifecycle.

## 4. First principles thinking

**Claim.** Conclusions inherited from convention are hypotheses, not
constraints; only physics, math, and verified evidence are load-bearing.

**Move.** For any architecture or strategy decision, list the true
constraints (cost floors, latency, law, capital), discard the "how it's
usually done" layer, and rebuild the design from the constraints up. Adopt
the conventional answer only when the rebuild reproduces it.

**Prevents.** Cargo-culting an industry structure that exists for reasons
that do not apply to this company.

**Binds.** Architecture work class; route compilation;
`$middle-manager-operating-doctrine` already forces this on managers —
this entry extends it to every role.

## 5. Thought experiment

**Claim.** Many expensive questions can be answered cheaply by running them
in a model instead of in the world.

**Move.** Before committing the company to a change, run it where reversal
is free. In Company OS that place is literal: open a ledger **branch**,
draft the pivot/reorg/pricing change as an overlay, diff it against main,
and merge only what survives inspection. For smaller questions, write the
one-paragraph "suppose we did X — what breaks first?" before dispatching.

**Prevents.** Discovering the flaw in production, at full price.

**Binds.** Ledger branches (`branch_create` + human merge); pre-dispatch
reasoning on any irreversible action.

## 6. Necessity and sufficiency (supporting idea)

**Claim.** "Required for" and "enough for" are different relations, and
most bad gates confuse them.

**Move.** For every acceptance gate, write two lists: what is *necessary*
(without it, automatic fail) and what is *sufficient* (with all of it,
automatic pass). If the sufficient list is empty, the gate is a vibe, not
a gate.

**Prevents.** Shipping because all the necessary boxes were ticked — tests
pass, lint clean — when nothing sufficient (a user journey actually
completing) was ever demonstrated.

**Binds.** Checkpoint contracts; acceptance benchmarks; quality-dimension
scoring.

## 7. Second-order thinking

**Claim.** Every intervention has consequences, and the consequences have
consequences; first-order wins routinely purchase second-order losses.

**Move.** Before merging a branch, mutating the organization, or
authorizing scale, complete the sentence "and then what happens?" at least
twice: once for the system, once for the incentives of everyone (human or
agent) inside it.

**Prevents.** The pricing change that lifts revenue this quarter and
poisons the ICP next year; the process rule that fixes one incident and
slows every future mission.

**Binds.** Branch merge decisions; `$authorize-outcome-scale`; org-mutation
steps of the outcome loop.

## 8. Probabilistic thinking

**Claim.** The future arrives as distributions; point predictions are
distributions with the honesty removed.

**Move.** Attach a confidence and a base rate to every estimate ("70%,
because 4 of our last 6 integrations of this shape landed in a week").
Treat quality scores and benchmarks as noisy samples — update on them,
never worship a single reading. Choose bets by expected value with capped
downside, not by best case.

**Prevents.** Plans built on the happy path; overreacting to one green or
one red data point.

**Binds.** The planning meter's budget estimates; batched quality scoring;
innovation-bet selection.

## 9. Causation vs. correlation (supporting idea)

**Claim.** Two lines moving together is a fact about the lines, not about
the mechanism.

**Move.** Before crediting a cause ("the launch drove signups"), demand
either a mechanism you can articulate and check, or an experiment with a
control. Otherwise record the correlation as a correlation and design the
test that would settle it.

**Prevents.** Doubling down on marketing spend that coincided with — but
did not cause — growth; "fixing" a metric by breaking its proxy.

**Binds.** Evaluation work class; operator-brief economics readings; KPI
dashboards synced from the ledger.

## 10. Inversion

**Claim.** Avoiding guaranteed failure is more tractable than engineering
guaranteed success.

**Move.** At mission start, write the failure story first: "it is six
months later and this failed — why?" Convert each reason into a
what-must-not-happen entry in the goal contract, then check the plan
against that list before dispatch. Solve problems backwards from the
desired end state when the forward path is foggy.

**Prevents.** Elaborate plans that never asked what would kill them.

**Binds.** Mission bootstrap; goal contracts; risk registers in the ledger's
legal/operations views.

## 11. Occam's razor

**Claim.** Among explanations or designs that fit the evidence equally,
the one with the fewest moving parts is most likely right — and cheapest
to be wrong about.

**Move.** Generate the simple candidate first and force the complex one to
justify every additional part with evidence. When debugging, test the
simplest cause that explains *all* observations before the interesting
one.

**Prevents.** Architecture astronautics; five-service designs for
two-artifact problems; debugging the exotic before the typo.

**Binds.** Direct topology (≤2 required artifact classes compile one lane —
Occam enforced in the controller); route compilation; repair triage.

## 12. Hanlon's razor

**Claim.** Most damage is incompetence, staleness, or accident wearing a
menacing costume.

**Move.** When a system, agent, or partner does something harmful, check
the mundane explanations in order — misconfiguration, stale context, race,
timeout, ambiguous instruction — before modeling an adversary. Reserve the
adversarial hypothesis for evidence that survives the mundane sweep, and
note that security *gates* stay fail-closed regardless: Hanlon calibrates
your diagnosis, never your defenses.

**Prevents.** Burning a cycle on "the other agent is sabotaging the merge"
when the truth is a stale `base_revision`; souring human-team relations
over what a log file would have explained.

**Binds.** Repair work class; multi-agent write conflicts (stale-write
errors are concurrency, not hostility); incident postmortems.

---

## Choosing under pressure

When a decision is urgent, run the gate's bound models only (see SKILL.md
heartbeat table). When two models disagree — Occam says simple, inversion
says the simple path holds a named kill-risk — inversion wins: avoiding
the named failure outranks elegance.
