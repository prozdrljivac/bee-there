import assert from "node:assert/strict";
import { after, before, test } from "node:test";
import { spawn, spawnSync } from "node:child_process";
import { mkdir, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { createServer } from "node:net";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { unzipSync } from "fflate";
import puppeteer, { TargetCloseError } from "puppeteer";

const extensionDirectory = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "..",
);
const projectDirectory = path.resolve(extensionDirectory, "..");
const backendDirectory = path.join(projectDirectory, "backend");
const distributionDirectory = path.join(extensionDirectory, "dist");
const releaseDirectory = path.join(extensionDirectory, "release");
let apiBaseUrl;
let backend;
let backendOutput = "";
let browser;
let browserSession;
let installedExtensionDirectory;
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

  for (let attempt = 0; attempt < 50; attempt += 1) {
    try {
      const response = await fetch(url, {
        method: "QUERY",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ from: "2025-03-30T22:00:00Z" }),
      });
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
  await browserSession.send("Target.setAutoAttach", {
    autoAttach: true,
    flatten: true,
    waitForDebuggerOnStart: true,
  });
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

  await rm(distributionDirectory, { force: true, recursive: true });
  await rm(releaseDirectory, { force: true, recursive: true });
  const release = spawnSync("npm", ["run", "release"], {
    cwd: extensionDirectory,
    encoding: "utf8",
    env: { ...process.env, BEE_THERE_API_BASE_URL: apiBaseUrl },
  });
  assert.equal(release.status, 0, release.stderr || release.stdout);

  const archive = unzipSync(
    await readFile(path.join(releaseDirectory, "bee-there-chrome-0.2.0.zip")),
  );
  installedExtensionDirectory = path.join(
    temporaryDirectory,
    "installed-extension",
  );
  for (const [archivePath, contents] of Object.entries(archive)) {
    const destination = path.join(installedExtensionDirectory, archivePath);
    await mkdir(path.dirname(destination), { recursive: true });
    await writeFile(destination, contents);
  }

  browser = await puppeteer.launch({
    enableExtensions: [installedExtensionDirectory],
    headless: true,
  });
  browserSession = await browser.target().createCDPSession();
  browserSession.on("Target.attachedToTarget", (event) => {
    const session = browserSession.connection().session(event.sessionId);
    void (async () => {
      await session.send("Emulation.setTimezoneOverride", {
        timezoneId: "America/Los_Angeles",
      });
      // Freeze dates without pausing page loading, timers, or network requests.
      await session.send("Page.enable");
      await session.send("Page.addScriptToEvaluateOnNewDocument", {
        runImmediately: true,
        source: `(() => {
          const NativeDate = Date;
          const fixedTime = NativeDate.parse("2025-03-30T22:30:00Z");
          globalThis.Date = class extends NativeDate {
            constructor(...args) {
              super(...(args.length ? args : [fixedTime]));
            }
            static now() {
              return fixedTime;
            }
          };
        })();`,
      });
      await session.send("Runtime.runIfWaitingForDebugger");
    })().catch((error) => {
      if (!error.message.includes("Target closed")) {
        console.error(error);
      }
    });
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
  await rm(distributionDirectory, { force: true, recursive: true });
  await rm(releaseDirectory, { force: true, recursive: true });
});

function closeBeforeMouseReply(t, popup) {
  const mouseUp = popup.mouse.up.bind(popup.mouse);
  t.mock.method(popup.mouse, "up", async (...args) => {
    const popupClosed = new Promise((resolve) => popup.once("close", resolve));
    await mouseUp(...args);
    await popupClosed;
    // Model Chrome closing the popup before the mouse-release reply arrives.
    throw new TargetCloseError(
      "Protocol error (Input.dispatchMouseEvent): Target closed",
    );
  });
}

