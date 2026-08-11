from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import time

REPO = Path(__file__).resolve().parents[1]
CONTROLLER = REPO / "skills/company-os/elastic-company-os/scripts/company_os_controller.py"
DIRECTOR = REPO / "skills/company-os/direct-outcome/scripts/direct_outcome.py"
MISSION = REPO / "skills/company-os/mission-execution-control/scripts/mission_control.py"
OBJECTIVE_ID = "tip-calculator-micro"
OBJECTIVE = "Build a polished one page tip calculator browser app with bill amount, tip percentage, people count, total tip, total bill, and per person amount. It must actually run and calculate correctly."


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(args, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if result.returncode != 0:
        raise RuntimeError(f"command failed ({result.returncode}): {' '.join(args)}\n{result.stdout}")
    return result


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    mission = load_module(MISSION, "micro_mission_control")
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="company-os-micro-") as temp:
        project = Path(temp)
        run("git", "init", "-q", cwd=project)
        run("git", "config", "user.name", "Company OS Micro Test", cwd=project)
        run("git", "config", "user.email", "micro@example.invalid", cwd=project)
        init = run(
            "python3", str(CONTROLLER), "init",
            "--project", str(project),
            "--name", "Tip Calculator Micro",
            "--project-type", "general",
            "--north-star", OBJECTIVE,
        )
        init_payload = json.loads(init.stdout.strip().splitlines()[-1])

        start = run(
            "python3", str(DIRECTOR), "start",
            "--project-root", str(project),
            "--objective-id", OBJECTIVE_ID,
            "--objective", OBJECTIVE,
        )
        start_payload = json.loads(start.stdout.strip().splitlines()[-1])
        start_elapsed = time.monotonic() - started

        state_path = project / ".company-os/outcomes" / OBJECTIVE_ID / "director-state.json"
        state = json.loads(state_path.read_text())
        fabric_rel = state["artifacts"]["discovery_fabric"]
        fabric = json.loads((project / fabric_rel).read_text())
        worker_classes = [worker.get("work_class") for manager in fabric.get("managers", []) for worker in manager.get("workers", [])]
        worker_tasks = [worker.get("task", "") for manager in fabric.get("managers", []) for worker in manager.get("workers", [])]

        product = project / "product"
        product.mkdir()
        html = product / "index.html"
        js = product / "calculator.js"
        runtime = project / ".company-os/micro/runtime.json"
        journey = project / ".company-os/micro/journey.json"
        runtime.parent.mkdir(parents=True, exist_ok=True)

        html.write_text("""<!doctype html>
<html><head><meta charset=\"utf-8\"><title>Tip Calculator</title></head>
<body><main><h1>Tip Calculator</h1><label>Bill <input id=\"bill\" type=\"number\"></label><label>Tip % <input id=\"tip\" type=\"number\"></label><label>People <input id=\"people\" type=\"number\" value=\"1\"></label><button id=\"calculate\">Calculate</button><output id=\"result\"></output><script src=\"calculator.js\"></script></main></body></html>\n""")
        js.write_text("""function calculateTip(bill, tipPercent, people) {
  const b = Number(bill), t = Number(tipPercent), p = Number(people);
  if (!Number.isFinite(b) || !Number.isFinite(t) || !Number.isFinite(p) || b < 0 || t < 0 || p <= 0) throw new Error('invalid input');
  const tip = b * t / 100;
  const total = b + tip;
  return { tip, total, perPerson: total / p };
}
if (typeof module !== 'undefined') module.exports = { calculateTip };
if (typeof document !== 'undefined') document.getElementById('calculate').addEventListener('click', () => {
  const r = calculateTip(document.getElementById('bill').value, document.getElementById('tip').value, document.getElementById('people').value);
  document.getElementById('result').textContent = `Tip $${r.tip.toFixed(2)} | Total $${r.total.toFixed(2)} | Per person $${r.perPerson.toFixed(2)}`;
});
""")
        first_artifact_elapsed = time.monotonic() - started

        node_probe = run("node", "-e", "const {calculateTip}=require('./product/calculator.js'); const r=calculateTip(100,20,3); if(Math.abs(r.tip-20)>1e-9||Math.abs(r.total-120)>1e-9||Math.abs(r.perPerson-40)>1e-9) process.exit(2); console.log(JSON.stringify(r));", cwd=project)
        runtime.write_text(json.dumps({"command": "node calculation probe", "stdout": node_probe.stdout.strip(), "passed": True}, sort_keys=True) + "\n")
        journey.write_text(json.dumps({"journey": "enter 100 bill, 20 percent tip, 3 people, calculate", "expected": {"tip": 20, "total": 120, "perPerson": 40}, "passed": True}, sort_keys=True) + "\n")

        receipt = {
            "$schema": mission.REALITY_SPIKE_SCHEMA,
            "objective_id": OBJECTIVE_ID,
            "completed_at": mission.format_time(mission.now_utc()),
            "artifacts": [
                {"capability_id": "first_real_artifact", "path": "product/index.html", "sha256": sha(html)},
                {"capability_id": "first_real_artifact", "path": "product/calculator.js", "sha256": sha(js)},
            ],
            "commands": [{"command": "node calculation probe", "exit_code": 0}],
            "observations": [
                {"capability_id": "first_real_artifact", "kind": "runtime_observed", "observation_kind": "node_runtime", "path": ".company-os/micro/runtime.json", "sha256": sha(runtime)},
                {"capability_id": "first_real_artifact", "kind": "journey_connected", "observation_kind": "calculation_interaction", "path": ".company-os/micro/journey.json", "sha256": sha(journey)},
            ],
            "blockers": [],
            "receipt_sha256": None,
        }
        receipt["receipt_sha256"] = mission.digest(receipt)
        spike_path = project / ".company-os/outcomes" / OBJECTIVE_ID / "reality-spike/reality-spike-receipt.json"
        spike_path.parent.mkdir(parents=True, exist_ok=True)
        spike_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")

        advance = run("python3", str(DIRECTOR), "advance", "--project-root", str(project), "--objective-id", OBJECTIVE_ID)
        status = run("python3", str(DIRECTOR), "status", "--project-root", str(project), "--objective-id", OBJECTIVE_ID)
        status_payload = json.loads(status.stdout.strip().splitlines()[-1])
        mission_state = status_payload["mission_execution"]
        reality = mission_state["reality"]

        docs = [p for p in project.rglob("*.md") if ".git" not in p.parts]
        product_files = [str(p.relative_to(project)) for p in product.rglob("*") if p.is_file()]
        checks = {
            "exact_company_os_commit": "8ef43175321fbdc76446dcb4820a3b46f94a6e61",
            "controller_initialized": init_payload.get("ok") is True,
            "start_stage_is_discovery": start_payload["stage"] == "discovery",
            "implementation_dispatched_during_discovery": "implementation" in worker_classes,
            "research_dispatched_during_discovery": "research" in worker_classes,
            "reality_spike_instruction_present": any("reality spike" in task.lower() or "real artifact" in task.lower() for task in worker_tasks),
            "product_artifact_created": html.is_file() and js.is_file(),
            "real_runtime_executed": node_probe.returncode == 0,
            "connected_journey_observed": reality.get("connected_vertical_slice") is True,
            "documentation_spiral_absent": len(docs) == 0,
            "product_files": product_files,
            "markdown_files_before_r3": [str(p.relative_to(project)) for p in docs],
            "start_elapsed_seconds": round(start_elapsed, 3),
            "first_artifact_elapsed_seconds": round(first_artifact_elapsed, 3),
            "director_stage_after_spike": status_payload["stage"],
            "governor_mode_after_spike": mission_state["governor_decision"]["mode"],
            "reality": reality,
        }
        required = [
            checks["controller_initialized"], checks["start_stage_is_discovery"], checks["implementation_dispatched_during_discovery"], checks["research_dispatched_during_discovery"],
            checks["reality_spike_instruction_present"], checks["product_artifact_created"], checks["real_runtime_executed"], checks["connected_journey_observed"], checks["documentation_spiral_absent"],
        ]
        report = {"objective": OBJECTIVE, "passed": all(required), "checks": checks, "start_output": start_payload, "advance_output": json.loads(advance.stdout.strip().splitlines()[-1]), "status_output": status_payload}
        out = REPO / "micro-execution-report.json"
        out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
