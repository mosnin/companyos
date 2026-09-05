#!/usr/bin/env python3
"""Company OS kernel protocol v1. Data packages only; never executes package code."""
import argparse
import base64
import contextlib
import fcntl
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import tarfile
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

PROTOCOL = 1
HOST_VERSION = "0.6.0"  # Distribution release, NOT the controller's state schema.
REGISTRY = "https://npm.pkg.github.com"
MAX_BYTES = 64 * 1024 * 1024
VERSION = r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)"
ID = r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def version(value):
    require(isinstance(value, str) and re.fullmatch(VERSION, value), "Expected stable x.y.z version")
    return tuple(map(int, value.split(".")))


def satisfies(value, constraint):
    """Deliberately small v1 grammar: exact, caret, tilde, or >=x.y.z <x.y.z."""
    current = version(value)
    require(isinstance(constraint, str), "Version constraint must be a string")
    if re.fullmatch(VERSION, constraint):
        return current == version(constraint)
    if constraint.startswith(("^", "~")):
        low = version(constraint[1:])
        if constraint[0] == "~":
            high = (low[0], low[1] + 1, 0)
        elif low[0]:
            high = (low[0] + 1, 0, 0)
        elif low[1]:
            high = (0, low[1] + 1, 0)
        else:
            high = (0, 0, low[2] + 1)
        return low <= current < high
    match = re.fullmatch(r">=(" + VERSION + r") <(" + VERSION + r")", constraint)
    require(match is not None, "Unsupported version constraint")
    low, high = version(match[1]), version(match[2])
    require(low < high, "Empty compatibility range")
    return low <= current < high


def kernel_id(value):
    require(isinstance(value, str) and len(value) <= 80 and re.fullmatch(ID, value), "Invalid kernel id")
    return value


def safe_path(value):
    require(isinstance(value, str) and value and "\\" not in value, "Invalid package path")
    parts = value.split("/")
    require(not any(p in ("", ".", "..") for p in parts), "Unsafe package path")
    require(not any(ord(c) < 32 or c == ":" for c in value), "Unsafe package path")
    return PurePosixPath(value)


def read_json(path):
    return json.loads(Path(path).read_text())


def validate(root, allow_draft=False, host=HOST_VERSION):
    root = Path(root)
    manifest = read_json(root / "company-os.kernel.json")
    allowed = {"schemaVersion", "id", "name", "version", "status", "companyOS", "entrypoints", "dependencies", "dataSchemaVersion", "permissions"}
    require(isinstance(manifest, dict) and set(manifest) == allowed, "Manifest fields do not match protocol v1")
    require(type(manifest["schemaVersion"]) is int and manifest["schemaVersion"] == PROTOCOL, "Unsupported kernel protocol")
    ident = kernel_id(manifest["id"])
    require(manifest["name"] == "@mosnin/" + ident, "Package must be scoped to @mosnin")
    version(manifest["version"])
    require(manifest["status"] in ("ready", "draft"), "Unknown release status")
    require(allow_draft or manifest["status"] == "ready", "Kernel is draft, not installable")
    require(satisfies(host, manifest["companyOS"]), "Kernel is incompatible with this Company OS release")
    require(type(manifest["dataSchemaVersion"]) is int and manifest["dataSchemaVersion"] >= 1, "Invalid data schema version")
    require(manifest["permissions"] == [], "Protocol v1 cannot grant permissions")
    entries = manifest["entrypoints"]
    require(isinstance(entries, list) and 0 < len(entries) <= 50 and len(set(entries)) == len(entries), "Kernel needs unique entrypoints")
    for entry in entries:
        rel = safe_path(entry)
        path = root / rel
        require(root.resolve() in path.resolve().parents and path.is_file() and not path.is_symlink(), "Missing or unsafe entrypoint")
    deps = manifest["dependencies"]
    require(isinstance(deps, dict) and len(deps) <= 32, "Invalid kernel dependencies")
    for dep, constraint in deps.items():
        require(kernel_id(dep) != ident, "Self dependency")
        version(constraint)  # exact dependencies make v1 reproducible and conflict detection explicit
    package = read_json(root / "package.json")
    require(package.get("name") == manifest["name"] and package.get("version") == manifest["version"], "Package and kernel identity disagree")
    require(package.get("publishConfig", {}).get("registry", "").rstrip("/") == REGISTRY, "Wrong publication registry")
    require(not package.get("dependencies") and not package.get("optionalDependencies"), "Use manifest kernel dependencies, not executable npm dependencies")
    require(not package.get("bin"), "Kernel packages cannot expose executables")
    require(not set(package.get("scripts", {})) & {"preinstall", "install", "postinstall", "prepare"}, "Lifecycle hooks are not allowed")
    return manifest


