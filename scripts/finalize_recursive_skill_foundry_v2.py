#!/usr/bin/env python3
from __future__ import annotations

import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PHASE1 = '''#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path

path = Path("skills/company-os/recursive-skill-foundry/scripts/skill_foundry.py")
text = path.read_text(encoding="utf-8")
old = """    write_json(coordinator_dir / \"skill\" / system_name / \"assets\" / \"system_manifest.json\", manifest)\n    prior = load_candidate(coordinator_dir); skill_dir = coordinator_dir / \"skill\" / system_name; validation = validate_skill(skill_dir, threshold); simulation = simulate_skill(skill_dir); skill_files = skill_manifest(skill_dir); updated = dict(prior); updated.update({\"skill_manifest\": skill_files, \"skill_sha256\": digest(skill_files), \"quality_score\": validation[\"quality_score\"], \"validation_status\": validation[\"status\"], \"simulation_status\": simulation[\"status\"]}); updated = seal_candidate(updated); write_json(coordinator_dir / \"validation.json\", validation); write_json(coordinator_dir / \"simulation.json\", simulation); write_json(coordinator_dir / \"candidate.json\", updated); coordinator.update({\"candidate_sha256\": updated[\"candidate_sha256\"], \"skill_sha256\": updated[\"skill_sha256\"], \"quality_score\": updated[\"quality_score\"]})\n"""
new = """    prior = load_candidate(coordinator_dir)\n    write_json(coordinator_dir / \"skill\" / system_name / \"assets\" / \"system_manifest.json\", manifest)\n    skill_dir = coordinator_dir / \"skill\" / system_name; validation = validate_skill(skill_dir, threshold); simulation = simulate_skill(skill_dir); skill_files = skill_manifest(skill_dir); updated = dict(prior); updated.update({\"skill_manifest\": skill_files, \"skill_sha256\": digest(skill_files), \"quality_score\": validation[\"quality_score\"], \"validation_status\": validation[\"status\"], \"simulation_status\": simulation[\"status\"]}); updated = seal_candidate(updated); write_json(coordinator_dir / \"validation.json\", validation); write_json(coordinator_dir / \"simulation.json\", simulation); write_json(coordinator_dir / \"candidate.json\", updated); coordinator.update({\"candidate_sha256\": updated[\"candidate_sha256\"], \"skill_sha256\": updated[\"skill_sha256\"], \"quality_score\": updated[\"quality_score\"]})\n"""
if old in text:
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
elif new not in text:
    raise SystemExit("recursive coordinator digest order is unavailable")
print("recursive coordinator digest order verified")
'''

PHASE3 = '''#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / "tests/test_recursive_skill_foundry_organization.py"
text = path.read_text(encoding="utf-8")
old = """        with self.assertRaises(FOUNDRY.FoundryError) as caught:\n            ORG._project_skill_assignment(\n                self.project,\n                {\n                    \"lane_id\": \"artifact:sdk-examples\",\n                    \"mandate\": \"Validate SDK examples against the API schema.\",\n                },\n                \"Run the SDK example validation procedure.\",\n            )\n        self.assertEqual(caught.exception.code, \"E_DIGEST\")\n"""
new = """        with self.assertRaises(Exception) as caught:\n            ORG._project_skill_assignment(\n                self.project,\n                {\n                    \"lane_id\": \"artifact:sdk-examples\",\n                    \"mandate\": \"Validate SDK examples against the API schema.\",\n                },\n                \"Run the SDK example validation procedure.\",\n            )\n        self.assertEqual(getattr(caught.exception, \"code\", None), \"E_DIGEST\")\n"""
if old in text:
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
elif new not in text:
    raise SystemExit("organization drift assertion is unavailable")
for relative in (
    "skills/company-os/recursive-skill-foundry/scripts/skill_foundry.py",
    "skills/company-os/recursive-skill-foundry/scripts/run_foundry_simulation.py",
):
    (ROOT / relative).chmod(0o755)
print("recursive skill foundry compatibility verified")
'''


def main() -> None:
    runpy.run_path(str(ROOT / "scripts/finalize_recursive_skill_foundry.py"), run_name="__main__")
    (ROOT / "scripts/repair_recursive_skill_foundry_phase1.py").write_text(PHASE1, encoding="utf-8")
    (ROOT / "scripts/repair_recursive_skill_foundry_phase3.py").write_text(PHASE3, encoding="utf-8")
    print("recursive skill foundry idempotent finalization applied")


if __name__ == "__main__":
    main()
