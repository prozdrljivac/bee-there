import assert from "node:assert/strict";
import { after, afterEach, before, beforeEach, test } from "node:test";
import { spawnSync } from "node:child_process";
import { createServer } from "node:http";
import path from "node:path";
import { fileURLToPath } from "node:url";
import puppeteer from "puppeteer";

const extensionDirectory = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "..",
);
const distributionDirectory = path.join(extensionDirectory, "dist");
let apiBaseUrl;
let browser;
let server;
let browserSession;
const requests = [];
let responseEvents = [];

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

async function waitForRequest() {
  for (let attempt = 0; attempt < 50; attempt += 1) {
    if (requests.length > 0) {
      return requests[0];
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
  const page = await browser.newPage();
  await extension.triggerAction(page);

  const popupTarget = await popupTargetPromise;
  const popup = await popupTarget.asPage();
  assert.ok(popup, "The action did not open a popup page");
  await popup.waitForSelector("h1");
  return { popup, triggerPage: page };
}

before(async () => {
  server = createServer((request, response) => {
    requests.push(new URL(request.url, apiBaseUrl));
    response.writeHead(200, { "Content-Type": "application/json" });
    response.end(JSON.stringify(responseEvents));
  });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  const address = server.address();
  assert.notEqual(address, null);
  assert.equal(typeof address, "object");
  apiBaseUrl = `http://127.0.0.1:${address.port}`;

  const result = spawnSync("npm", ["run", "build"], {
    cwd: extensionDirectory,
    encoding: "utf8",
    env: { ...process.env, BEE_THERE_API_BASE_URL: apiBaseUrl },
  });
  assert.equal(result.status, 0, result.stderr || result.stdout);
});

beforeEach(async () => {
  requests.length = 0;
  responseEvents = [];
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

afterEach(async () => {
  await browser?.close();
});

after(async () => {
  await new Promise((resolve, reject) => {
    server?.close((error) => (error ? reject(error) : resolve()));
  });
});

test("the toolbar action opens a popup with the BeeThere heading", async () => {
  const { popup, triggerPage } = await openPopup();
  const heading = await popup.$eval("h1", (element) => element.textContent);
  assert.equal(heading, "BeeThere");
  await popup.close();
  await triggerPage.close();
});

test("the popup starts with an empty event list", async () => {
  const { popup, triggerPage } = await openPopup();
  const eventCount = await popup.$eval(
    "#event-list",
    (eventList) => eventList.children.length,
  );
  assert.equal(eventCount, 0);
  await popup.close();
  await triggerPage.close();
});

test("the popup requests events from the start of today in Belgrade", async () => {
  const { popup, triggerPage } = await openPopup();
  assert.equal(
    await popup.evaluate(
      () => Intl.DateTimeFormat().resolvedOptions().timeZone,
    ),
    "America/Los_Angeles",
  );

  const request = await waitForRequest();
  assert.ok(request, "The popup did not request events");
  assert.equal(request.pathname, "/api/events");
  assert.deepEqual([...request.searchParams], [
    ["from", "2025-03-30T22:00:00.000Z"],
  ]);
  await popup.close();
  await triggerPage.close();
});

test("the popup safely renders event cards in API order", async () => {
  responseEvents = [
    {
      id: "019a57c0-8800-7000-8000-000000000001",
      title: "Jazz <img src=x onerror=alert(1)>",
      summary: "Live jazz in the city centre.",
      category: "music",
      starts_at: "2025-03-31T17:30:00Z",
      ends_at: null,
      location_name: "Cultural Station",
      source_name: "Moj Novi Sad",
      source_url: "https://example.com/events/jazz",
    },
    {
      id: "019a57c0-8800-7000-8000-000000000002",
      title: "Spring Fair",
      summary: "Local makers and food.",
      category: "fair",
      starts_at: "2025-04-01T08:00:00Z",
      ends_at: "2025-04-01T12:00:00Z",
      location_name: "Liberty Square",
      source_name: "City Events",
      source_url: "https://example.org/events/spring-fair",
    },
  ];

  const { popup, triggerPage } = await openPopup();
  await popup.waitForSelector(".event-card:nth-child(2)");
  const cards = await popup.$$eval(".event-card", (elements) =>
    elements.map((card) => ({
      title: card.querySelector(".event-title").textContent,
      summary: card.querySelector(".event-summary").textContent,
      category: card.querySelector(".event-category").textContent,
      date: card.querySelector(".event-date").textContent,
      time: card.querySelector(".event-time").textContent,
      location: card.querySelector(".event-location").textContent,
      sourceName: card.querySelector(".event-source").textContent,
      sourceUrl: card.querySelector(".event-source").href,
    })),
  );

  assert.deepEqual(cards, [
    {
      title: "Jazz <img src=x onerror=alert(1)>",
      summary: "Live jazz in the city centre.",
      category: "Music",
      date: "31 March 2025",
      time: "19:30",
      location: "Cultural Station",
      sourceName: "Moj Novi Sad",
      sourceUrl: "https://example.com/events/jazz",
    },
    {
      title: "Spring Fair",
      summary: "Local makers and food.",
      category: "Fair",
      date: "1 April 2025",
      time: "10:00",
      location: "Liberty Square",
      sourceName: "City Events",
      sourceUrl: "https://example.org/events/spring-fair",
    },
  ]);
  assert.equal(await popup.$(".event-title img"), null);
  await popup.close();
  await triggerPage.close();
});
