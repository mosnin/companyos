---
name: navigation-control
description: Internal navigation mechanism of the Company OS dispatch loop. mission-execution-control evaluates it programmatically on every boundary to treat research, audits, tests, and runtime evidence as sensors, choose the highest-value safe action, and stop sensor/document spirals. Use when inspecting, tuning, or extending the navigation decision itself — not as a separate dispatch-boundary layer beside mission-execution-control.
---

# Navigation Control

This module runs inside the `$mission-execution-control` dispatch loop: `mission_control.py` evaluates `scripts/navigation_control.py` programmatically at every boundary. Load this skill directly only to inspect, tune, or extend the navigation decision — never as a second control layer at dispatch.

The objective is the destination. Product changes, integration, runtime execution, repair, checkpointing, and packaging are actuators. Research, architecture analysis, audits, tests, browser observations, logs, and evaluation are sensors. Sensors exist to improve or safely constrain the next action; they are not a competing destination.

Every control cycle is:

1. **Observe** the current evidence-bound environment state.
2. **Orient** against the original destination and current waypoint.
3. **Act** on the smallest safe action that most reduces objective distance.
4. **Verify** the environment changed as expected.
5. **Replan** immediately from the new evidence.

Use `scripts/navigation_control.py` for the authoritative navigation decision. Follow its `next_action`, `sensor_posture`, objective distance, velocity, and actuation policy.

When the work is bottleneck optimization, a `company-os.riocl-tc-packet.v1`
may name regime, constraints, leverage, and decision mode. It is an overlay
checklist. Follow only the navigation `next_action`; do not let the packet
own the loop.

Research or audit work is justified only when it blocks the active action, is likely to change the next action, or is itself the current verification action. If objective velocity stalls, change implementation strategy or context before generating more general research or reports.

The minimum-sufficient-actuation ladder prefers existing code and supplied integrations, then standard-library/native platform capabilities, then installed dependencies, and only then the smallest new code that produces the required observable state transition. Never simplify away explicit requirements, security, trust-boundary validation, data-loss prevention, required error handling, accessibility, or reality evidence.

## Skill foundry navigation rule

Reusable skill creation is an actuator only when the destination is a skill or a missing reusable capability is the current concrete blocker. Otherwise it is post checkpoint learning and contributes zero destination movement. Sensor work about possible abstractions cannot interrupt the current actuator without value of information evidence.
