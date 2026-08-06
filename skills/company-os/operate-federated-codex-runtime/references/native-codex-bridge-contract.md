# Native Codex bridge contract

Contract: `company-os.codex-native-dispatch.v1`.

The bridge is a transactional outbox consumer split across two authorities:

1. PostgreSQL atomically claims a content-bound command and fences a lease
   generation. SQLite compatibility is not implemented by this bridge version.
2. The interactive host performs one native Codex operation from an exact
   compiled packet and returns raw host evidence.
3. The verifier binds the exposed thread/host identity to the exact initial
   prompt and dispatch marker.
4. PostgreSQL binds exactly one verified receipt to the prepared launch attempt.
5. The database settles the command only with that same bound receipt.

The create API has no provider idempotency key. Therefore exactly-once creation
cannot be claimed. Company OS obtains recoverable at-most-once behavior by
persisting intent, the claim, and a content-bound native launch attempt before
create; embedding a content-addressed marker in the initial prompt; and
reconciling list/read evidence before any retry. An uncertain create is
`ambiguous`, not `absent`, and blocks lease-expiry replay until it is recovered,
explicitly resolved by a future separately authorized provider-backed absence
transition, or marked conflict. The current host exposes no authenticated
snapshot/pagination watermark, so a zero-result listing is audit evidence only
and cannot abandon, requeue, or authorize another create.

Host bindings are project-local configuration. They map a Company OS project
and exact kernel digest to a native Codex target. They contain no credentials.
Database DSNs and claim tokens stay in host secrets. A binding for one project
or kernel cannot be replayed into another.
PostgreSQL also binds each Company OS project immutably to one active database
role. Every project operation checks that role before reading or mutating state;
deployments must not give one unrestricted runtime login authority over
unrelated tenant projects.

Capacity comes from the compiled manager cell. `direct_report_limit` and
`declared_worker_slots` are organizational capacity; the global admission
controller independently limits active concurrency. The bridge cannot widen
either value and never changes user, production, financial, legal, deployment,
or external-communication authority.

The packet also carries a risk-tiered execution policy. A delegated low- or
medium-risk cell may use `charter_bound_auto_continue` to eliminate a redundant
master round trip only when all exact design conditions pass: requirement
ownership and checks, disjoint writer scopes, satisfied dependencies, resolved
capabilities, no protected action or variance, and intact budget, concurrency,
and authority. Otherwise it fails closed at design. High, consequential, and
non-delegated cells always use `authenticated_master_decision`. Managers are
Luna-first, consume compact receipts rather than transcripts, and must disclose
every direct-labor exception.

## Executable transition order

`claim` → bridge `compile` → candidate `reconcile(pre_create)` →
`prepare-native-launch` → one native `create_thread` → bridge `verify` →
`recover-native-launch` with exactly that receipt → `settle`.

If native creation is uncertain, use `mark-native-launch-ambiguous`; do not
reclaim the ordinary command. After restart, use `reclaim-native-launch`, rerun
bounded candidate reconciliation, and call `recover-native-launch`. The
database binds one exact receipt and makes multiple candidates a durable
conflict. Zero evidence is recorded while the launch remains ambiguous and
blocked; self-attested listing completeness is not sufficient to requeue.
