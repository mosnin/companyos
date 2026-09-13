# Council OS integration

Council OS is the advisory board above Company OS management. Its source is
https://github.com/mosnin/council-os and its installed Codex command is `$council`.
The canonical routing policy is [routing.md](routing.md). All 17 personas are
analytical perspectives, not real participants. The human owner retains authority.

The company entry point, direct-outcome director, strategy and portfolio skills,
automatically route strategic decisions to the board; managers escalate through the master. The council
skill owns task dispatch, independent recommendations, label-based peer review,
neutral synthesis and request-bound record validation. Management owns adoption.

Install Council OS via the personal Codex marketplace. Then deploy this bounded
routing update to existing Company OS distributions with:

```sh
python3 scripts/install_council_routing.py --target ~/.codex/skills
```

The installer installs the company-board role and the canonical routing section in existing entry skills,
backs up each prior file, and refuses symlinks. It does not replace unrelated skill
versions. Use distribution.py for a complete distribution upgrade. Start a new
Codex thread after installation to load the updated skills.

Verification boundaries: these routing instructions are orchestration policy,
not a new database-enforced controller transition. The offline council validator
checks completeness and request binding, not runtime authenticity or approval.
No provider calls or business decisions are made by installing this update.

The host-portable [company-board role](../../skills/company-os/company-board/SKILL.md)
provisions/reconciles the instance's persistent native board chat. Web holds business
context; the framework owns board/executive identities and the reporting loop.
Board records bind the instance, both chats, program version, and context revisions.
The local handoff validator rejects cross-instance replay and changed context;
actual native tool readback and complete Council validation remain required.
