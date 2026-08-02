# Program 5 to 6 Transition Repair — Authoritative Application Handoff

## Status

`DRY_RUN_COMPLETE / SOURCE_REVIEW_REQUIRED / RELEASE_REQUIRED / NOT_APPLIED`

This handoff is derived read-only from the authoritative SQLite history in
`/Users/preston/Documents/Codex/company-os-core`. Candidate commit `7c96e918`
was independently rejected and is superseded by the follow-up remediation that
contains this handoff; the re-review request must name the final exact commit.
No grant was minted, no command was executed, and authoritative revision 130
was not changed.

## Exact history boundary

| Fact | Exact value |
| --- | --- |
| Project ID | `company-os-core-699e8726f6dd` |
| Source revision | `129` |
| Source program | `5` |
| Source state SHA-256 | `594bac4c13b7396ea1207be398741f29a3f63c633b87a94a76df0240f666b1fe` |
| Source program fingerprint | `0fd0db7855cdfe8f4f1c23bd89ca8487ce4d78dd31075ec58b0a74d08c91e486` |
| Transition revision | `130` |
| Replacement program | `6` |
| Transition state SHA-256 | `583ddfd5bd84795f1d87737377a39bbba8ff6d51318aaa2f45c7517e3c430c45` |
| Replacement program fingerprint | `8e35c5b9acccc5f7bec83eb8044cd0cf011380d2f52f3602049fa4b6b1160a87` |
| Transition event | `b5041210ce1b480b8dcb6a090718f937` / `program_replaced` |
| Transition ID | `program-transition-5-to-6` |
| Expected repair revision | `131` |

The retained transition reason is:

> Learning revision 127 formally rejected the non-runtime loop and adaptation
> adapt-learning-runtime-first-v1 was independently accepted

## Exact repair payload

```json
{
  "adaptation_archive_digest": "d3e5c16b745c0264ace64d9af164b7c6c18a2a09adcfb79784e6893afb335dbe",
  "candidate_state_digest": "7d4936ec90b9d88446744ccabe0cba16ea45966225cef49cbd35afa68afc77fa",
  "quality_archive_digest": "c2410146e34774950425d400b8c190070dd544ea45020389315f8dc0cc1cac4a",
  "reason": "Learning revision 127 formally rejected the non-runtime loop and adaptation adapt-learning-runtime-first-v1 was independently accepted",
  "replacement_program_version": 6,
  "runtime_archive_digest": "f924f2c8e57239e5d258ff266ad187f362c114042d5cd2d2c7f5a26dc337d19a",
  "source_program_version": 5,
  "source_state_digest": "594bac4c13b7396ea1207be398741f29a3f63c633b87a94a76df0240f666b1fe",
  "source_state_revision": 129,
  "transition_id": "program-transition-5-to-6",
  "transition_state_digest": "583ddfd5bd84795f1d87737377a39bbba8ff6d51318aaa2f45c7517e3c430c45",
  "transition_state_revision": 130,
  "transition_event": {
    "event_id": "b5041210ce1b480b8dcb6a090718f937",
    "event_payload_sha256": "95a395a5fd85f68878ccf4e6b09b344e2cfeb41faa4acf8fd27698d07e150897",
    "event_type": "program_replaced",
    "old_program_version": 5,
    "program_version": 6,
    "project_id": "company-os-core-699e8726f6dd",
    "reason": "Learning revision 127 formally rejected the non-runtime loop and adaptation adapt-learning-runtime-first-v1 was independently accepted",
    "state_revision": 130,
    "strategy_transition": {
      "source_strategy": {
        "constraints": [],
        "current_outcome": "Give a Company OS operator one exceptional decision surface for direction, stage, change, agents, evidence, quality, cost, authority, and the exact next decision",
        "non_goals": [],
        "north_star": "A self-improving company control plane that turns ambitious direction into independently verified outcomes",
        "program_fingerprint": "0fd0db7855cdfe8f4f1c23bd89ca8487ce4d78dd31075ec58b0a74d08c91e486",
        "program_updated_at": "2026-08-01T21:43:51.892678+00:00",
        "program_version": 5,
        "success_metric": "An independent product audit scores all 13 experience dimensions at least 9 out of 10, every acceptance-matrix case passes, and the view exposes no protected authority material"
      },
      "replacement_strategy": {
        "constraints": [],
        "current_outcome": "Prove one provider-authenticated Sol manager can supervise one exact GPT-5.6 Luna worker through a durable, budgeted, cancellable, restart-safe lifecycle in an isolated Company OS project",
        "non_goals": [],
        "north_star": "A self-improving company control plane that turns ambitious direction into independently verified outcomes",
        "program_fingerprint": "8e35c5b9acccc5f7bec83eb8044cd0cf011380d2f52f3602049fa4b6b1160a87",
        "program_updated_at": "2026-08-02T03:43:52.995464+00:00",
        "program_version": 6,
        "success_metric": "One authenticated Sol-to-Luna job passes exact provider/model identity, bounded token/cost/time budgets, cancellation dominance, terminal receipts, restart reconstruction, telemetry, signed reconciliation, and independent acceptance; Luna performs at least 70 percent of measured execution tokens; applicable quality scores are at least 8 and security, authority, durability, cancellation, and evidence integrity are at least 9"
      }
    },
    "strategy_transition_digest": "9ee130939cfc8cb5ad2de83212f3b945533023e861f7462fa2c9cedb207fae0c"
  }
}
```

The signed operation payload hash is:

`4a208e8799c0ca8b909c319ba8162eca35ca5b2227cece5741ac810cf4abd2c7`

## Independent reviewer boundary

The repair reviewer must be a non-empty actor different from every actor below.
These 34 exclusions were derived from retained evidence author/reviewer fields
and signed adaptation and quality grant claims:

