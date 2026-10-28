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
  const apiBaseUrl = "http://127.0.0.1:43123";
  const result = spawnSync("npm", ["run", "build"], {
    cwd: extensionDirectory,
    encoding: "utf8",
    env: { ...process.env, BEE_THERE_API_BASE_URL: apiBaseUrl },
  });

  assert.equal(result.status, 0, result.stderr || result.stdout);

  const manifest = JSON.parse(
    await readFile(path.join(distributionDirectory, "manifest.json"), "utf8"),
  );
  assert.deepEqual(manifest, {
    manifest_version: 3,
    name: "BeeThere",
    version: "0.1.0",
    icons: {
      16: "assets/logo/beethere-icon-16.png",
      32: "assets/logo/beethere-icon-32.png",
      48: "assets/logo/beethere-icon-48.png",
      128: "assets/logo/beethere-icon-128.png",
    },
    action: {
      default_popup: "popup.html",
      default_title: "BeeThere",
      default_icon: {
        16: "assets/logo/beethere-icon-16.png",
        32: "assets/logo/beethere-icon-32.png",
        48: "assets/logo/beethere-icon-48.png",
      },
    },
    host_permissions: [`${apiBaseUrl}/*`],
  });
  assert.equal(
    await readFile(path.join(distributionDirectory, "config.js"), "utf8"),
    `export const API_BASE_URL = ${JSON.stringify(apiBaseUrl)};\n`,
  );
  await readFile(path.join(distributionDirectory, "popup.html"), "utf8");
  for (const size of [16, 32, 48, 128]) {
    const icon = await readFile(
      path.join(
        distributionDirectory,
        "assets",
        "logo",
        `beethere-icon-${size}.png`,
      ),
    );
    assert.ok(icon.length > 0);
  }
});
