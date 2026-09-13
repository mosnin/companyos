<!-- council-os:begin -->
## Board and executive conversations

Company OS owns **owner → board → executives → managers → workers**. Company OS
Web stores business context. At startup/resume the entry conversation loads
`company-board` (`skills/company-os/company-board/SKILL.md` from this distribution)
and reconciles the instance's board conversation in its host project.

The board creates executive conversations with `company-executive`; executives
create manager conversations; managers create Luna worker conversations. Every
management role has its own native thread in the same host project, with explicit
parent/return IDs and message acknowledgements. Executives and managers use
`gpt-6-astra` at `medium` reasoning; workers retain `gpt-5.6-luna`.

Consult `$council` inside the board on strategic direction, major roadmap/resource
changes, pivots/stops and executive conflict. Bind its 17-member deliberation to
the instance, responsible executive, program version and Web context revisions.
Executives record disposition, apply existing dispatch rules, and report measured
results back to the board. Routine work under accepted direction continues.

Follow `company-board` for provisioning and reconciliation. Human authority and
existing execution gates remain; appointments do not enable feature-off schedulers
or permit direct board-to-worker dispatch. Report unavailable host capabilities
honestly. An explicit human waiver is recorded as a waiver, not a council result.
<!-- council-os:end -->