async function openSourceTab(popup, sourceUrl) {
  await browserSession.send("Target.setAutoAttach", {
    autoAttach: false,
    flatten: true,
    waitForDebuggerOnStart: false,
  });
  const existingTargets = new Set(browser.targets());
  const controller = new AbortController();
  const sourceTargetPromise = browser.waitForTarget(
    (target) =>
      target.type() === "page" &&
      !existingTargets.has(target) &&
      target.url() === sourceUrl,
    { signal: controller.signal },
  );
  try {
    const [sourceTarget] = await Promise.all([
      sourceTargetPromise,
      popup.click(".event-card:first-child .event-source").catch((error) => {
        // Opening a focused tab can close the action popup before CDP replies.
        if (!(error instanceof TargetCloseError) || !popup.isClosed()) {
          throw error;
        }
      }),
    ]);
    assert.notEqual(sourceTarget, popup.target());
    assert.equal(sourceTarget.url(), sourceUrl);
    const sourcePage = await sourceTarget.asPage();
    assert.ok(sourcePage, "The source link did not open a page");
    await sourcePage.close();
  } finally {
    controller.abort();
    await Promise.allSettled([sourceTargetPromise]);
  }
}

for (const closeDuringClick of [false, true]) {
  const scenario = closeDuringClick
    ? "popup closes during click"
    : "normal click";
  test(`the clean release bundle completes the real backend journey: ${scenario}`, async (t) => {
    const { popup, triggerPage } = await openPopup();
    try {
      await popup.waitForSelector(".event-card:nth-child(2)");
      const titles = await popup.$$eval(".event-title", (elements) =>
        elements.map((element) => element.textContent),
      );
      assert.deepEqual(titles, ["Boundary Event", "Later Event"]);

      if (closeDuringClick) {
        closeBeforeMouseReply(t, popup);
      }
      const sourceUrl = `${apiBaseUrl.replace("http:", "https:")}/events/boundary`;
      await openSourceTab(popup, sourceUrl);
    } finally {
      await triggerPage.close();
    }
  });
}

for (const error of [
  new Error("Unexpected input failure"),
  new TargetCloseError("The popup is still open"),
]) {
  test(`source navigation rejects input errors: ${error.message}`, async (t) => {
    const { popup, triggerPage } = await openPopup();
    try {
      t.mock.method(popup, "click", async () => {
        throw error;
      });
      const sourceUrl = `${apiBaseUrl.replace("http:", "https:")}/events/boundary`;
      await assert.rejects(
        openSourceTab(popup, sourceUrl),
        (actual) => actual === error,
      );
    } finally {
      await popup.close();
      await triggerPage.close();
    }
  });
}

test("discovery uses real server overlap, title search, category OR and all result pages", async () => {
  const seedScript = `
from datetime import UTC, datetime
import os
from modules.events.contracts import EventDraft
from modules.events.domain import EventCategory
from modules.events.sqlite import SQLiteEventRepository
from modules.sources.contracts import SourceDraft
from modules.sources.sqlite import SQLiteSourceRepository
path = os.environ["BEE_THERE_DATABASE_PATH"]
source = SQLiteSourceRepository(path).create(SourceDraft(name="Discovery fixture", base_url="https://discovery.example"))
repository = SQLiteEventRepository(path)
for index in range(44):
    repository.upsert(EventDraft(
        title=f"Jazz overlap {index}" if index < 43 else "Summary-only match",
        summary="jazz", category=EventCategory.MUSIC if index < 41 else EventCategory.THEATRE,
        starts_at=datetime(2025, 3, 30, 12, tzinfo=UTC), ends_at=datetime(2025, 4, 3, 12, tzinfo=UTC),
        location_name="Test Venue", source_id=source.id,
        source_url=f"https://discovery.example/events/{index}", external_id=str(index),
    ))
`;
  const seed = spawnSync("uv", ["run", "python", "-c", seedScript], {
    cwd: backendDirectory,
    encoding: "utf8",
    env: {
      ...process.env,
      BEE_THERE_DATABASE_PATH: path.join(
        temporaryDirectory,
        "bee-there.sqlite3",
      ),
      PYTHONPATH: path.join(backendDirectory, "src"),
    },
  });
  assert.equal(seed.status, 0, seed.stderr || seed.stdout);
  const { popup, triggerPage } = await openPopup();
  try {
    await popup.click("#toggle-filters");
    await popup.waitForSelector("#title-query");
    await popup.type("#title-query", "jAzZ");
    await popup.click("#category-trigger");
    await popup.click("#category-music");
    await popup.click("#category-theatre");
    await popup.keyboard.press("Escape");
    await popup.click("#date-trigger");
    await popup.click('[data-date="custom"]');
    await popup.type("#custom-start", "02 Apr 2025");
    await popup.keyboard.press("Escape");
    await popup.waitForFunction(() =>
      document.querySelector("#status").textContent.startsWith("20+ events"),
    );
    for (const count of [40, 43]) {
      await popup.$eval("#results", (el) => {
        el.scrollTop = el.scrollHeight;
      });
      await popup.waitForFunction(
        (count) => document.querySelectorAll(".event-card").length === count,
        {},
        count,
      );
    }
    const titles = await popup.$$eval(".event-title", (items) =>
      items.map((item) => item.textContent),
    );
    assert.equal(titles.length, 43);
    assert.ok(titles.every((title) => title.startsWith("Jazz overlap")));
    assert.equal(new Set(titles).size, 43);
    assert.deepEqual(
      (
        await popup.$$eval(".event-category", (items) => [
          ...new Set(items.map((item) => item.textContent)),
        ])
      ).sort(),
      ["MUSIC", "THEATRE"],
    );
  } finally {
    await popup.close();
    await triggerPage.close();
  }
});

