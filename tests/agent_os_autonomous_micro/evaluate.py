from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import time
import urllib.error
import urllib.request
from typing import Any


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def safe_relative(root: Path, raw: str) -> Path:
    candidate = (root / raw).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"path escapes workspace: {raw}") from exc
    return candidate


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {path}")
    return value


def wait_for_http(url: str, timeout_seconds: float = 35.0) -> tuple[bool, str]:
    deadline = time.monotonic() + timeout_seconds
    last_error = ""
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2.0) as response:
                if 200 <= response.status < 500:
                    return True, f"HTTP {response.status}"
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = str(exc)
        time.sleep(0.5)
    return False, last_error or "HTTP endpoint did not become ready"


def first_visible(locator):
    count = locator.count()
    for index in range(count):
        item = locator.nth(index)
        try:
            if item.is_visible():
                return item
        except Exception:
            continue
    return None


def locate_note_input(page):
    patterns = [re.compile(value, re.I) for value in ("note", "content", "text", "message")]
    for pattern in patterns:
        try:
            item = first_visible(page.get_by_label(pattern))
            if item is not None:
                return item
        except Exception:
            pass
    selectors = [
        "textarea",
        "input[type='text']",
        "input:not([type])",
        "[contenteditable='true']",
    ]
    for selector in selectors:
        item = first_visible(page.locator(selector))
        if item is not None:
            return item
    raise AssertionError("no visible accessible note input found")


def locate_add_button(page):
    for pattern in ("add", "create", "save", "new note"):
        try:
            item = first_visible(page.get_by_role("button", name=re.compile(pattern, re.I)))
            if item is not None:
                return item
        except Exception:
            pass
    item = first_visible(page.locator("button[type='submit'], input[type='submit']"))
    if item is not None:
        return item
    raise AssertionError("no visible add or save control found")


def fill_note_input(locator, value: str) -> None:
    tag = locator.evaluate("element => element.tagName.toLowerCase()")
    if locator.get_attribute("contenteditable") == "true":
        locator.click()
        locator.evaluate("(element, value) => { element.textContent = value; element.dispatchEvent(new InputEvent('input', { bubbles: true, inputType: 'insertText', data: value })); }", value)
    elif tag in {"input", "textarea"}:
        locator.fill(value)
    else:
        locator.click()
        locator.press("Control+A")
        locator.type(value)


def delete_note(page, note_text: str) -> None:
    note = first_visible(page.get_by_text(note_text, exact=True))
    if note is None:
        raise AssertionError("created note is not visible before deletion")

    candidate = note
    for _ in range(6):
        for pattern in ("delete", "remove", "trash"):
            try:
                button = first_visible(candidate.get_by_role("button", name=re.compile(pattern, re.I)))
                if button is not None:
                    button.click()
                    return
            except Exception:
                pass
        candidate = candidate.locator("xpath=..")

    for pattern in ("delete", "remove", "trash"):
        try:
            button = first_visible(page.get_by_role("button", name=re.compile(pattern, re.I)))
            if button is not None:
                button.click()
                return
        except Exception:
            pass
    raise AssertionError("no visible delete control associated with the note")


