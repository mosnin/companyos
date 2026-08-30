import assert from "node:assert/strict";
import { execFileSync, spawnSync } from "node:child_process";
import {
  chmodSync,
  copyFileSync,
  existsSync,
  mkdtempSync,
  mkdirSync,
  readFileSync,
  rmSync,
  symlinkSync,
  writeFileSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const root = dirname(dirname(fileURLToPath(import.meta.url)));
const cli = join(root, "bin", "companyos.mjs");
const releaseIdentity = join(root, "scripts", "verify_release_identity.mjs");
const packageJson = JSON.parse(
  readFileSync(join(root, "package.json"), "utf8"),
);
const version = readFileSync(join(root, "VERSION"), "utf8").trim();

function run(...args) {
  return execFileSync(process.execPath, [cli, ...args], {
    cwd: root,
    encoding: "utf8",
  });
}

test("package and framework versions stay identical", () => {
  assert.equal(packageJson.version, version);
  assert.equal(run("version"), `${version}\n`);
});

test("help documents the safe install surface", () => {
  const output = run("help");
  assert.match(output, /companyos install --target/);
  assert.match(output, /never overwritten without exact prior-manifest proof/);
});

test("verify checks the package's committed distribution", () => {
  assert.match(run("verify"), /distribution manifest verified/);
});

test("install and check work in a disposable skills root", () => {
  const temporaryRoot = mkdtempSync(join(tmpdir(), "companyos-npm-test-"));
  const target = join(temporaryRoot, "skills");

  try {
    const installOutput = run("install", "--target", target);
    assert.match(installOutput, /distribution manifest verified/);
    assert.match(run("check", "--target", target), /matches canonical source/);
  } finally {
    rmSync(temporaryRoot, { recursive: true, force: true });
  }
});

test("unknown commands fail without invoking a shell", () => {
  const result = spawnSync(
    process.execPath,
    [cli, "not-a-command;echo unsafe"],
    {
      cwd: root,
      encoding: "utf8",
    },
  );

  assert.equal(result.status, 2);
  assert.match(result.stderr, /unknown command/);
  assert.doesNotMatch(result.stdout, /unsafe/);
});

function pythonStub(root, version, exitCode = 0) {
  const stub = join(root, "python-stub");
  writeFileSync(
    stub,
    `#!/usr/bin/env node
if (process.argv[2] === "-c") {
  process.stdout.write(${JSON.stringify(`${version}\n`)});
} else {
  const log = process.env.COMPANYOS_STUB_LOG;
  if (log) require("node:fs").writeFileSync(log, JSON.stringify(process.argv.slice(2)));
  process.exitCode = ${exitCode};
}
`,
  );
  chmodSync(stub, 0o755);
  return stub;
}

test("commands reject missing and unsupported Python before running the installer", () => {
  const temporaryRoot = mkdtempSync(join(tmpdir(), "companyos-python-test-"));
  try {
    const missing = spawnSync(process.execPath, [cli, "verify"], {
      cwd: root,
      encoding: "utf8",
      env: {
        ...process.env,
        COMPANYOS_PYTHON: join(temporaryRoot, "missing-python"),
      },
    });
    assert.equal(missing.status, 2);
    assert.match(missing.stderr, /was not found/);

    const unsupported = spawnSync(process.execPath, [cli, "verify"], {
      cwd: root,
      encoding: "utf8",
      env: {
        ...process.env,
        COMPANYOS_PYTHON: pythonStub(temporaryRoot, "3.10.14"),
      },
    });
    assert.equal(unsupported.status, 2);
    assert.match(unsupported.stderr, /Python 3\.11 or newer is required/);
  } finally {
    rmSync(temporaryRoot, { recursive: true, force: true });
  }
});

test("recover maps safely and child failures propagate unchanged", () => {
  const temporaryRoot = mkdtempSync(join(tmpdir(), "companyos-recover-test-"));
  const log = join(temporaryRoot, "arguments.json");
  try {
    const result = spawnSync(
      process.execPath,
      [cli, "recover", "--target", join(temporaryRoot, "skills")],
      {
        cwd: root,
        encoding: "utf8",
        env: {
          ...process.env,
          COMPANYOS_PYTHON: pythonStub(temporaryRoot, "3.11.9", 7),
          COMPANYOS_STUB_LOG: log,
        },
      },
    );
    assert.equal(result.status, 7);
    const forwarded = JSON.parse(readFileSync(log, "utf8"));
    assert.equal(forwarded[1], "recover-install");
    assert.deepEqual(forwarded.slice(2), [
      "--target",
      join(temporaryRoot, "skills"),
    ]);
  } finally {
    rmSync(temporaryRoot, { recursive: true, force: true });
  }
});

test("release tag is exactly bound to package, framework, and manifest versions", () => {
  assert.match(
    execFileSync(process.execPath, [releaseIdentity, "--tag", `v${version}`], {
      cwd: root,
      encoding: "utf8",
    }),
    new RegExp(`@mosnin/companyos@${version} is bound to v${version}`),
  );
  const mismatch = spawnSync(
    process.execPath,
    [releaseIdentity, "--tag", "v999.0.0"],
    { cwd: root, encoding: "utf8" },
  );
  assert.notEqual(mismatch.status, 0);
  assert.match(mismatch.stderr, new RegExp(`must be exactly v${version}`));

  const publishGate = spawnSync(
    process.execPath,
    [releaseIdentity, "--tag", `v${version}`, "--publish"],
    { cwd: root, encoding: "utf8" },
  );
  const licensed =
    packageJson.license !== "UNLICENSED" && existsSync(join(root, "LICENSE"));
  if (licensed) {
    assert.equal(publishGate.status, 0, publishGate.stderr);
    assert.match(
      publishGate.stdout,
      new RegExp(`@mosnin/companyos@${version} is bound to v${version}`),
    );
  } else {
    assert.notEqual(publishGate.status, 0);
    assert.match(publishGate.stderr, /publishing is blocked.*license/);
  }
});

test("publish identity rejects invalid SPDX expressions and license symlinks", () => {
  const fixtureRoot = mkdtempSync(join(root, ".release-identity-test-"));
  const fixtureScript = join(
    fixtureRoot,
    "scripts",
    "verify_release_identity.mjs",
  );
  const fixturePackage = join(fixtureRoot, "package.json");
  const fixtureLicense = join(fixtureRoot, "LICENSE");
  const runFixture = () =>
    spawnSync(
      process.execPath,
      [fixtureScript, "--tag", `v${version}`, "--publish"],
      { cwd: fixtureRoot, encoding: "utf8" },
    );

  try {
    mkdirSync(join(fixtureRoot, "scripts"));
    copyFileSync(releaseIdentity, fixtureScript);
    writeFileSync(join(fixtureRoot, "VERSION"), `${version}\n`);
    writeFileSync(
      join(fixtureRoot, "distribution-manifest.json"),
      `${JSON.stringify({ distribution_version: version })}\n`,
    );
    const fixtureMetadata = {
      name: "@mosnin/companyos",
      version,
      license: "MIT",
    };
    writeFileSync(fixturePackage, `${JSON.stringify(fixtureMetadata)}\n`);
    writeFileSync(
      fixtureLicense,
      "MIT License\n\nPermission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files to use, copy, modify, merge, publish, distribute, sublicense, and sell copies.\n",
    );
    assert.equal(runFixture().status, 0);

    writeFileSync(
      fixturePackage,
      `${JSON.stringify({ ...fixtureMetadata, license: "Banana" })}\n`,
    );
    const invalidExpression = runFixture();
    assert.notEqual(invalidExpression.status, 0);
    assert.match(invalidExpression.stderr, /chosen SPDX license/);

    writeFileSync(fixturePackage, `${JSON.stringify(fixtureMetadata)}\n`);
    rmSync(fixtureLicense);
    symlinkSync(join(root, "README.md"), fixtureLicense);
    const symlinkedLicense = runFixture();
    assert.notEqual(symlinkedLicense.status, 0);
    assert.match(symlinkedLicense.stderr, /regular license file/);
  } finally {
    rmSync(fixtureRoot, { recursive: true, force: true });
  }
});
