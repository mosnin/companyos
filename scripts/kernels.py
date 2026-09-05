#!/usr/bin/env python3
"""Repository entry point; implementation is bundled with the installed core."""
from pathlib import Path
import runpy

runpy.run_path(str(Path(__file__).resolve().parents[1] / "skills/company-os/elastic-company-os/scripts/kernel_manager.py"), run_name="__main__")
