#!/usr/bin/env python3
from __future__ import annotations

import runpy
from pathlib import Path

path = Path("scripts/apply_execution_enforcement_v2_phase2.py")
text = path.read_text(encoding="utf-8")n