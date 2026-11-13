import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { beforeEach, after, test } from "node:test";
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
  "bee-there-chrome-0.2.0.zip",
);

async function removeArtifacts() {
  await rm(distributionDirectory, { force: true, recursive: true });
  await rm(releaseDirectory, { force: true, recursive: true });
}

beforeEach(removeArtifacts);
after(removeArtifacts);

function runCommand(command, apiBaseUrl) {
  const env = { ...process.env };
  delete env.BEE_THERE_API_BASE_URL;
  if (apiBaseUrl !== undefined) {
    env.BEE_THERE_API_BASE_URL = apiBaseUrl;
  }
  return spawnSync("npm", ["run", command], {
    cwd: extensionDirectory,
    encoding: "utf8",
    env,
  });
}

async function readBundle(command) {
  if (command === "release") {
    const archive = unzipSync(await readFile(archivePath));
    return {
      manifest: JSON.parse(strFromU8(archive["manifest.json"])),
      config: strFromU8(archive["config.js"]),
    };
  }
  return {
    manifest: JSON.parse(
      await readFile(path.join(distributionDirectory, "manifest.json"), "utf8"),
    ),
    config: await readFile(path.join(distributionDirectory, "config.js"), "utf8"),
  };
}

for (const command of ["build", "release"]) {
  for (const apiBaseUrl of [
    "http://api.example.test",
    "http://192.168.1.1",
    "http://0.0.0.0",
    "http://[::]",
    "http://[fd00::1]",
    "http://localhost.evil.test",
    "http://127.0.0.1.evil.test",
    "http://[::ffff:127.0.0.1]",
    "http://localhost.",
  ]) {
    test(`${command} rejects a disallowed HTTP origin: ${apiBaseUrl}`, async () => {
      const result = runCommand(command, apiBaseUrl);

      assert.notEqual(result.status, 0);
      assert.match(result.stderr, /Error: API URL must use HTTPS/);
      await assert.rejects(
        readFile(path.join(distributionDirectory, "manifest.json")),
        { code: "ENOENT" },
      );
      await assert.rejects(readFile(archivePath), { code: "ENOENT" });
    });
  }

  for (const [apiBaseUrl, expectedOrigin] of [
    ["https://api.example.test", "https://api.example.test"],
    ["http://localhost:8000", "http://localhost:8000"],
    ["http://127.0.0.1:8000", "http://127.0.0.1:8000"],
    ["http://127.4.5.6:8000", "http://127.4.5.6:8000"],
    ["http://[::1]:8000", "http://[::1]:8000"],
    ["http://[0:0:0:0:0:0:0:1]:8000", "http://[::1]:8000"],
    ["http://LOCALHOST:8000", "http://localhost:8000"],
    ["http://127.1:8000", "http://127.0.0.1:8000"],
  ]) {
    test(`${command} accepts a secure or loopback origin: ${apiBaseUrl}`, async () => {
      const result = runCommand(command, apiBaseUrl);
      assert.equal(result.status, 0, result.stderr || result.stdout);

      const { manifest, config } = await readBundle(command);
      assert.deepEqual(manifest.host_permissions, [`${expectedOrigin}/*`]);
      assert.equal(
        config,
        `export const API_BASE_URL = ${JSON.stringify(expectedOrigin)};\n`,
      );
    });
  }

  for (const [apiBaseUrl, expectedError] of [
    [undefined, /Error: BEE_THERE_API_BASE_URL is required/],
    ["", /Error: BEE_THERE_API_BASE_URL is required/],
    ["not a URL", /Invalid URL/],
    ["ftp://api.example.test", /Error: API URL must use HTTP or HTTPS/],
  ]) {
    test(`${command} rejects invalid configuration: ${apiBaseUrl}`, () => {
      const result = runCommand(command, apiBaseUrl);
      assert.notEqual(result.status, 0);
      assert.match(result.stderr, expectedError);
    });
  }
}