def digest_tree(root):
    result = {}
    for path in sorted(Path(root).rglob("*")):
        require(not path.is_symlink(), "Symlinks are not allowed")
        if path.is_file():
            result[path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def atomic_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".pending-", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump(data, stream, sort_keys=True, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise ValueError("Registry and MCP redirects are refused")


def fetch(url, token, payload=None):
    parsed = urllib.parse.urlsplit(url)
    require(parsed.scheme == "https" and not parsed.username and not parsed.password and not parsed.fragment, "HTTPS endpoint required")
    headers = {"Authorization": "Bearer " + token, "Accept": "application/json", "User-Agent": "company-os-kernels/1"}
    if payload is not None:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=None if payload is None else json.dumps(payload).encode(), headers=headers)
    try:
        with urllib.request.build_opener(NoRedirect).open(request, timeout=20) as response:
            data = response.read(MAX_BYTES + 1)
            require(len(data) <= MAX_BYTES, "Response exceeds size limit")
            return data
    except urllib.error.HTTPError as error:
        raise ValueError("Service refused request (HTTP %s)" % error.code) from None
    except urllib.error.URLError:
        raise ValueError("Service unavailable; previous installation retained") from None


class Registry:
    def __init__(self):
        self.token = os.environ.get("COMPANY_OS_REGISTRY_TOKEN", "")

    def metadata(self, ident):
        kernel_id(ident)
        require(self.token, "Set COMPANY_OS_REGISTRY_TOKEN with read:packages access")
        return json.loads(fetch(REGISTRY + "/" + urllib.parse.quote("@mosnin/" + ident, safe=""), self.token))

    def archive(self, release):
        url = release["dist"]["tarball"]
        require(urllib.parse.urlsplit(url).netloc == "npm.pkg.github.com", "Untrusted tarball host")
        return fetch(url, self.token)


def unpack(data, integrity, target):
    require(isinstance(integrity, str) and integrity.startswith("sha512-"), "SHA-512 integrity required")
    expected = base64.b64encode(hashlib.sha512(data).digest()).decode()
    require(integrity == "sha512-" + expected, "Package integrity mismatch")
    require(len(data) <= MAX_BYTES, "Archive too large")
    seen, total = set(), 0
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
        for count, member in enumerate(archive):
            require(count < 20000, "Too many archive entries")
            name = member.name.rstrip("/")
            rel = safe_path(name)
            require(rel.parts[0] == "package" and len(rel.parts) > 1 or name == "package", "Archive must be npm package rooted")
            require(name not in seen, "Duplicate archive member")
            seen.add(name)
            require(member.isdir() or member.isfile(), "Archive links and special files refused")
            require(not member.sparse, "Sparse files refused")
            total += member.size
            require(total <= MAX_BYTES and member.size >= 0, "Expanded archive exceeds limit")
            if name == "package":
                require(member.isdir(), "Invalid package root")
                continue
            dest = Path(target).joinpath(*rel.parts[1:])
            if member.isdir():
                dest.mkdir(parents=True, exist_ok=True)
            else:
                dest.parent.mkdir(parents=True, exist_ok=True)
                with archive.extractfile(member) as source, dest.open("xb") as output:
                    output.write(source.read())
                    output.flush()
                    os.fsync(output.fileno())


class KernelManager:
    def __init__(self, project, registry=None):
        self.project = Path(project).resolve()
        require(self.project.is_dir(), "Project directory does not exist")
        self.root = self.project / ".company-os" / "kernels"
        self.registry = registry or Registry()

    @contextlib.contextmanager
    def locked(self):
        # A user-controlled managed tree must not redirect writes elsewhere.
        for path in [self.project / ".company-os", self.root]:
            require(not path.is_symlink(), "Managed path cannot be a symlink")
        self.root.mkdir(parents=True, exist_ok=True)
        require(not (self.root / "operation.lock").is_symlink(), "Unsafe lock path")
        with (self.root / "operation.lock").open("a") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise ValueError("Another kernel operation is running") from None
            for name in ("objects", "history", "data", "overrides", "state.json"):
                require(not (self.root / name).is_symlink(), "Unsafe managed path")
            yield

    def state(self):
        path = self.root / "state.json"
        if path.exists():
            state = read_json(path)
            require(state.get("schemaVersion") == PROTOCOL, "Unknown installed-state protocol")
            return state
        return {"schemaVersion": PROTOCOL, "companyOSVersion": HOST_VERSION, "environmentId": str(uuid.uuid4()), "generation": 0, "installed": {}, "desired": {}}

    def verify(self, state):
        for ident, record in state["installed"].items():
            kernel_id(ident)
            require(re.fullmatch(r"[a-f0-9]{64}", record["object"]), "Invalid object id")
            root = self.root / "objects" / record["object"]
            require(root.is_dir() and not root.is_symlink(), "Installed object missing")
            require(digest_tree(root) == record["files"], "Installed kernel modified; preserve changes in overrides before updating")
            validate(root)

    def initialize(self, force=False):
        with self.locked():
            state = self.state()
            self.verify(state)
            state["companyOSVersion"] = HOST_VERSION
            previous = state.get("updateCheck", {})
            now = time.time()
            if force or not 0 <= now - previous.get("checkedAt", 0) < 86400:
                results = {}
                for ident, record in state["installed"].items():
                    try:
                        releases = self.registry.metadata(ident).get("versions", {})
                        constraint = state["desired"].get(ident, record["version"])
                        candidates = [v for v in releases if re.fullmatch(VERSION, v) and satisfies(v, constraint)]
                        latest = max(candidates, key=version) if candidates else None
                        results[ident] = {"status": "available" if latest and version(latest) > version(record["version"]) else "current" if latest else "unknown", "version": latest, "compatibility": "checked-on-install"}
                    except (ValueError, KeyError, TypeError, json.JSONDecodeError):
                        results[ident] = {"status": "unknown", "reason": "Registry unavailable or release metadata invalid"}
                state["updateCheck"] = {"checkedAt": now, "results": results}
            atomic_json(self.root / "state.json", state)
            return state

    def install(self, desired, binding=None):
        require(isinstance(desired, dict) and 0 < len(desired) <= 32, "Select 1 to 32 kernels")
        for ident, constraint in desired.items():
            kernel_id(ident)
            satisfies("0.0.0", constraint)
        with self.locked():
            state = self.state()
            self.verify(state)
            if binding:
                require(not state.get("companyId") or state["companyId"] == binding["companyId"], "Project already bound to a different company")
            selected, visiting = {}, set()
            with tempfile.TemporaryDirectory(prefix="stage-", dir=self.root) as temporary:
                def resolve(ident, constraint):
                    require(ident not in visiting, "Kernel dependency cycle")
                    if ident in selected:
                        require(satisfies(selected[ident]["version"], constraint), "Kernel version conflict")
                        return
                    require(len(selected) + len(visiting) < 32, "Dependency graph too large")
                    visiting.add(ident)
                    releases = self.registry.metadata(ident)["versions"]
                    candidates = [v for v in releases if re.fullmatch(VERSION, v) and satisfies(v, constraint)]
                    require(candidates, "No release satisfies " + ident + " " + constraint)
                    chosen = max(candidates, key=version)
                    release = releases[chosen]
                    dest = Path(temporary) / ident
                    dest.mkdir()
                    archive = self.registry.archive(release)
                    integrity = release["dist"]["integrity"]
                    unpack(archive, integrity, dest)
                    manifest = validate(dest)
                    require(manifest["id"] == ident and manifest["version"] == chosen, "Registry identity mismatch")
                    old = state["installed"].get(ident)
                    require(not old or old["dataSchemaVersion"] == manifest["dataSchemaVersion"], "Data migration requires an explicit migration plan")
                    require(not old or version(chosen) >= version(old["version"]), "Downgrade requires rollback, not update")
                    for dep, exact in manifest["dependencies"].items():
                        resolve(dep, exact)
                    selected[ident] = {"version": chosen, "integrity": integrity, "object": hashlib.sha256(archive).hexdigest(), "files": digest_tree(dest), "entrypoints": manifest["entrypoints"], "dataSchemaVersion": manifest["dataSchemaVersion"]}
                    visiting.remove(ident)
                # Existing roots stay installed; install is never an implicit uninstall.
                roots = {**state["desired"], **desired}
                for ident, constraint in sorted(roots.items()):
                    resolve(ident, constraint)
                objects = self.root / "objects"
                require(not objects.is_symlink(), "Unsafe objects directory")
                objects.mkdir(exist_ok=True)
                for ident, record in selected.items():
                    obj = objects / record["object"]
                    if obj.exists():
                        require(not obj.is_symlink() and digest_tree(obj) == record["files"], "Existing object corrupt")
                    else:
                        os.replace(Path(temporary) / ident, obj)
                        # Persist every containing directory before the state can refer to it.
                        directories = [p for p in obj.rglob("*") if p.is_dir()] + [obj, objects]
                        for directory in directories:
                            descriptor = os.open(directory, os.O_RDONLY)
                            try:
                                os.fsync(descriptor)
                            finally:
                                os.close(descriptor)
                generation = state["generation"] + 1
                atomic_json(self.root / "history" / (str(state["generation"]) + ".json"), state)
                updated = {**state, "companyOSVersion": HOST_VERSION, "generation": generation, "installed": selected, "desired": roots, "activatedAt": time.time()}
                if binding:
                    updated.update(companyId=binding["companyId"], desiredRevision=binding["revision"])
                else:
                    updated.pop("desiredRevision", None)
                for name in ("data", "overrides"):
                    (self.root / name).mkdir(exist_ok=True)
                updated.pop("updateCheck", None)
                atomic_json(self.root / "state.json", updated)  # single activation boundary
                return updated

    def rollback(self, generation):
        with self.locked():
            current = self.state()
            require(type(generation) is int and 0 <= generation < current["generation"], "Invalid rollback generation")
            previous = read_json(self.root / "history" / (str(generation) + ".json"))
            self.verify(previous)
            require(all(ident not in current["installed"] or item["dataSchemaVersion"] == current["installed"][ident]["dataSchemaVersion"] for ident, item in previous["installed"].items()), "Data schema rollback refused")
            atomic_json(self.root / "history" / (str(current["generation"]) + ".json"), current)
            previous.update(generation=current["generation"] + 1, rolledBackTo=generation, activatedAt=time.time())
            previous["companyOSVersion"] = HOST_VERSION
            previous.pop("desiredRevision", None)
            atomic_json(self.root / "state.json", previous)
            return previous


def mcp_call(name, arguments):
    endpoint = os.environ.get("COMPANY_OS_MCP_URL", "")
    token = os.environ.get("COMPANY_OS_MCP_TOKEN", "")
    require(endpoint and token, "Set COMPANY_OS_MCP_URL and COMPANY_OS_MCP_TOKEN")
    result = json.loads(fetch(endpoint, token, {"jsonrpc": "2.0", "id": str(uuid.uuid4()), "method": "tools/call", "params": {"name": name, "arguments": arguments}}))
    require("error" not in result, "MCP request refused")
    body = result["result"]
    require(not body.get("isError"), "MCP tool refused request")
    return json.loads(body["content"][0]["text"])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["init", "status", "check", "install", "update-kernels", "sync", "report", "rollback", "validate"])
    parser.add_argument("--project", default=".")
    parser.add_argument("--kernel")
    parser.add_argument("--version")
    parser.add_argument("--package")
    parser.add_argument("--generation", type=int)
    parser.add_argument("--allow-draft", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.command == "validate":
            require(args.package, "--package required")
            result = validate(args.package, args.allow_draft)
        else:
            manager = KernelManager(args.project)
            if args.command in ("init", "check"):
                result = manager.initialize(force=args.command == "check")
            elif args.command == "status":
                result = manager.state()
                manager.verify(result)
            elif args.command == "rollback":
                result = manager.rollback(args.generation)
            elif args.command in ("sync", "report"):
                remote = mcp_call("kernels_status", {})
                if args.command == "sync":
                    require(remote["desired"], "No kernels requested in the web app")
                    result = manager.install(remote["desired"], binding=remote)
                else:
                    result = manager.state()
                    manager.verify(result)
                    require(result.get("companyId") == remote["companyId"], "Report belongs to a different company")
                report = {"environmentId": result["environmentId"], "revision": result.get("desiredRevision", -1), "generation": result["generation"], "companyOSVersion": result["companyOSVersion"], "installed": [{"id": ident, "version": item["version"], "integrity": item["integrity"]} for ident, item in result["installed"].items()]}
                result = {"state": result, "receipt": mcp_call("kernels_report", report)}
            else:
                desired = manager.state()["desired"] if args.command == "update-kernels" else {}
                if args.kernel:
                    require(args.version, "--version required")
                    desired = {**desired, args.kernel: args.version}
                result = manager.install(desired)
        print(json.dumps({"ok": True, "result": result}, indent=2))
        return 0
    except (ValueError, OSError, KeyError, TypeError, tarfile.TarError) as error:
        # Network helpers intentionally redact response bodies, URLs and credentials.
        print(json.dumps({"ok": False, "error": str(error)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
