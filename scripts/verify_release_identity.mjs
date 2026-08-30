#!/usr/bin/env node

import assert from "node:assert/strict";
import { lstatSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import parseSpdxExpression from "spdx-expression-parse";

const root = dirname(dirname(fileURLToPath(import.meta.url)));
const packageJson = JSON.parse(
  readFileSync(join(root, "package.json"), "utf8"),
);
const version = readFileSync(join(root, "VERSION"), "utf8").trim();
const manifest = JSON.parse(
  readFileSync(join(root, "distribution-manifest.json"), "utf8"),
);
const tagIndex = process.argv.indexOf("--tag");
const tag =
  tagIndex >= 0 ? process.argv[tagIndex + 1] : process.env.GITHUB_REF_NAME;

assert.equal(packageJson.name, "@mosnin/companyos", "unexpected package name");
assert.equal(packageJson.version, version, "package.json and VERSION differ");
assert.equal(
  manifest.distribution_version,
  version,
  "distribution manifest and VERSION differ",
);
assert(tag, "release tag is required through --tag or GITHUB_REF_NAME");
assert.equal(
  tag,
  `v${version}`,
  `release tag must be exactly v${version}, received ${tag}`,
);
if (process.argv.includes("--publish")) {
  const licenseExpression = String(packageJson.license ?? "").trim();
  let parsedLicense;
  try {
    parsedLicense = parseSpdxExpression(licenseExpression);
  } catch {
    parsedLicense = null;
  }
  assert(
    licenseExpression &&
      licenseExpression !== "UNLICENSED" &&
      !licenseExpression.startsWith("SEE LICENSE IN ") &&
      parsedLicense,
    "publishing is blocked until package.json names the maintainer's chosen SPDX license",
  );
  const licensePath = join(root, "LICENSE");
  let licenseStat;
  let licenseText = "";
  try {
    licenseStat = lstatSync(licensePath);
    licenseText = readFileSync(licensePath, "utf8").trim();
  } catch {
    assert.fail(
      "publishing is blocked until the chosen root LICENSE is committed",
    );
  }
  assert(
    !licenseStat.isSymbolicLink() &&
      licenseStat.isFile() &&
      licenseText.length >= 100,
    "publishing is blocked until LICENSE is a nonempty regular license file",
  );
}

process.stdout.write(`${packageJson.name}@${version} is bound to ${tag}\n`);
