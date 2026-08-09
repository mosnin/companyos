# Operator Command Center — Design System

Concept source: `docs/design/operator-command-center-concept-v1.png`

## Visual direction

The screen is an editorial operating-intelligence console: true near-black
canvas, warm white typography, acid-lime reserved for the one current decision,
and coral reserved for blocking truth. It uses open rails and hairline divisions,
not a generic grid of floating cards.

## Tokens

| Role | Value |
| --- | --- |
| Canvas | `#070907` |
| Primary text | `#f3f4ef` |
| Muted text | `#9da198` |
| Hairline | `#292d28` |
| Decision accent | `#c9ff36` |
| Blocker accent | `#ff6b61` |
| Decision tint | `rgba(201,255,54,.07)` |
| Blocker tint | `rgba(255,107,97,.07)` |
| Display type | `Arial Black`, `Arial`, system sans-serif |
| UI type | `Inter`, `SF Pro Text`, system sans-serif |
| Content width | 1440px maximum |
| Outer gutter | 28–36px desktop; 18px mobile |
| Major spacing | 48px |
| Minor spacing | 8, 12, 16, 24px |
| Border radius | 4px controls; 10px decision frame |

## Hierarchy and containers

1. A restrained three-part masthead: brand, project, governed status.
2. An open two-column change band: semantic changes left, attributable event
   trail right.
3. One lime-framed decision strip is the visual focal point.
4. The seven named stages form one horizontal rail and become a vertical
   sequence on narrow screens.
5. Quality exceptions, primary work, and agent-team truth share one open
   three-column band without individual cards.
6. Trust and feedback use a compact horizontal facts rail.
7. Blockers, trust notes, and evidence boundaries use native disclosure rows.

## Typography

- The changed outcome and current decision use large display text with compact
  line height and no decorative eyebrow above the page heading.
- Labels are uppercase, 11–12px, 0.12em tracking, and never carry meaning alone.
- Body copy is 14–16px with 1.45–1.6 line height.
- Operational facts use tabular numerals where available.

## Interaction

- Native `<details>` elements reveal the full decision trail, quality
  exceptions, agent runs, blockers, trust notes, and evidence boundary without
  JavaScript.
- Focus rings use the lime accent and remain visible on the dark canvas.
- Status and stage meaning are always written in text; color is redundant.
- The page has a brief staged entrance and a restrained current-stage pulse.
  Both are disabled with `prefers-reduced-motion: reduce`.
- Print mode removes animation, preserves text, and uses a white canvas.

## Exact copy boundary

All project, program, status, change, decision, work, quality, team, evidence,
feedback, authority, and warning copy comes from the curated operator brief.
The renderer may add only structural labels such as “Latest governed change,”
“Governed command trail,” “Current decision,” and “Trust notes.” It may not invent
people, timestamps, agent activity, progress, metrics, evidence, or outcomes.

## Responsive behavior

- At 920px, the change band, decision metadata, and three-column operating band
  become one column.
- The stage rail becomes a bordered vertical sequence while preserving order
  and full state labels.
- Tables remain inside horizontally scrollable semantic regions with a visible
  focus target.
- No primary content may clip at 375px width.

## Browser fidelity ledger

- Method: Codex in-app Browser against the self-hosted static artifact over
  `127.0.0.1`; no external page, service, or project state was mutated.
- Desktop viewport: 1435 × 1096.
- Mobile viewport: 375 × 812.
- Concept: `docs/design/operator-command-center-concept-v1.png`.
- Latest captures:
  `programs/company-os-self-hosting/OPERATOR_COMMAND_CENTER_DESKTOP.jpg` and
  `programs/company-os-self-hosting/OPERATOR_COMMAND_CENTER_MOBILE.jpg`.

| Comparison point | Concept intent | Verified implementation |
| --- | --- | --- |
| Editorial structure | Open rails and hairlines, not a dashboard-card grid | Masthead, change band, journey, operating band, fact rail, and disclosures retain that structure |
| Decision dominance | One lime-framed next decision is visually primary | One framed decision contains the governed title, owner, output, done condition, and verification |
| Change attribution | Four compact recent decisions, with deeper comparison history on demand | The acceptance artifact explicitly names the Program v5 update 6 → 15 window; four records appear on desktop, two on mobile, and all nine updates in that comparison remain in one disclosure |
| Stage orientation | Seven named phases with a visibly current stage | All seven names and textual states are present; Experience is current without relying on color |
| Exception compression | Quality, work, and team truth share one operating band | The desktop surface begins this band inside the first viewport and collapses complete evidence behind disclosures |
| Trust rail | Authority, certification, schedule, and observations remain explicit | Protected update, authority, certification, schedule/lease, token, cost, and lead-time truth are rendered from state |
| Mobile hierarchy | One decisive narrow-screen surface without clipping | The current decision is first visually, the page has no horizontal overflow, and disclosure targets are about 60px high |
| Motion and focus | Restraint rather than decorative animation | One short entrance and current-stage pulse honor reduced motion; focus rings and a skip link are present |

### Copy and truth differences

The generated concept used illustrative times, actors, and compressed decision
copy. The implementation intentionally does not reproduce them. It uses real
update numbers, commands, safe references, current blockers, and the actual
independent-review owner. Long governed decision text is compressed only in the
focal strip; the exact instruction, done condition, and verification remain in
the open “Governed decision handoff” disclosure together with the exact program,
update, outcome, work, and acceptance reference. The concept's illustrative “0 active”
blocker line is replaced by the actual quality blocker.

### Interaction path verified

The browser pass opened and closed the governed Program v5 comparison trail,
confirmed all nine updates in the explicitly labeled update 6 → 15 window
remained available, opened the governed decision handoff, verified its
exact governed text, and confirmed the native summaries are unique focusable
controls. The skip link is focusable and resolves to the one H1. Desktop and
mobile passes reported no horizontal overflow, no browser console warnings or
errors, and a logical H1-to-H2 heading sequence.

### Fidelity decision

The implemented command center is faithful to the accepted concept's visual
system and hierarchy while deliberately replacing illustrative content with
governed truth. The mobile decision-first reflow and compact recent trail are
intentional usability improvements, not unreviewed visual drift.