- `benchmark-runner`
- `company-os-release-author`
- `delivery-installer-implementation`
- `evidence-recovery-integrator`
- `experience-owner`
- `external-delegation-control`
- `independent-product-scorer`
- `learning-quality-scorer`
- `learning-quality-sol-reviewer`
- `occ-v5-delivery-independent-reviewer`
- `occ-v5-delivery-independent-scorer`
- `occ-v5-learning-analysis-author`
- `occ-v5-learning-evidence-reviewer`
- `occ-v5-learning-independent-reviewer-final`
- `occ-v5-learning-independent-scorer-final`
- `occ-v5-verification-independent-reviewer`
- `occ-v5-verification-independent-scorer`
- `phase2-runtime-manager-delegation-channel`
- `phase2-sol-install-reviewer`
- `phase2-sol-installed-verification-reviewer`
- `phase2-sol-release-reviewer`
- `phase2-sol-reviewer`
- `phase2-sol-verification-author`
- `post-install-provenance-adjudicator`
- `product-research-owner`
- `program-owner`
- `root-control-auditor`
- `root-installed-verification-observer`
- `root-master-orchestrator`
- `root-product-owner`
- `root-release-authority`
- `root-release-owner`
- `root-verification-acceptance`
- `runtime-first-adaptation-sol-reviewer`

The reviewer must also be different from the implementation author and the
independent source reviewer for candidate commit `7c96e918`, so the application
decision does not collapse implementation, source acceptance, and state repair
authority into one actor.

## Grant claims schema

After source acceptance and the 0.4.3 release gate, the independent decision
issuer must sign exactly these claims. `nonce` and `expiry` are intentionally
left unset in this dry run; no grant has been minted.

```json
{
  "actor": "<independent-repair-reviewer>",
  "action": "repair-program-transition",
  "resource": "program-transition:5:6",
  "project_id": "company-os-core-699e8726f6dd",
  "program_version": 6,
  "work_id": "",
  "cycle_id": "",
  "dimension": "state-integrity",
  "decision": "archive-stale-authority",
  "payload_hash": "4a208e8799c0ca8b909c319ba8162eca35ca5b2227cece5741ac810cf4abd2c7",
  "nonce": "<new-unique-nonce>",
  "expiry": "<short-lived-future-ISO-8601>"
}
```

## Release decision

Cherry-picking `7c96e918` changes the canonical controller source but does not
change any of these version gates:

- distribution `VERSION` remains `0.4.2`;
- controller `CORE_VERSION` remains `2.6.0`;
- controller `SCHEMA_VERSION` remains `9`;
- control-store schema remains `1`.

The repair is additive and does not require a state-schema migration. However,
the candidate changes shipped `skills/company-os` bytes, which makes the
committed distribution manifest stale. Both `verify-manifest` and
`check-install --target /Users/preston/.codex/skills` fail with
`distribution manifest is stale; run write-manifest`.

Therefore **cherry-pick alone is not an accepted operational release**. A
reviewed `0.4.3` distribution release, refreshed manifest, clean detached-source
verification, and installed-copy parity are required before this new command is
used on authoritative state. Technically invoking the repository script after
only a cherry-pick would execute the new code, but doing so would bypass the
existing versioned-distribution acceptance contract and is NO-GO.

## Application sequence after the gates pass

1. Independently re-review the exact final remediation commit; stop on any P0
   or P1. Commit `7c96e918` remains unaccepted.
2. Produce and independently accept a `0.4.3` release containing the exact
   accepted source; refresh the content-addressed manifest and prove clean
   detached-source and installed-copy parity.
3. Re-read authoritative revision and require it still equals `130` with exact
   transition state digest
   `583ddfd5bd84795f1d87737377a39bbba8ff6d51318aaa2f45c7517e3c430c45`.
4. Recompute the pure repair payload and require byte-equivalence with this
   handoff and payload hash
   `4a208e8799c0ca8b909c319ba8162eca35ca5b2227cece5741ac810cf4abd2c7`.
5. Select an independent reviewer outside every excluded actor above and mint
   one short-lived grant with a new nonce.
6. Execute exactly once with stable command key
   `repair-program-transition-v5-v6-r129-r130`. Preserve the complete original
   command and signed token as the only valid retry receipt.
7. Require authoritative revision `131`, one repair event, one repair record,
   healthy store audit, empty live adaptation authority, and cleared live
   quality authority. If the result is ambiguous, retry only the byte-identical
   original command and command key; never mint a second key.
8. Keep the instance paused, scheduler off, runtime disabled, and Chippy frozen.

The eventual command shape is:

```text
python3 skills/company-os/elastic-company-os/scripts/company_os_controller.py \
  repair-program-transition \
  --project /Users/preston/Documents/Codex/company-os-core \
  --reviewer <independent-repair-reviewer> \
  --repair-grant <short-lived-signed-token> \
  --command-key repair-program-transition-v5-v6-r129-r130
```

## Expected post-application state and audit

After a valid repair, revision 131 must preserve:

- instance `paused`;
- schedule disabled and lease absent;
- runtime adapter disabled with no attempts;
- zero active/committed work, cycles, or live evidence;
- zero pending/applied live adaptations;
- all 23 live quality scores and their authority fields cleared;
- exactly one adaptation archive, one quality archive, one runtime archive,
  and one independently authorized repair record for
  `program-transition-5-to-6`;
- exactly one atomic `program_transition_repaired` event paired with the repair
  record;
- a healthy transactional-store audit.

The stale-program errors must disappear. Controller validation must remain
NO-GO because program 6 is still in `reality_audit` without valid
`evidence.reality`. It should continue to warn that the product/project reality
audit is incomplete and report the protected launcher as an external
prerequisite. The repair is not permission to activate runtime or scheduling.