function seedFavoriteEvents(mode = "initial") {
  const seed = spawnSync("uv", ["run", "python", "-c", `
from datetime import UTC, datetime, timedelta
import os
from modules.events.contracts import EventDraft
from modules.events.domain import EventCategory
from modules.events.sqlite import SQLiteEventRepository
from modules.sources.contracts import SourceDraft
from modules.sources.sqlite import SQLiteSourceRepository
path = os.environ["BEE_THERE_DATABASE_PATH"]
mode = os.environ["FAVORITES_FIXTURE_MODE"]
sources = SQLiteSourceRepository(path)
source = sources.get_by_base_url("https://favorites.example/")
if source is None:
    source = sources.create(SourceDraft(name="Favorite Events", base_url="https://favorites.example"))
repository = SQLiteEventRepository(path)
for index in (range(45) if mode == "initial" else [44]):
    starts = datetime(2025, 4, 2, 18, tzinfo=UTC) + timedelta(minutes=index)
    if mode == "unavailable":
        starts = datetime(2025, 3, 29, 18, tzinfo=UTC)
    repository.upsert(EventDraft(
        title=f"Favorite plan {index:02}" + (" updated" if mode != "initial" else ""),
        summary="A current listing from the real backend.",
        category=EventCategory.MUSIC, starts_at=starts,
        location_name="Updated Hall" if mode != "initial" else "First Hall",
        source_id=source.id, source_url=f"https://favorites.example/events/{index}",
        external_id=str(index),
    ))
`], {
    cwd: backendDirectory,
    encoding: "utf8",
    env: {
      ...process.env,
      BEE_THERE_DATABASE_PATH: path.join(temporaryDirectory, "bee-there.sqlite3"),
      PYTHONPATH: path.join(backendDirectory, "src"),
      FAVORITES_FIXTURE_MODE: mode,
    },
  });
  assert.equal(seed.status, 0, seed.stderr || seed.stdout);
}

