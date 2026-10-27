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
let responseHandler;

function respondWithJson(response, body = responseEvents, statusCode = 200) {
  response.writeHead(statusCode, { "Content-Type": "application/json" });
  response.end(JSON.stringify(body));
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
    responseHandler(request, response);
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
  responseHandler = (_request, response) => respondWithJson(response);
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

test("the toolbar action opens the BeeThere visual shell", async () => {
  const { popup, triggerPage } = await openPopup();
  const shell = await popup.$eval(".popup", (element) => ({
    brand: element.querySelector(".brand").textContent.trim(),
    width: getComputedStyle(element).width,
  }));
  assert.deepEqual(shell, { brand: "BeeThere", width: "420px" });
  await popup.close();
  await triggerPage.close();
});

test("the popup starts with no event cards", async () => {
  const { popup, triggerPage } = await openPopup();
  assert.equal(await popup.$$(".event-card").then((items) => items.length), 0);
  await popup.close();
  await triggerPage.close();
});

test("the popup shows loading feedback while events are pending", async () => {
  let pendingResponse;
  responseHandler = (_request, response) => {
    pendingResponse = response;
  };

  const { popup, triggerPage } = await openPopup();
  await waitForRequest();
  assert.equal(
    await popup.$eval("#status", (status) => status.textContent),
    "Loading events…",
  );
  assert.equal(await popup.$$(".skeleton").then((items) => items.length), 2);
  assert.equal(
    await popup.$eval("#event-list", (list) => list.getAttribute("aria-busy")),
    "true",
  );

  respondWithJson(pendingResponse);
  await popup.waitForFunction(
    () => document.querySelector("#status").textContent !== "Loading events…",
  );
  assert.equal(await popup.$(".skeleton"), null);
  assert.equal(
    await popup.$eval("#event-list", (list) => list.getAttribute("aria-busy")),
    "false",
  );
  await popup.close();
  await triggerPage.close();
});

test("the popup shows a message when no events are available", async () => {
  const { popup, triggerPage } = await openPopup();
  await popup.waitForFunction(
    () => document.querySelector("#status").textContent !== "Loading events…",
  );
  assert.equal(
    await popup.$eval("#status", (status) => status.textContent),
    "No upcoming events.",
  );
  assert.deepEqual(
    await popup.$eval(".state", (state) => ({
      title: state.querySelector("h3").textContent,
      message: state.querySelector("p").textContent,
    })),
    {
      title: "A quiet moment.",
      message:
        "No upcoming events right now. Come back soon for your next good plan.",
    },
  );
  assert.equal(await popup.$("#retry"), null);
  await popup.close();
  await triggerPage.close();
});

test("the popup retries after a network error", async () => {
  let attempt = 0;
  responseHandler = (_request, response) => {
    attempt += 1;
    if (attempt === 1) {
      response.destroy();
      return;
    }
    respondWithJson(response, [
      {
        id: "019a57c0-8800-7000-8000-000000000003",
        title: "Recovered Event",
        summary: "Available after retry.",
        category: "community",
        starts_at: "2025-03-31T18:00:00Z",
        ends_at: null,
        location_name: "Community Centre",
        source_name: "City Events",
        source_url: "https://example.org/events/recovered",
      },
    ]);
  };

  const { popup, triggerPage } = await openPopup();
  await popup.waitForSelector("#retry");
  assert.equal(
    await popup.$eval("#status", (status) => status.textContent),
    "Could not load events.",
  );
  assert.deepEqual(
    await popup.$eval(".state", (state) => ({
      title: state.querySelector("h3").textContent,
      message: state.querySelector("p").textContent,
      retry: state.querySelector("button").textContent,
    })),
    {
      title: "A small bump in the road.",
      message: "We could not load the events. Please try again.",
      retry: "Try again",
    },
  );
  assert.equal(requests.length, 1);

  await popup.click("#retry");
  await popup.waitForSelector(".event-card");
  assert.equal(
    await popup.$eval(".event-title", (title) => title.textContent),
    "Recovered Event",
  );
  assert.equal(await popup.$("#retry"), null);
  assert.equal(requests.length, 2);
  await popup.close();
  await triggerPage.close();
});

test("the popup reports a non-success API response", async () => {
  responseHandler = (_request, response) => {
    respondWithJson(response, [], 503);
  };

  const { popup, triggerPage } = await openPopup();
  await popup.waitForSelector("#retry");
  assert.equal(
    await popup.$eval("#status", (status) => status.textContent),
    "Could not load events.",
  );
  assert.equal(await popup.$(".event-card"), null);
  await popup.close();
  await triggerPage.close();
});

test("the popup reports invalid API response data", async () => {
  responseEvents = [
    {
      id: "019a57c0-8800-7000-8000-000000000004",
      title: 42,
      summary: "The title has the wrong type.",
      category: "other",
      starts_at: "2025-03-31T18:00:00Z",
      ends_at: null,
      location_name: null,
      source_name: "City Events",
      source_url: "https://example.org/events/invalid",
    },
  ];

  const { popup, triggerPage } = await openPopup();
  await popup.waitForSelector("#retry");
  assert.equal(
    await popup.$eval("#status", (status) => status.textContent),
    "Could not load events.",
  );
  assert.equal(await popup.$(".event-card"), null);
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
      category: "MUSIC",
      date: "31 March 2025",
      time: "19:30",
      location: "Cultural Station",
      sourceName: "Moj Novi Sad ↗",
      sourceUrl: "https://example.com/events/jazz",
    },
    {
      title: "Spring Fair",
      summary: "Local makers and food.",
      category: "FAIR",
      date: "1 April 2025",
      time: "10:00–14:00",
      location: "Liberty Square",
      sourceName: "City Events ↗",
      sourceUrl: "https://example.org/events/spring-fair",
    },
  ]);
  assert.deepEqual(
    await popup.$eval(".event-card", (card) => ({
      classes: card.className,
      month: card.querySelector(".date-tile span").textContent,
      day: card.querySelector(".date-tile strong").textContent,
      hasLocationIcon: card.querySelector(".location-icon") !== null,
      sourceLabel: card.querySelector(".event-source").ariaLabel,
    })),
    {
      classes: "event event-card",
      month: "Mar",
      day: "31",
      hasLocationIcon: true,
      sourceLabel: "Open Moj Novi Sad source website (opens a new tab)",
    },
  );
  assert.equal(await popup.$(".event-title img"), null);
  await popup.close();
  await triggerPage.close();
});
