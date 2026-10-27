import { mkdir, readFile, readdir, rm, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { zipSync } from "fflate";

const extensionDirectory = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "..",
);
const distributionDirectory = path.join(extensionDirectory, "dist");
const releaseDirectory = path.join(extensionDirectory, "release");

await import("./build.mjs");

async function collectFiles(directory, prefix = "") {
  const files = {};
  const entries = await readdir(directory, { withFileTypes: true });
  for (const entry of entries.sort((left, right) =>
    left.name.localeCompare(right.name),
  )) {
    const sourcePath = path.join(directory, entry.name);
    const archivePath = prefix ? `${prefix}/${entry.name}` : entry.name;
    if (entry.isDirectory()) {
      Object.assign(files, await collectFiles(sourcePath, archivePath));
    } else if (entry.isFile()) {
      files[archivePath] = new Uint8Array(await readFile(sourcePath));
    }
  }
  return files;
}

const manifest = JSON.parse(
  await readFile(path.join(distributionDirectory, "manifest.json"), "utf8"),
);
const archiveName = `bee-there-chrome-${manifest.version}.zip`;
const archive = zipSync(await collectFiles(distributionDirectory), {
  level: 9,
  mtime: new Date("1980-01-01T00:00:00Z"),
});

await rm(releaseDirectory, { force: true, recursive: true });
await mkdir(releaseDirectory, { recursive: true });
await writeFile(path.join(releaseDirectory, archiveName), archive);
