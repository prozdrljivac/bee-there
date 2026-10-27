import assert from "node:assert/strict";
import { after, before, test } from "node:test";
import { spawnSync } from "node:child_process";
import { readFile, rm } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const extensionDirectory = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "..",
);
const distributionDirectory = path.join(extensionDirectory, "dist");

before(async () => {
  await rm(distributionDirectory, { force: true, recursive: true });
});

after(async () => {
  await rm(distributionDirectory, { force: true, recursive: true });
});

test("the build creates an installable action popup package", async () => {
  const result = spawnSync("npm", ["run", "build"], {
    cwd: extensionDirectory,
    encoding: "utf8",
  });

  assert.equal(result.status, 0, result.stderr || result.stdout);

  const manifest = JSON.parse(
    await readFile(path.join(distributionDirectory, "manifest.json"), "utf8"),
  );
  assert.deepEqual(manifest, {
    manifest_version: 3,
    name: "BeeThere",
    version: "0.1.0",
    action: { default_popup: "popup.html" },
  });
  await readFile(path.join(distributionDirectory, "popup.html"), "utf8");
});
