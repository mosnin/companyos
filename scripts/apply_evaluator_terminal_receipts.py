#!/usr/bin/env python3
from pathlib import Path


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one match, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def patch_runtime() -> None:
    path = Path("skills/company-os/elastic-company-os/scripts/native_task_runtime.py")
    replace_once(
        path,
        '            optional.update({"terminal_message_digest", "artifact_digests", "artifact_bindings"})',
        '            optional.update({"terminal_message_digest", "artifact_digests", "artifact_bindings", "evaluation_receipt_path"})',
        "evaluation receipt optional field",
    )
    old = '''                if artifact_digests is None:
                    normalized["artifact_digests"] = binding_digests
    else:
'''
    new = '''                if artifact_digests is None:
                    normalized["artifact_digests"] = binding_digests
            evaluation_receipt_path = normalized.get("evaluation_receipt_path")
            if evaluation_receipt_path is not None:
                evaluation_receipt_path = _text(evaluation_receipt_path, "evaluation_receipt_path")
                if evaluation_receipt_path.startswith("/") or "\\\\" in evaluation_receipt_path or any(
                    part in {"", ".", ".."} for part in evaluation_receipt_path.split("/")
                ):
                    raise RuntimeStateError("terminal evaluation receipt path is invalid")
                normalized["evaluation_receipt_path"] = evaluation_receipt_path
    else:
'''
    replace_once(path, old, new, "evaluation receipt validation")


def patch_tests() -> None:
    path = Path("skills/company-os/elastic-company-os/scripts/test_native_task_runtime.py")
    marker = '''    def test_cancellation_intent_is_separate_and_dominates_success(self):
'''
    addition = '''    def test_terminal_evaluation_receipt_path_is_typed_and_relative(self):
        completed = runtime.apply_event(
            self.running(),
            "terminal",
            source="host_observation",
            tool="read_task",
            task_id="task-1",
            thread_id="thread-1",
            status="succeeded",
            evaluation_receipt_path=".company-os/evaluations/gameplay.json",
        )
        self.assertEqual(
            completed["terminal"]["observation"]["evaluation_receipt_path"],
            ".company-os/evaluations/gameplay.json",
        )
        self.assertEqual(runtime.audit_state(completed), [])
        with self.assertRaises(runtime.RuntimeStateError):
            runtime.apply_event(
                self.running(),
                "terminal",
                source="host_observation",
                tool="read_task",
                task_id="task-1",
                thread_id="thread-1",
                status="succeeded",
                evaluation_receipt_path="/tmp/fake-evaluation.json",
            )

'''
    replace_once(path, marker, addition + marker, "evaluator terminal receipt test")


if __name__ == "__main__":
    patch_runtime()
    patch_tests()
