#!/usr/bin/env python3
"""Render a safe read-only Company OS Control Station from observatory JSON."""

from __future__ import annotations

import argparse
import html
import json
import math
from pathlib import Path
from typing import Any


SCHEMA = "company-os.control-station-snapshot.v1"


class SnapshotError(ValueError):
    """Raised when an observatory snapshot is unsafe or incomplete."""


def _objects(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _count(value: Any) -> int:
    number = _number(value)
    return max(0, int(number)) if number is not None else 0


def _escape(value: Any) -> str:
    return html.escape(str(value or "Unavailable"), quote=True)


def _label(value: Any) -> str:
    return " ".join(word.capitalize() for word in str(value or "unknown").replace("_", " ").replace("-", " ").split())


def _percent(value: Any) -> str:
    number = _number(value)
    return "Unavailable" if number is None else f"{number * 100:.0f}%"


def _metric(value: Any, *, suffix: str = "") -> str:
    number = _number(value)
    if number is None:
        return "Unavailable"
    rendered = f"{number:,.0f}" if number.is_integer() else f"{number:,.1f}"
    return f"{rendered}{suffix}"


def load_snapshot(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SnapshotError(f"cannot load control-station snapshot: {error}") from error
    if not isinstance(value, dict) or value.get("schema") != SCHEMA:
        raise SnapshotError(f"snapshot.schema must equal {SCHEMA!r}")
    if not isinstance(value.get("summary"), dict):
        raise SnapshotError("snapshot.summary must be an object")
    if not isinstance(value.get("runs"), list):
        raise SnapshotError("snapshot.runs must be an array")
    if not isinstance(value.get("blockers"), list):
        raise SnapshotError("snapshot.blockers must be an array")
    return value


def render_html(snapshot: dict[str, Any], *, title: str = "Company OS Control Station") -> str:
    summary = snapshot.get("summary", {})
    runs = _objects(snapshot.get("runs"))
    blockers = _objects(snapshot.get("blockers"))
    ready = bool(runs) and not blockers and all(run.get("scaling_evidence_eligible") is True for run in runs)
    decision = "Ready for bounded scale" if ready else "Hold scale. Close the evidence gaps."
    decision_detail = (
        "Every recorded run is scale-eligible and no open blocker is present."
        if ready
        else "The system has real output, but it does not yet prove efficient Luna execution, complete scope fidelity, and accepted delivery."
    )

    cards = [
        ("Recorded runs", str(_count(summary.get("run_count"))), "Real programs in the observatory"),
        ("Delivery acceptance", _percent(summary.get("delivery_acceptance_rate")), "Accepted complete runs"),
        ("Artifact acceptance", _percent(summary.get("artifact_acceptance_rate")), "Accepted planned artifacts"),
        ("Luna proof", f"{_count(summary.get('luna_proven_runs'))} / {_count(summary.get('run_count'))}", "Observed, not requested"),
        ("Efficiency proof", f"{_count(summary.get('efficiency_proven_runs'))} / {_count(summary.get('run_count'))}", "Tokens, cost, and lead time"),
        ("Write collisions", _metric(summary.get("write_collisions")), "Must remain zero"),
    ]
    card_html = "".join(
        f'<article class="metric"><p>{_escape(label)}</p><strong>{_escape(value)}</strong><span>{_escape(note)}</span></article>'
        for label, value, note in cards
    )

    run_rows = "".join(
        "<tr>"
        f"<td><strong>{_escape(run.get('project_id'))}</strong><span>{_escape(run.get('comparison_class'))}</span></td>"
        f"<td><span class=\"status status-{_escape(run.get('status'))}\">{_escape(_label(run.get('status')))}</span></td>"
        f"<td>{_percent(run.get('accepted_artifact_rate'))}</td>"
        f"<td>{_metric(run.get('mandatory_requirements_satisfied'))} / {_metric(run.get('mandatory_requirements_total'))}</td>"
        f"<td>{_metric(run.get('required_capabilities_applied'))} / {_metric(run.get('required_capabilities_total'))}</td>"
        f"<td>{'Proven' if run.get('luna_execution_proven') is True else 'Unproven'}</td>"
        f"<td>{'Proven' if run.get('efficiency_proven') is True else 'Unproven'}</td>"
        "</tr>"
        for run in runs
    ) or '<tr><td colspan="7">No runs have been recorded.</td></tr>'

    blocker_html = "".join(
        "<li>"
        f"<span>{_escape(_label(blocker.get('kind')))}</span>"
        f"<div><strong>{_escape(blocker.get('id'))}</strong><p>{_escape(blocker.get('summary'))}</p>"
        f"<small>{_escape(blocker.get('run_id'))}</small></div>"
        "</li>"
        for blocker in blockers
    ) or '<li class="empty"><div><strong>No open blockers</strong><p>Every recorded mandatory requirement and capability is closed.</p></div></li>'

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_escape(title)}</title>
<style>
:root{{--ink:#141414;--muted:#6b6b67;--line:#deddd7;--paper:#f3f1eb;--panel:#fbfaf7;--signal:#24594a;--warn:#a4432d;--amber:#8f641f;--ease:cubic-bezier(.23,1,.32,1)}}
*{{box-sizing:border-box}} body{{margin:0;background:var(--paper);color:var(--ink);font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;line-height:1.45}} .skip{{position:absolute;left:-999px;top:12px}} .skip:focus{{left:16px;background:var(--ink);color:white;padding:10px 14px;border-radius:8px;z-index:10}} main{{width:min(1180px,calc(100% - 32px));margin:0 auto;padding:56px 0 72px}} header{{display:flex;justify-content:space-between;gap:32px;align-items:flex-end;padding-bottom:28px;border-bottom:1px solid var(--ink)}} .eyebrow{{font-size:12px;letter-spacing:.14em;text-transform:uppercase;color:var(--muted);margin:0 0 10px}} h1{{font-family:Georgia,"Times New Roman",serif;font-size:clamp(38px,6vw,72px);font-weight:500;line-height:.96;letter-spacing:-.045em;margin:0;max-width:760px}} .as-of{{text-align:right;color:var(--muted);font-size:13px;max-width:260px}} .decision{{display:grid;grid-template-columns:minmax(220px,.7fr) 1.3fr;gap:28px;margin:28px 0;padding:26px;border:1px solid var(--line);border-left:4px solid { 'var(--signal)' if ready else 'var(--warn)' };background:var(--panel)}} .decision h2{{font-size:24px;margin:0;letter-spacing:-.025em}} .decision p{{margin:0;color:var(--muted);max-width:720px}} .metrics{{display:grid;grid-template-columns:repeat(3,1fr);gap:1px;background:var(--line);border:1px solid var(--line);margin-bottom:36px}} .metric{{background:var(--panel);padding:22px;min-height:146px}} .metric p,.metric span{{margin:0;color:var(--muted);font-size:13px}} .metric strong{{display:block;font-family:Georgia,"Times New Roman",serif;font-size:38px;font-weight:500;letter-spacing:-.035em;margin:12px 0 20px}} section{{margin-top:40px}} section>div.heading{{display:flex;align-items:baseline;justify-content:space-between;gap:20px;margin-bottom:14px}} h2{{font-size:18px;margin:0}} .heading p{{margin:0;color:var(--muted);font-size:13px}} .table-wrap{{overflow:auto;border:1px solid var(--line);background:var(--panel)}} table{{width:100%;border-collapse:collapse;min-width:900px}} th{{text-align:left;padding:12px 14px;color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:.09em;border-bottom:1px solid var(--line)}} td{{padding:16px 14px;border-bottom:1px solid var(--line);font-size:13px;vertical-align:top}} tr:last-child td{{border-bottom:0}} td strong,td span{{display:block}} td span{{color:var(--muted);margin-top:3px}} .status{{display:inline-block;width:max-content;margin:0;padding:4px 8px;border-radius:99px;background:#e8e5dd;color:var(--ink);font-size:11px;text-transform:uppercase;letter-spacing:.05em}} .status-blocked,.status-failed{{background:#f4ddd7;color:#792d1f}} .status-rework{{background:#f4e7c9;color:#6f4a10}} .status-accepted{{background:#dcebe4;color:#174c3c}} ul{{list-style:none;padding:0;margin:0;border:1px solid var(--line);background:var(--panel)}} li{{display:grid;grid-template-columns:120px 1fr;gap:22px;padding:18px 20px;border-bottom:1px solid var(--line)}} li:last-child{{border-bottom:0}} li>span{{font-size:11px;text-transform:uppercase;letter-spacing:.09em;color:var(--warn)}} li strong{{font-size:14px}} li p{{margin:4px 0;color:var(--muted)}} li small{{color:var(--muted)}} footer{{margin-top:48px;padding-top:18px;border-top:1px solid var(--line);color:var(--muted);font-size:12px}} @media(max-width:760px){{main{{padding-top:32px}}header{{display:block}}.as-of{{text-align:left;margin-top:18px}}.decision{{grid-template-columns:1fr}}.metrics{{grid-template-columns:1fr 1fr}}}} @media(max-width:480px){{.metrics{{grid-template-columns:1fr}}li{{grid-template-columns:1fr;gap:6px}}}} @media(prefers-reduced-motion:reduce){{*,*::before,*::after{{scroll-behavior:auto!important;animation:none!important;transition:none!important}}}}
</style>
</head>
<body>
<a class="skip" href="#runs">Skip to recorded runs</a>
<main>
<header><div><p class="eyebrow">Evidence, not activity</p><h1>{_escape(title)}</h1></div><p class="as-of">Workspace: {_escape(snapshot.get('workspace_id'))}<br>Evidence as of {_escape(snapshot.get('as_of'))}</p></header>
<section class="decision" aria-labelledby="decision-title"><h2 id="decision-title">{_escape(decision)}</h2><p>{_escape(decision_detail)}</p></section>
<section class="metrics" aria-label="Operating metrics">{card_html}</section>
<section id="runs"><div class="heading"><h2>Recorded real work</h2><p>Unavailable telemetry stays unavailable.</p></div><div class="table-wrap"><table><thead><tr><th>Project</th><th>Status</th><th>Artifacts</th><th>Requirements</th><th>Capabilities</th><th>Luna</th><th>Efficiency</th></tr></thead><tbody>{run_rows}</tbody></table></div></section>
<section><div class="heading"><h2>Open evidence gaps</h2><p>{len(blockers)} unresolved item(s)</p></div><ul>{blocker_html}</ul></section>
<footer>Generated from the append-only Company OS observatory. This view is read-only and cannot activate workers, schedules, integrations, or production writes.</footer>
</main>
</body>
</html>"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("snapshot", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--title", default="Company OS Control Station")
    args = parser.parse_args()
    try:
        rendered = render_html(load_snapshot(args.snapshot), title=args.title)
    except SnapshotError as error:
        parser.error(str(error))
    args.output.write_text(rendered, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
