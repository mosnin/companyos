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
        '            optional.update({"terminal_message_digest", "artifact_digests"})',
        '            optional.update({"terminal_message_digest", "artifact_digests", "artifact_bindings"})',
        "terminal optional fields",
    )
    old = '''            artifact_digests = normalized.get("artifact_digests")
            if artifact_digests is not None and (
                not isinstance(artifact_digests, list)
                or any(not isinstance(item, str) or not item for item in artifact_digests)
            ):
                raise RuntimeStateError("terminal artifact digests are invalid")
'''
    new = '''            artifact_digests = normalized.get("artifact_digests")
            if artifact_digests is not None and (
                not isinstance(artifact_digests, list)
                or any(not isinstance(item, str) or not item for item in artifact_digests)
            ):
                raise RuntimeStateError("terminal artifact digests are invalid")
            artifact_bindings = normalized.get("artifact_bindings")
            if artifact_bindings is not None:
                if not isinstance(artifact_bindings, list) or not artifact_bindings:
                    raise RuntimeStateError("terminal artifact bindings are invalid")
                normalized_bindings = []
                seen_ids = set()
                for index, binding in enumerate(artifact_bindings):
                    if not isinstance(binding, Mapping) or set(binding) != {
                        "artifact_id", "artifact_class_id", "path", "sha256"
                    }:
                        raise RuntimeStateError("terminal artifact binding shape is invalid")
                    artifact_id = _text(binding.get("artifact_id"), f"artifact_bindings[{index}].artifact_id")
                    artifact_class_id = _text(binding.get("artifact_class_id"), f"artifact_bindings[{index}].artifact_class_id")
                    artifact_path = _text(binding.get("path"), f"artifact_bindings[{index}].path")
                    artifact_sha = _text(binding.get("sha256"), f"artifact_bindings[{index}].sha256")
                    if artifact_id in seen_ids:
                        raise RuntimeStateError("terminal artifact binding IDs must be unique")
                    if len(artifact_sha) != 64 or any(ch not in "0123456789abcdef" for ch in artifact_sha):
                        raise RuntimeStateError("terminal artifact binding sha256 is invalid")
                    if artifact_path.startswith("/") or "\\\\" in artifact_path or any(
                        part in {"", ".", ".."} for part in artifact_path.split("/")
                    ):
                        raise RuntimeStateError("terminal artifact binding path is invalid")
                    seen_ids.add(artifact_id)
                    normalized_bindings.append({
                        "artifact_id": artifact_id,
                        "artifact_class_id": artifact_class_id,
                        "path": artifact_path,
                        "sha256": artifact_sha,
                    })
                normalized_bindings.sort(key=lambda item: item["artifact_id"])
                normalized["artifact_bindings"] = normalized_bindings
                binding_digests = [item["sha256"] for item in normalized_bindings]
                if artifact_digests is not None and sorted(artifact_digests) != sorted(binding_digests):
                    raise RuntimeStateError("terminal artifact digests conflict with artifact bindings")
                if artifact_digests is None:
                    normalized["artifact_digests"] = binding_digests
'''
    replace_once(path, old, new, "terminal artifact validation")


def patch_tests() -> None:
    path = Path("skills/company-os/elastic-company-os/scripts/test_native_task_runtime.py")
    marker = '''    def test_cancellation_intent_is_separate_and_dominates_success(self):
'''
    addition = '''    def test_terminal_artifact_bindings_are_content_addressed_and_classified(self):
        bindings = [
            {
                "artifact_id": "build",
                "artifact_class_id": "interactive_experience",
                "path": "dist/game/index.html",
                "sha256": "a" * 64,
            },
            {
                "artifact_id": "audio",
                "artifact_class_id": "audio",
                "path": "dist/game/audio.ogg",
                "sha256": "b" * 64,
            },
        ]
        completed = runtime.apply_event(
            self.running(),
            "terminal",
            source="host_observation",
            tool="read_task",
            task_id="task-1",
            thread_id="thread-1",
            status="succeeded",
            artifact_bindings=list(reversed(bindings)),
        )
        payload = completed["terminal"]["observation"]
        self.assertEqual(payload["artifact_bindings"], bindings)
        self.assertEqual(payload["artifact_digests"], ["a" * 64, "b" * 64])
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
                artifact_digests=["c" * 64],
                artifact_bindings=bindings,
            )
        duplicate = [dict(bindings[0]), dict(bindings[0])]
        with self.assertRaises(runtime.RuntimeStateError):
            runtime.apply_event(
                self.running(),
                "terminal",
                source="host_observation",
                tool="read_task",
                task_id="task-1",
                thread_id="thread-1",
                status="succeeded",
                artifact_bindings=duplicate,
            )

'''
    replace_once(path, marker, addition + marker, "native runtime test insertion")


if __name__ == "__main__":
    patch_runtime()
    patch_tests()
