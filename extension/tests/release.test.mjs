import assert from "node:assert/strict";
import { after, before, test } from "node:test";
import { spawnSync } from "node:child_process";
import { readFile, rm } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { strFromU8, unzipSync } from "fflate";

const extensionDirectory = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "..",
);
const distributionDirectory = path.join(extensionDirectory, "dist");
const releaseDirectory = path.join(extensionDirectory, "release");
const archivePath = path.join(
  releaseDirectory,
  "bee-there-chrome-0.1.0.zip",
);

before(async () => {
  await rm(distributionDirectory, { force: true, recursive: true });
  await rm(releaseDirectory, { force: true, recursive: true });
});

after(async () => {
  await rm(distributionDirectory, { force: true, recursive: true });
  await rm(releaseDirectory, { force: true, recursive: true });
});

test("the release command creates a minimal Chrome upload archive", async () => {
  const apiBaseUrl = "https://api.example.test";
  const result = spawnSync("npm", ["run", "release"], {
    cwd: extensionDirectory,
    encoding: "utf8",
    env: { ...process.env, BEE_THERE_API_BASE_URL: apiBaseUrl },
  });
  assert.equal(result.status, 0, result.stderr || result.stdout);

  const archive = unzipSync(await readFile(archivePath));
  assert.deepEqual(Object.keys(archive).sort(), [
    "config.js",
    "manifest.json",
    "popup.css",
    "popup.html",
    "popup.js",
    "theme.js",
  ]);
  assert.deepEqual(JSON.parse(strFromU8(archive["manifest.json"])), {
    manifest_version: 3,
    name: "BeeThere",
    version: "0.1.0",
    action: { default_popup: "popup.html" },
    host_permissions: [`${apiBaseUrl}/*`],
  });
  for (const contents of Object.values(archive)) {
    assert.ok(contents.length > 0);
  }
});
