#!/usr/bin/env node

import { spawnSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const packageRoot = dirname(dirname(fileURLToPath(import.meta.url)));
const version = readFileSync(join(packageRoot, "VERSION"), "utf8").trim();

const commands = new Map([
  ["verify", "verify-manifest"],
  ["install", "install"],
  ["check", "check-install"],
  ["recover", "recover-install"],
]);

function printHelp() {
  process.stdout.write(`Company OS ${version}

Usage:
  companyos install --target /absolute/path/to/skills
  companyos check --target /absolute/path/to/skills
  companyos recover --target /absolute/path/to/skills
  companyos verify
  companyos version

Company OS installs two verified skill bundles: company-os and autonomy-suite.
Existing installations are never overwritten without exact prior-manifest proof.
Documentation: https://docs.companyos.sh
`);
}

function fail(message) {
  process.stderr.write(`companyos: ${message}\n`);
  process.exitCode = 2;
}

function pythonVersion(python) {
  const probe = spawnSync(
    python,
    [
      "-c",
      "import sys; print('.'.join(str(part) for part in sys.version_info[:3]))",
    ],
    {
      cwd: packageRoot,
      env: process.env,
      encoding: "utf8",
      shell: false,
    },
  );
  if (probe.error) {
    fail(
      probe.error.code === "ENOENT"
        ? `${python} was not found. Install Python 3.11 or set COMPANYOS_PYTHON.`
        : `could not start ${python}: ${probe.error.message}`,
    );
    return null;
  }
  if (probe.status !== 0) {
    fail(`${python} could not report its version.`);
    return null;
  }
  const match = probe.stdout.trim().match(/^(\d+)\.(\d+)\.(\d+)$/);
  if (!match) {
    fail(`${python} returned an unreadable version.`);
    return null;
  }
  const [, majorText, minorText] = match;
  const major = Number(majorText);
  const minor = Number(minorText);
  if (major < 3 || (major === 3 && minor < 11)) {
    fail(
      `Python 3.11 or newer is required. ${python} is ${probe.stdout.trim()}.`,
    );
    return null;
  }
  return probe.stdout.trim();
}

const [requested = "help", ...args] = process.argv.slice(2);

if (requested === "help" || requested === "--help" || requested === "-h") {
  printHelp();
} else if (
  requested === "version" ||
  requested === "--version" ||
  requested === "-v"
) {
  process.stdout.write(`${version}\n`);
} else if (!commands.has(requested)) {
  fail(`unknown command "${requested}". Run "companyos help" for usage.`);
} else if (process.platform === "win32") {
  fail(
    "this release supports macOS and Linux. The transactional installer requires POSIX file locking.",
  );
} else {
  const python = process.env.COMPANYOS_PYTHON || "python3";
  if (pythonVersion(python)) {
    const result = spawnSync(
      python,
      [
        join(packageRoot, "scripts", "distribution.py"),
        commands.get(requested),
        ...args,
      ],
      {
        cwd: packageRoot,
        env: process.env,
        stdio: "inherit",
        shell: false,
      },
    );

    if (result.error) {
      fail(`could not start ${python}: ${result.error.message}`);
    } else {
      process.exitCode = result.status ?? 1;
    }
  }
}