test("favorites from distant pages persist and use current real backend listings", async () => {
  seedFavoriteEvents();
  let { popup, triggerPage } = await openPopup();
  const eventRequests = [];
  const recordEventRequests = page => page.on("request", request => {
    const url = new URL(request.url());
    if (url.pathname !== "/api/events") return;
    assert.equal(request.method(), "QUERY");
    assert.equal(request.headers()["content-type"], "application/json");
    assert.equal(url.search, "");
    eventRequests.push(JSON.parse(request.postData()));
  });
  recordEventRequests(popup);
  try {
    await popup.evaluate(() => {
      localStorage.removeItem("bee-there-discovery");
      localStorage.removeItem("bee-there-favorites");
    });
    await popup.reload();

    await popup.click("#toggle-filters");
    await popup.type("#title-query", "Favorite plan");
    await popup.waitForFunction(() =>
      document.querySelector("#status").textContent.startsWith("20+ events") &&
      document.querySelector(".event-title")?.textContent === "Favorite plan 00",
    );
    assert.deepEqual(eventRequests.at(-1), {
      from: "2025-03-30T22:00:00.000Z", q: "Favorite plan", limit: 20, offset: 0,
    });
    await popup.click(".event-card:first-child .favorite-action");
    for (const count of [40, 45]) {
      await popup.$eval("#results", element => {
        element.scrollTop = element.scrollHeight;
      });
      await popup.waitForFunction(
        count => document.querySelectorAll(".event-card").length === count,
        {}, count,
      );
    }
    await popup.click(".event-card:last-child .favorite-action");
    await popup.click("#category-trigger");
    await popup.click("#category-music");
    await popup.keyboard.press("Escape");
    await popup.click("#date-trigger");
    await popup.click('[data-date="custom"]');
    await popup.type("#custom-start", "02 Apr 2025");
    await popup.keyboard.press("Escape");
    await popup.click("#favorites-only");
    await popup.waitForFunction(() => document.querySelectorAll(".event-card").length === 2);
    assert.deepEqual(await popup.$$eval(".event-title", items => items.map(item => item.textContent)), [
      "Favorite plan 00", "Favorite plan 44",
    ]);
    const savedIds = await popup.evaluate(() => JSON.parse(localStorage.getItem("bee-there-favorites")));
    assert.equal(savedIds.length, 2);
    assert.deepEqual(eventRequests.at(-1), {
      event_ids: savedIds,
      from: "2025-04-01T22:00:00.000Z",
      to: "2025-04-02T22:00:00.000Z",
      q: "Favorite plan", category: ["music"], limit: 20, offset: 0,
    });
    await popup.close();
    await triggerPage.close();
    ({ popup, triggerPage } = await openPopup());
    recordEventRequests(popup);
    await popup.waitForSelector(".event-card:nth-child(2)");
    assert.equal(await popup.$eval("#discovery-filters", element => element.hidden), true);
    assert.equal(await popup.$eval("#favorites-only", element => element.getAttribute("aria-pressed")), "true");
    assert.equal(await popup.$$eval('.favorite-action[aria-pressed="true"]', items => items.length), 2);

    seedFavoriteEvents("updated");
    await popup.reload();
    await popup.waitForFunction(() => [...document.querySelectorAll(".event-title")].some(item => item.textContent === "Favorite plan 44 updated"));
    assert.equal(await popup.$eval(".event-card:last-child .event-location", element => element.textContent), "Updated Hall");

    seedFavoriteEvents("unavailable");
    await popup.reload();
    await popup.waitForFunction(() => document.querySelectorAll(".event-card").length === 1 && document.querySelector("#event-list").getAttribute("aria-busy") === "false");
    assert.deepEqual(await popup.evaluate(() => JSON.parse(localStorage.getItem("bee-there-favorites"))), savedIds);

    seedFavoriteEvents("returned");
    await popup.reload();
    await popup.waitForSelector('.event-card:nth-child(2) .favorite-action[aria-pressed="true"]');
    await popup.click(".event-card:first-child .favorite-action");
    await popup.waitForFunction(() => document.querySelectorAll(".event-card").length === 1 && document.querySelector(".event-title").textContent === "Favorite plan 44 updated");
    const remainingIds = await popup.evaluate(() => JSON.parse(localStorage.getItem("bee-there-favorites")));
    assert.equal(remainingIds.length, 1);
    await popup.click("#clear-all");
    await popup.waitForFunction(() => document.querySelector("#favorites-only").getAttribute("aria-pressed") === "false" && document.querySelector("#event-list").getAttribute("aria-busy") === "false");
    assert.deepEqual(eventRequests.at(-1), {
      from: "2025-03-30T22:00:00.000Z", limit: 20, offset: 0,
    });
    assert.deepEqual(await popup.evaluate(() => JSON.parse(localStorage.getItem("bee-there-favorites"))), remainingIds);
  } finally {
    if (!popup.isClosed()) await popup.close();
    await triggerPage.close();
  }
});
