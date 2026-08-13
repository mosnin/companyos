#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

path = Path("skills/company-os/recursive-skill-foundry/scripts/skill_foundry.py")
text = path.read_text(encoding="utf-8")
old = '''    write_json(coordinator_dir / "skill" / system_name / "assets" / "system_manifest.json", manifest)
    prior = load_candidate(coordinator_dir); skill_dir = coordinator_dir / "skill" / system_name; validation = validate_skill(skill_dir, threshold); simulation = simulate_skill(skill_dir); skill_files = skill_manifest(skill_dir); updated = dict(prior); updated.update({"skill_manifest": skill_files, "skill_sha256": digest(skill_files), "quality_score": validation["quality_score"], "validation_status": validation["status"], "simulation_status": simulation["status"]}); updated = seal_candidate(updated); write_json(coordinator_dir / "validation.json", validation); write_json(coordinator_dir / "simulation.json", simulation); write_json(coordinator_dir / "candidate.json", updated); coordinator.update({"candidate_sha256": updated["candidate_sha256"], "skill_sha256": updated["skill_sha256"], "quality_score": updated["quality_score"]})
'''
new = '''    prior = load_candidate(coordinator_dir)
    write_json(coordinator_dir / "skill" / system_name / "assets" / "system_manifest.json", manifest)
    skill_dir = coordinator_dir / "skill" / system_name; validation = validate_skill(skill_dir, threshold); simulation = simulate_skill(skill_dir); skill_files = skill_manifest(skill_dir); updated = dict(prior); updated.update({"skill_manifest": skill_files, "skill_sha256": digest(skill_files), "quality_score": validation["quality_score"], "validation_status": validation["status"], "simulation_status": simulation["status"]}); updated = seal_candidate(updated); write_json(coordinator_dir / "validation.json", validation); write_json(coordinator_dir / "simulation.json", simulation); write_json(coordinator_dir / "candidate.json", updated); coordinator.update({"candidate_sha256": updated["candidate_sha256"], "skill_sha256": updated["skill_sha256"], "quality_score": updated["quality_score"]})
'''
if text.count(old) != 1:
    raise SystemExit(f"coordinator repair anchor expected once, found {text.count(old)}")
path.write_text(text.replace(old, new, 1), encoding="utf-8")
print("recursive coordinator digest repair applied")
