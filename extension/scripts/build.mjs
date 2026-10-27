import { cp, mkdir, readFile, rm, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const extensionDirectory = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "..",
);
const sourceDirectory = path.join(extensionDirectory, "src");
const distributionDirectory = path.join(extensionDirectory, "dist");
const configuredApiBaseUrl = process.env.BEE_THERE_API_BASE_URL;

if (!configuredApiBaseUrl) {
  throw new Error("BEE_THERE_API_BASE_URL is required");
}

const apiUrl = new URL(configuredApiBaseUrl);
if (apiUrl.protocol !== "http:" && apiUrl.protocol !== "https:") {
  throw new Error("BEE_THERE_API_BASE_URL must use HTTP or HTTPS");
}
const apiBaseUrl = apiUrl.origin;

await rm(distributionDirectory, { force: true, recursive: true });
await mkdir(distributionDirectory, { recursive: true });
await cp(sourceDirectory, distributionDirectory, { recursive: true });

const manifestPath = path.join(distributionDirectory, "manifest.json");
const manifest = JSON.parse(await readFile(manifestPath, "utf8"));
manifest.host_permissions = [`${apiBaseUrl}/*`];
await writeFile(manifestPath, `${JSON.stringify(manifest, null, 2)}\n`);
await writeFile(
  path.join(distributionDirectory, "config.js"),
  `export const API_BASE_URL = ${JSON.stringify(apiBaseUrl)};\n`,
);
