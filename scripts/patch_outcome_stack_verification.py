#!/usr/bin/env python3
from pathlib import Path


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one match, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


synthesis = Path("skills/company-os/synthesize-outcome-model/scripts/synthesize_outcome_model.py")
replace_once(
    synthesis,
    'RICH_MODALITIES = {"interactive", "visual", "audio", "executable", "service", "database", "model", "physical", "composite"}\n',
    'RICH_MODALITIES = {"interactive", "visual", "audio", "executable", "service", "database", "model", "physical", "composite"}\nBENCHMARK_TIERS = {"negative", "baseline", "strong", "exemplar"}\n',
    "benchmark tier constant",
)
replace_once(
    synthesis,
    '        tier = text(ref.get("quality_tier"), f"{label}.quality_tier")\n        tiers.add(tier)\n',
    '        tier = text(ref.get("quality_tier"), f"{label}.quality_tier")\n        if tier not in BENCHMARK_TIERS:\n            raise SynthesisError("E_BENCHMARK", f"{benchmark_id} uses unsupported quality tier {tier}")\n        tiers.add(tier)\n',
    "benchmark tier validation",
)

test = Path("tests/test_outcome_discovery_bootstrap.py")
replace_once(
    test,
    '"quality_tier": "weak",',
    '"quality_tier": "negative",',
    "benchmark fixture tier",
)

print("outcome stack schema alignment applied")
