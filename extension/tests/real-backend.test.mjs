import assert from "node:assert/strict";
import { after, before, test } from "node:test";
import { spawn, spawnSync } from "node:child_process";
import { mkdtemp, rm } from "node:fs/promises";
import { createServer } from "node:net";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import puppeteer from "puppeteer";

const extensionDirectory = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "..",
);
const projectDirectory = path.resolve(extensionDirectory, "..");
const backendDirectory = path.join(projectDirectory, "backend");
const distributionDirectory = path.join(extensionDirectory, "dist");
let apiBaseUrl;
let backend;
let backendOutput = "";
let browser;
let browserSession;
let temporaryDirectory;

async function findAvailablePort() {
  const probe = createServer();
  await new Promise((resolve) => probe.listen(0, "127.0.0.1", resolve));
  const address = probe.address();
  assert.notEqual(address, null);
  assert.equal(typeof address, "object");
  await new Promise((resolve, reject) => {
    probe.close((error) => (error ? reject(error) : resolve()));
  });
  return address.port;
}

async function waitForBackend() {
  const url = new URL("/api/events", apiBaseUrl);
  url.searchParams.set("from", "2025-03-30T22:00:00Z");
  for (let attempt = 0; attempt < 50; attempt += 1) {
    try {
      const response = await fetch(url);
      if (response.ok) {
        return;
      }
    } catch {
      // The server is still starting.
    }
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  throw new Error(`Backend did not start:\n${backendOutput}`);
}

async function waitForExtension() {
  for (let attempt = 0; attempt < 50; attempt += 1) {
    const extension = (await browser.extensions()).values().next().value;
    if (extension) {
      return extension;
    }
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  return undefined;
}

async function openPopup() {
  const extension = await waitForExtension();
  assert.ok(extension, "BeeThere extension was not loaded");
  const popupTargetPromise = browser.waitForTarget(
    (target) =>
      target.type() === "page" && target.url().endsWith("/popup.html"),
  );
  const triggerPage = await browser.newPage();
  await extension.triggerAction(triggerPage);
  const popup = await (await popupTargetPromise).asPage();
  assert.ok(popup, "The action did not open a popup page");
  return { popup, triggerPage };
}

before(async () => {
  const port = await findAvailablePort();
  apiBaseUrl = `http://127.0.0.1:${port}`;
  temporaryDirectory = await mkdtemp(path.join(tmpdir(), "bee-there-e2e-"));
  const databasePath = path.join(temporaryDirectory, "bee-there.sqlite3");
  const sourceOrigin = `https://127.0.0.1:${port}`;
  const seedScript = `
from datetime import UTC, datetime
import os

from infrastructure.migrations import upgrade_database
from modules.events.contracts import EventDraft
from modules.events.domain import EventCategory
from modules.events.sqlite import SQLiteEventRepository
from modules.sources.contracts import SourceDraft
from modules.sources.sqlite import SQLiteSourceRepository

database_path = os.environ["BEE_THERE_DATABASE_PATH"]
source_origin = os.environ["BEE_THERE_TEST_SOURCE_ORIGIN"]
upgrade_database(database_path)
source = SQLiteSourceRepository(database_path).create(
    SourceDraft(name="Real Source", base_url=source_origin)
)
repository = SQLiteEventRepository(database_path)
for title, starts_at, path in (
    ("Later Event", datetime(2025, 3, 30, 23, 0, tzinfo=UTC), "later"),
    ("Past Event", datetime(2025, 3, 30, 21, 59, tzinfo=UTC), "past"),
    ("Boundary Event", datetime(2025, 3, 30, 22, 0, tzinfo=UTC), "boundary"),
):
    repository.upsert(
        EventDraft(
            title=title,
            summary=f"Summary for {title}.",
            category=EventCategory.COMMUNITY,
            starts_at=starts_at,
            location_name="Test Venue",
            source_id=source.id,
            source_url=f"{source_origin}/events/{path}",
            external_id=path,
        )
    )
`;
  const seed = spawnSync("uv", ["run", "python", "-c", seedScript], {
    cwd: backendDirectory,
    encoding: "utf8",
    env: {
      ...process.env,
      BEE_THERE_DATABASE_PATH: databasePath,
      BEE_THERE_TEST_SOURCE_ORIGIN: sourceOrigin,
      PYTHONPATH: path.join(backendDirectory, "src"),
    },
  });
  assert.equal(seed.status, 0, seed.stderr || seed.stdout);

  backend = spawn(
    "uv",
    [
      "run",
      "uvicorn",
      "main:app",
      "--app-dir",
      "src",
      "--host",
      "127.0.0.1",
      "--port",
      String(port),
    ],
    {
      cwd: backendDirectory,
      env: { ...process.env, BEE_THERE_DATABASE_PATH: databasePath },
      stdio: ["ignore", "pipe", "pipe"],
    },
  );
  backend.stdout.on("data", (chunk) => {
    backendOutput += chunk;
  });
  backend.stderr.on("data", (chunk) => {
    backendOutput += chunk;
  });
  await waitForBackend();

  const build = spawnSync("npm", ["run", "build"], {
    cwd: extensionDirectory,
    encoding: "utf8",
    env: { ...process.env, BEE_THERE_API_BASE_URL: apiBaseUrl },
  });
  assert.equal(build.status, 0, build.stderr || build.stdout);

  browser = await puppeteer.launch({
    enableExtensions: [distributionDirectory],
    headless: true,
  });
  browserSession = await browser.target().createCDPSession();
  browserSession.on("Target.attachedToTarget", (event) => {
    const session = browserSession.connection().session(event.sessionId);
    void (async () => {
      await session.send("Emulation.setTimezoneOverride", {
        timezoneId: "America/Los_Angeles",
      });
      await session.send("Emulation.setVirtualTimePolicy", {
        policy: "advance",
        initialVirtualTime: Date.parse("2025-03-30T22:30:00Z") / 1000,
      });
      await session.send("Runtime.runIfWaitingForDebugger");
    })().catch((error) => {
      if (!error.message.includes("Target closed")) {
        console.error(error);
      }
    });
  });
  await browserSession.send("Target.setAutoAttach", {
    autoAttach: true,
    flatten: true,
    waitForDebuggerOnStart: true,
  });
});

after(async () => {
  await browser?.close();
  if (backend && backend.exitCode === null) {
    backend.kill("SIGTERM");
    await new Promise((resolve) => backend.once("exit", resolve));
  }
  if (temporaryDirectory) {
    await rm(temporaryDirectory, { force: true, recursive: true });
  }
});

test("the real backend supplies ordered upcoming events and source links", async () => {
  const { popup, triggerPage } = await openPopup();
  await popup.waitForSelector(".event-card:nth-child(2)");
  const titles = await popup.$$eval(".event-title", (elements) =>
    elements.map((element) => element.textContent),
  );
  assert.deepEqual(titles, ["Boundary Event", "Later Event"]);

  const sourceUrl = `${apiBaseUrl.replace("http:", "https:")}/events/boundary`;
  await browserSession.send("Target.setAutoAttach", {
    autoAttach: false,
    flatten: true,
    waitForDebuggerOnStart: false,
  });
  const existingTargets = new Set(browser.targets());
  const sourceTargetPromise = browser.waitForTarget(
    (target) => target.type() === "page" && !existingTargets.has(target),
  );
  await popup.click(".event-card:first-child .event-source");
  const sourceTarget = await sourceTargetPromise;
  assert.notEqual(sourceTarget, popup.target());
  assert.equal(sourceTarget.url(), sourceUrl);

  await triggerPage.close();
});
