#!/usr/bin/env python3
from pathlib import Path

path = Path("skills/company-os/company-os/SKILL.md")
text = path.read_text(encoding="utf-8")
old = '''| Execution | Deliver approved work through Sol manager tasks and bounded Luna labor with measurable materialization, verification, and decisions | `$manage-company-program`, `$execute-bounded-task`, `$force-first-execution`, `$autonomy-suite`, `$luna-execution-fabric` |
| Elastic control | Create an isolated project operating model and improve it through independently reviewed feedback | `$elastic-company-os` |
'''
new = '''| Executive execution governor | Measure distance from the original objective, identify the global bottleneck, allocate scarce time/tokens/cost toward reality, and trigger compression/critical-path modes when execution lags | `$govern-outcome-execution` |
| Execution | Deliver work through Sol manager tasks and bounded Luna labor with early real artifacts, runtime observation, targeted rework, verification, and decisions | `$manage-company-program`, `$execute-bounded-task`, `$force-first-execution`, `$autonomy-suite`, `$luna-execution-fabric` |
| Elastic control | Create an isolated project operating model and improve it through independently reviewed feedback | `$elastic-company-os` |
'''
if old not in text:
    raise SystemExit("company-os pillar marker missing")
text = text.replace(old, new, 1)
marker = '''## Company rhythm

'''
section = '''## Outcome executive governor

For every autonomous build mission, the master runs `$govern-outcome-execution` on each meaningful heartbeat. The governor is the mission-level CEO/COO/CFO function above local managers.

Maintain an explicit **Reality Map** from the original user objective to observable capabilities. Classify the strongest state reached as R0 research/design, R1 internal primitives, R2 isolated runnable capability, R3 connected vertical behavior, R4 fresh-user usable outcome, or R5 independently accepted outcome.

The master must always name the **global bottleneck**: the missing capability whose completion most increases the probability of the original objective becoming real. Managers may optimize local work, but resources follow the global bottleneck.

For build missions, target R3 before roughly 25% of the mission resource budget is consumed. Missing that boundary is an execution incident. The master pauses broad research, speculative architecture, benchmark expansion, noncritical documentation, and governance refinement and redirects capacity to implementation, integration, runtime, and repair.

Use mission modes:

- **NORMAL:** enough discovery to act, while a real product lane starts immediately.
- **COMPRESSION:** research/design/governance shrink because reality progress is lagging burn.
- **CRITICAL_PATH:** only blockers to a fresh user-usable outcome receive substantial resources.
- **REALITY_CLOSURE:** near budget exhaustion, start nothing new; integrate, run, fix, verify, package, and checkpoint.

A green document review cannot cancel an execution incident. Reality advances from actual artifact behavior.

Prefer supplied capabilities over reimplementation. If the user provides a repository, SDK, provider, or framework that already implements a required capability, inspect, integrate, and exercise it first. A replacement requires specific blocker evidence. This prevents an agent from solving an adjacent problem because writing new infrastructure is easier than learning the requested system.

Product bytes are first-class durable state. Tested, bounded product increments should be checkpointed or committed promptly; governance records must never be more durable than the actual product they govern.

'''
if marker not in text:
    raise SystemExit("company-os rhythm marker missing")
text = text.replace(marker, section + marker, 1)
path.write_text(text, encoding="utf-8")
print("executive manager policy integrated")