def visible_validation(page) -> str | None:
    pattern = re.compile(r"required|empty|enter|cannot|must|note", re.I)
    candidates = page.locator("[role='alert'], [aria-live], .error, .validation, p, span, div")
    for index in range(min(candidates.count(), 250)):
        candidate = candidates.nth(index)
        try:
            if not candidate.is_visible():
                continue
            text = candidate.inner_text().strip()
        except Exception:
            continue
        if text and len(text) <= 240 and pattern.search(text):
            return text
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()

    workspace = args.workspace.resolve()
    report_path = args.report.resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    checks: list[dict[str, Any]] = []
    failures: list[str] = []
    server: subprocess.Popen[str] | None = None

    def record(name: str, passed: bool, detail: Any = None) -> None:
        checks.append({"name": name, "passed": bool(passed), "detail": detail})
        if not passed:
            failures.append(name)

    result_path = workspace / ".company-os-test/result.json"
    result: dict[str, Any] = {}
    try:
        record("result_receipt_exists", result_path.is_file(), str(result_path))
        if result_path.is_file():
            result = read_json(result_path)
    except Exception as exc:
        record("result_receipt_parses", False, str(exc))

    record("agent_claims_accepted", result.get("status") == "accepted", result.get("status"))
    record("objective_id_matches", result.get("objective_id") == "signal-notes-micro", result.get("objective_id"))

    director_path = workspace / ".company-os/outcomes/signal-notes-micro/director-state.json"
    mission_path = workspace / ".company-os/outcomes/signal-notes-micro/mission-execution-state.json"
    record("director_state_exists", director_path.is_file(), str(director_path))
    record("mission_state_exists", mission_path.is_file(), str(mission_path))

    director: dict[str, Any] = {}
    mission: dict[str, Any] = {}
    try:
        if director_path.is_file():
            director = read_json(director_path)
        if mission_path.is_file():
            mission = read_json(mission_path)
    except Exception as exc:
        record("company_os_state_parses", False, str(exc))

    navigation = mission.get("navigation") if isinstance(mission.get("navigation"), dict) else {}
    position = navigation.get("position") if isinstance(navigation.get("position"), dict) else {}
    record("director_stage_accepted", director.get("stage") == "accepted", director.get("stage"))
    record("navigation_arrived", navigation.get("mode") == "arrived", navigation.get("mode"))
    record("destination_distance_zero", position.get("destination_distance") == 0, position.get("destination_distance"))
    record("durable_checkpoint_present", isinstance(mission.get("checkpoint"), dict), mission.get("checkpoint"))

    mission_script = workspace / ".codex/skills/company-os/mission-execution-control/scripts/mission_control.py"
    try:
        mission_module = load_module(mission_script, "agent_os_micro_mission")
        verified_mission = mission_module.verify_state(mission)
        reality = mission_module.reality_signals(verified_mission)
        record("connected_user_journey_recorded", reality.get("connected_vertical_slice") is True, reality)
        record("user_usable_reality_recorded", reality.get("user_usable") is True, reality)
        record("independent_acceptance_recorded", reality.get("independent_acceptance") is True, reality)
    except Exception as exc:
        record("mission_reality_verifies", False, str(exc))

    manager_threads = result.get("manager_threads")
    worker_threads = result.get("worker_threads")
    manager_threads = manager_threads if isinstance(manager_threads, list) else []
    worker_threads = worker_threads if isinstance(worker_threads, list) else []
    record("real_manager_thread_reported", len(manager_threads) >= 1, manager_threads)
    record("real_worker_thread_reported", len(worker_threads) >= 1, worker_threads)

    thread_ids: list[str] = []
    for collection in (manager_threads, worker_threads):
        for item in collection:
            if isinstance(item, dict) and isinstance(item.get("thread_id"), str):
                thread_ids.append(item["thread_id"].strip())
    plausible = bool(thread_ids) and all(len(value) >= 8 and value.lower() not in {"unknown", "n/a", "none"} for value in thread_ids)
    record("thread_ids_are_plausible", plausible, thread_ids)
    record("thread_ids_are_unique", len(thread_ids) == len(set(thread_ids)), thread_ids)
    record("root_did_not_claim_product_writes", result.get("root_product_writes") == [], result.get("root_product_writes"))

    immutable = subprocess.run(
        ["git", "diff", "--exit-code", "--", "OBJECTIVE.md", "AGENTS.md", ".codex/skills"],
        cwd=workspace,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    record("objective_and_installed_skills_unchanged", immutable.returncode == 0, immutable.stdout[-4000:])

    product_root_raw = result.get("product_root")
    product_root: Path | None = None
    try:
        if not isinstance(product_root_raw, str) or not product_root_raw.strip():
            raise ValueError("product_root is missing")
        product_root = safe_relative(workspace, product_root_raw)
        record("product_root_exists", product_root.is_dir(), str(product_root))
    except Exception as exc:
        record("product_root_is_safe", False, str(exc))

    product_files: list[str] = []
    if product_root is not None and product_root.is_dir():
        for path in sorted(product_root.rglob("*")):
            if path.is_file() and ".git" not in path.parts:
                product_files.append(path.relative_to(workspace).as_posix())
    record("product_contains_real_files", len(product_files) >= 2, product_files)
    record("product_is_bounded", 2 <= len(product_files) <= 60, len(product_files))

    markdown_files = [
        path.relative_to(workspace).as_posix()
        for path in workspace.rglob("*.md")
        if ".git" not in path.parts and ".codex" not in path.parts
    ]
    record("documentation_spiral_absent", len(markdown_files) <= 6, markdown_files)

    command_raw = result.get("start_command")
    command: list[str] = []
    if isinstance(command_raw, list) and command_raw and all(isinstance(item, str) and item for item in command_raw):
        command = list(command_raw)
    elif isinstance(command_raw, str) and command_raw.strip():
        command = shlex.split(command_raw)
    record("start_command_is_executable_shape", bool(command), command_raw)

    url = result.get("url") if isinstance(result.get("url"), str) else "http://127.0.0.1:8765"
    record("test_url_is_local", url.startswith("http://127.0.0.1:8765") or url.startswith("http://localhost:8765"), url)

    browser_evidence: dict[str, Any] = {}
    try:
        if not command or product_root is None:
            raise RuntimeError("cannot start product without a valid command and product root")
        environment = os.environ.copy()
        environment["PORT"] = "8765"
        environment["HOST"] = "127.0.0.1"
        server_log = workspace / ".company-os-test/server.log"
        server_log.parent.mkdir(parents=True, exist_ok=True)
        log_handle = server_log.open("w", encoding="utf-8")
        server = subprocess.Popen(
            command,
            cwd=product_root,
            env=environment,
            text=True,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
        )
        ready, ready_detail = wait_for_http(url)
        record("application_starts_on_port_environment", ready, ready_detail)
        if not ready:
            raise RuntimeError(ready_detail)

        from playwright.sync_api import sync_playwright

        note_text = "Autonomous note 7391"
        screenshot = workspace / ".company-os-test/browser-final.png"
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            page.goto(url, wait_until="networkidle")

            note_input = locate_note_input(page)
            add_button = locate_add_button(page)
            fill_note_input(note_input, note_text)
            add_button.click()
            page.get_by_text(note_text, exact=True).wait_for(state="visible", timeout=8000)
            browser_evidence["created_visible"] = True

            page.reload(wait_until="networkidle")
            page.get_by_text(note_text, exact=True).wait_for(state="visible", timeout=8000)
            browser_evidence["persisted_after_reload"] = True

            delete_note(page, note_text)
            page.get_by_text(note_text, exact=True).wait_for(state="hidden", timeout=8000)
            page.reload(wait_until="networkidle")
            page.get_by_text(note_text, exact=True).wait_for(state="hidden", timeout=8000)
            browser_evidence["deleted_and_absent_after_reload"] = True

            note_input = locate_note_input(page)
            add_button = locate_add_button(page)
            fill_note_input(note_input, "")
            add_button.click()
            page.wait_for_timeout(500)
            validation = visible_validation(page)
            if validation is None:
                raise AssertionError("empty note submission produced no visible validation")
            browser_evidence["empty_validation"] = validation

            page.screenshot(path=str(screenshot), full_page=True)
            browser.close()

        record("browser_create_journey_passes", browser_evidence.get("created_visible") is True, browser_evidence)
        record("browser_persistence_journey_passes", browser_evidence.get("persisted_after_reload") is True, browser_evidence)
        record("browser_delete_journey_passes", browser_evidence.get("deleted_and_absent_after_reload") is True, browser_evidence)
        record("browser_empty_validation_passes", bool(browser_evidence.get("empty_validation")), browser_evidence)
    except Exception as exc:
        record("independent_browser_journey", False, f"{type(exc).__name__}: {exc}")
    finally:
        if server is not None:
            server.terminate()
            try:
                server.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=5)

    passed = not failures
    report = {
        "objective_id": "signal-notes-micro",
        "passed": passed,
        "failures": failures,
        "checks": checks,
        "agent_result": result,
        "director_state": director,
        "navigation": navigation,
        "product_files": product_files,
        "browser_evidence": browser_evidence,
    }
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
