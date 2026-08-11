#!/usr/bin/env python3
from pathlib import Path


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one match, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


# The global discovery budget was halved to 45m/12k/$12. Split that budget
# across the two discovery managers instead of oversubscribing it.
bootstrap = Path("skills/company-os/bootstrap-outcome/scripts/bootstrap_outcome.py")
replace_once(
    bootstrap,
    'return {"time_minutes": 45.0, "token_limit": 12000, "cost_usd": 12.0, "max_concurrency": 1, "max_retries": 1}',
    'return {"time_minutes": 22.5, "token_limit": 6000, "cost_usd": 6.0, "max_concurrency": 1, "max_retries": 1}',
    "discovery manager budget",
)

# Preserve the old single-artifact lane field while allowing a pilot to bundle
# many artifact classes into at most two execution lanes.
loop = Path("skills/company-os/elastic-company-os/scripts/outcome_loop.py")
replace_once(
    loop,
    "{'lane_id':f'pilot:artifact-bundle:{index+1:02d}','role':'artifact_specialist','artifact_classes':group,",
    "{'lane_id':f'pilot:artifact-bundle:{index+1:02d}','role':'artifact_specialist','artifact_classes':group,**({'artifact_class_id':group[0]} if len(group)==1 else {}),",
    "single-artifact pilot compatibility",
)

print("execution regression compatibility fixes applied")
