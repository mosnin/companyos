#!/usr/bin/env node

import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import {
  existsSync,
  mkdirSync,
  mkdtempSync,
  readFileSync,
  rmSync,
  statSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = dirname(dirname(fileURLToPath(import.meta.url)));
const packageJson = JSON.parse(
  readFileSync(join(root, "package.json"), "utf8"),
);
const version = readFileSync(join(root, "VERSION"), "utf8").trim();
const manifest = JSON.parse(
  readFileSync(join(root, "distribution-manifest.json"), "utf8"),
);
assert.equal(
  packageJson.version,
  version,
  "package.json and VERSION must match",
);
assert.equal(
  manifest.distribution_version,
  version,
  "distribution manifest and VERSION must match",
);

const temporaryRoot = mkdtempSync(join(tmpdir(), "companyos-package-gate-"));

try {
  const raw = execFileSync(
    "npm",
    ["pack", "--json", "--ignore-scripts", "--pack-destination", temporaryRoot],
    { cwd: root, encoding: "utf8" },
  );
  const [pack] = JSON.parse(raw);
  assert(pack, "npm pack returned no artifact metadata");
  const paths = pack.files.map((entry) => entry.path);
  const files = new Set(paths);
  assert.equal(
    files.size,
    paths.length,
    "npm package contains duplicate paths",
  );

  const runtimeFiles = [
    "package.json",
    "README.md",
    "VERSION",
    "distribution-manifest.json",
    "bin/companyos.mjs",
    "scripts/distribution.py",
  ];
  // npm always includes a conventional root license file, even when the
  // package `files` allowlist does not name it. Keep the exact-file gate
  // license-ready instead of forcing the release to weaken parity later.
  if (existsSync(join(root, "LICENSE"))) runtimeFiles.push("LICENSE");
  const manifestFiles = manifest.files.map((entry) => `skills/${entry.path}`);
  const expectedFiles = new Set([...runtimeFiles, ...manifestFiles]);
  assert.deepEqual(
    [...files].sort(),
    [...expectedFiles].sort(),
    "packed files must match the distribution manifest plus the release runtime files exactly",
  );

  for (const required of [
    "bin/companyos.mjs",
    "scripts/distribution.py",
    "distribution-manifest.json",
    "VERSION",
    "skills/company-os/company-os/SKILL.md",
    "skills/autonomy-suite/SKILL.md",
  ]) {
    assert(files.has(required), `npm package is missing ${required}`);
  }

  for (const entry of files) {
    assert(
      !entry.startsWith("tests/"),
      `npm package leaked test source: ${entry}`,
    );
    assert(
      !entry.startsWith("programs/"),
      `npm package leaked program evidence: ${entry}`,
    );
    assert(
      !entry.startsWith(".github/"),
      `npm package leaked CI source: ${entry}`,
    );
    assert(
      !entry.includes("/__pycache__/"),
      `npm package leaked Python cache: ${entry}`,
    );
    assert(
      !entry.endsWith(".pyc"),
      `npm package leaked Python bytecode: ${entry}`,
    );
    assert(
      !entry.endsWith(".pyo"),
      `npm package leaked Python bytecode: ${entry}`,
    );
  }

  const tarball = join(temporaryRoot, pack.filename);
  const consumer = join(temporaryRoot, "consumer");
  mkdirSync(consumer, { recursive: true });
  execFileSync(
    "npm",
    [
      "install",
      "--ignore-scripts",
      "--no-audit",
      "--no-fund",
      "--prefix",
      consumer,
      tarball,
    ],
    { encoding: "utf8" },
  );

  const installedBin = join(consumer, "node_modules", ".bin", "companyos");
  assert(
    (statSync(installedBin).mode & 0o111) !== 0,
    "installed companyos bin must remain executable",
  );
  const runInstalled = (...args) =>
    execFileSync(installedBin, args, { cwd: consumer, encoding: "utf8" });
  assert.equal(runInstalled("version"), `${version}\n`);
  assert.match(runInstalled("verify"), /distribution manifest verified/);

  const target = join(temporaryRoot, "installed-skills");
  assert.match(
    runInstalled("install", "--target", target),
    /distribution manifest verified/,
  );
  assert.match(
    runInstalled("check", "--target", target),
    /matches canonical source/,
  );

  process.stdout.write(
    `verified installed ${packageJson.name}@${version}: ${pack.entryCount} exact files, ${pack.unpackedSize} unpacked bytes\n`,
  );
} finally {
  rmSync(temporaryRoot, { recursive: true, force: true });
}
