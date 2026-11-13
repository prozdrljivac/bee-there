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

async function openPopup({ expandFilters = true } = {}) {
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
  if (expandFilters) await popup.click("#toggle-filters");
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
    args: ["--window-size=1280,1000"],
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

test("a plain text button shows and hides filters without loading results", async () => {
  const { popup } = await openPopup({ expandFilters: false });
  await popup.waitForFunction(
    () =>
      document.querySelector("#event-list").getAttribute("aria-busy") ===
      "false",
  );
  const requestCount = requests.length;
  const collapsedHeight = await popup.$eval("#results", (el) => el.clientHeight);
  assert.equal(
    await popup.$eval("#discovery-filters", (el) => el.hidden),
    true,
  );
  assert.equal(
    await popup.$eval("#toggle-filters", (el) => el.textContent.trim()),
    "Show filters",
  );
  assert.equal(
    await popup.$eval("#toggle-filters", (el) => el.getAttribute("aria-expanded")),
    "false",
  );
  assert.equal(
    await popup.$eval("#toggle-filters", (el) => el.getAttribute("aria-controls")),
    "discovery-filters",
  );
  await popup.focus("#toggle-filters");
  await popup.keyboard.press("Enter");
  assert.equal(
    await popup.$eval("#discovery-filters", (el) => el.hidden),
    false,
  );
  assert.equal(
    await popup.$eval("#toggle-filters", (el) => el.textContent.trim()),
    "Hide filters",
  );
  assert.equal(
    await popup.$eval("#toggle-filters", (el) => el.getAttribute("aria-expanded")),
    "true",
  );
  const expandedHeight = await popup.$eval("#results", (el) => el.clientHeight);
  assert.ok(collapsedHeight > expandedHeight);
  assert.equal(
    await popup.evaluate(() => document.activeElement.id),
    "toggle-filters",
  );
  await popup.keyboard.press("Space");
  assert.equal(
    await popup.$eval("#discovery-filters", (el) => el.hidden),
    true,
  );
  await popup.keyboard.press("Tab");
  assert.equal(
    await popup.evaluate(() =>
      document.activeElement.closest("#discovery-filters"),
    ),
    null,
  );
  assert.equal(requests.length, requestCount);
  assert.deepEqual(
    await popup.$eval("#toggle-filters", (el) => ({
      icons: el.querySelectorAll("img, svg").length,
      border: getComputedStyle(el).borderTopWidth,
    })),
    { icons: 0, border: "0px" },
  );
});

test("hiding filters closes their menus and keeps the applied choices", async () => {
  const { popup } = await openPopup();
  await popup.type("#title-query", "jazz");
  await popup.click("#category-trigger");
  await popup.click("#category-music");
  await popup.keyboard.press("Escape");
  await popup.click("#date-trigger");
  await popup.click('[data-date="tomorrow"]');
  await popup.waitForFunction(
    () =>
      document.querySelector("#event-list").getAttribute("aria-busy") ===
      "false",
  );
  const requestCount = requests.length;
  const choices = await popup.evaluate(() =>
    localStorage.getItem("bee-there-discovery"),
  );
  for (const menu of ["category", "date", "custom"]) {
    await popup.click(menu === "category" ? "#category-trigger" : "#date-trigger");
    if (menu === "custom") await popup.click('[data-date="custom"]');
    await popup.focus("#toggle-filters");
    await popup.keyboard.press("Enter");
    assert.equal(
      await popup.$eval(`#${menu}-menu`, (el) => el.hidden),
      true,
      `${menu} menu stays hidden`,
    );
    assert.equal(
    await popup.evaluate(() => document.activeElement.id),
    "toggle-filters",
  );
    assert.equal(
      await popup.$eval("#toggle-filters", (el) => el.textContent.trim()),
      "Show filters",
    );
    assert.equal(
      await popup.$eval("#category-trigger", (el) => el.getAttribute("aria-expanded")),
      "false",
    );
    assert.equal(
      await popup.$eval("#date-trigger", (el) => el.getAttribute("aria-expanded")),
      "false",
    );
    await popup.click("#toggle-filters");
  }
  assert.equal(
    await popup.$eval("#title-query", (el) => el.value),
    "jazz",
  );
  assert.equal(
    await popup.$eval("#category-music", (el) => el.checked),
    true,
  );
  assert.equal(
    await popup.$eval("#date-trigger span", (el) => el.textContent),
    "Tomorrow",
  );
  assert.equal(
    await popup.evaluate(() => localStorage.getItem("bee-there-discovery")),
    choices,
  );
  assert.equal(requests.length, requestCount);
});

test("restored filters start hidden and Clear all keeps focus on a visible control", async () => {
  const { popup } = await openPopup({ expandFilters: false });
  await popup.evaluate(() =>
    localStorage.setItem("bee-there-discovery", JSON.stringify({
      query: "jazz",
      categories: ["music"],
      date: { kind: "tomorrow" },
    })),
  );
  await popup.reload();
  await popup.waitForFunction(
    () =>
      document.querySelector("#event-list").getAttribute("aria-busy") ===
      "false",
  );
  assert.equal(
    await popup.$eval("#discovery-filters", (el) => el.hidden),
    true,
  );
  assert.equal(
    await popup.$eval("#toggle-filters", (el) => el.textContent.trim()),
    "Show filters",
  );
  assert.equal(requests.at(-1).searchParams.get("q"), "jazz");
  assert.deepEqual(requests.at(-1).searchParams.getAll("category"), ["music"]);
  assert.equal(requests.at(-1).searchParams.get("to"), "2025-04-01T22:00:00.000Z");
  await popup.click("#clear-all");
  await popup.waitForFunction(
    () =>
      document.querySelector("#event-list").getAttribute("aria-busy") ===
      "false",
  );
  assert.equal(
    await popup.$eval("#discovery-filters", (el) => el.hidden),
    true,
  );
  assert.equal(
    await popup.evaluate(() => document.activeElement.id),
    "toggle-filters",
  );
  assert.equal(requests.at(-1).searchParams.has("q"), false);
  assert.equal(requests.at(-1).searchParams.has("category"), false);
  assert.equal(requests.at(-1).searchParams.has("to"), false);
  await popup.click("#toggle-filters");
  assert.equal(
    await popup.$eval("#title-query", (el) => el.value),
    "",
  );
  assert.equal(
    await popup.$eval("#category-music", (el) => el.checked),
    false,
  );
  assert.equal(
    await popup.$eval("#date-trigger span", (el) => el.textContent),
    "Date · Any",
  );
});

test("the filter toggle fits narrow and standard popups in both themes", async () => {
  responseEvents = [
    {
      id: "concert",
      title: "City Jazz Night",
      summary: "Live music with local artists.",
      category: "music",
      starts_at: "2025-04-01T18:00:00Z",
      ends_at: null,
      location_name: "Community Hall",
      source_name: "Local Events",
      source_url: "https://example.org/concert",
    },
  ];
  const action = await openPopup({ expandFilters: false });
  const url = action.popup.url();
  await action.popup.close();
  const popup = await browser.newPage();
  for (const width of [420, 320]) {
    await popup.setViewport({ width, height: 600 });
    await popup.goto(url);
    await popup.waitForSelector(".event-card");
    for (const theme of ["light", "dark"]) {
      await popup.click(`label[for="theme-${theme}"]`);
      for (const state of ["collapsed", "expanded"]) {
        if (state === "expanded") await popup.click("#toggle-filters");
        const layout = await popup.evaluate(() => {
          const shell = document.querySelector(".popup");
          const heading = document.querySelector(".section-heading")
            .getBoundingClientRect();
          const toggle = document.querySelector("#toggle-filters")
            .getBoundingClientRect();
          const title = document.querySelector(".section-heading h2")
            .getBoundingClientRect();
          return {
            overflow: shell.scrollWidth > shell.clientWidth,
            overlap: title.right > toggle.left,
            bounded: toggle.right <= heading.right,
          };
        });
        assert.deepEqual(layout, {
          overflow: false,
          overlap: false,
          bounded: true,
        });
        await popup.screenshot({
          path: `/tmp/beethere-filters-${width}-${theme}-${state}.png`,
        });
      }
      await popup.click("#toggle-filters");
    }
  }
});

test("the toolbar action opens the BeeThere visual shell", async () => {
  const { popup, triggerPage } = await openPopup();
  const shell = await popup.$eval(".popup", (element) => ({
    brand: element.querySelector(".brand").textContent.trim(),
    width: getComputedStyle(element).width,
    hasFromTodayLabel: element.querySelector(".from-today") !== null,
  }));
  assert.deepEqual(shell, {
    brand: "BeeThere",
    width: "420px",
    hasFromTodayLabel: false,
  });
  await popup.close();
  await triggerPage.close();
});

test("the header logo follows the selected color scheme", async () => {
  const { popup, triggerPage } = await openPopup();
  await popup.emulateMediaFeatures([
    { name: "prefers-color-scheme", value: "light" },
  ]);
  assert.deepEqual(
    await popup.$eval(".brand", (brand) => ({
      lightSource: brand.querySelector(".brand-logo-light").getAttribute("src"),
      darkSource: brand.querySelector(".brand-logo-dark").getAttribute("src"),
      lightDisplay: getComputedStyle(brand.querySelector(".brand-logo-light"))
        .display,
      darkDisplay: getComputedStyle(brand.querySelector(".brand-logo-dark"))
        .display,
    })),
    {
      lightSource: "assets/logo/beethere-logo-light.svg",
      darkSource: "assets/logo/beethere-logo-dark.svg",
      lightDisplay: "block",
      darkDisplay: "none",
    },
  );

  await popup.emulateMediaFeatures([
    { name: "prefers-color-scheme", value: "dark" },
  ]);
  assert.deepEqual(
    await popup.$eval(".brand", (brand) => ({
      lightDisplay: getComputedStyle(brand.querySelector(".brand-logo-light"))
        .display,
      darkDisplay: getComputedStyle(brand.querySelector(".brand-logo-dark"))
        .display,
    })),
    { lightDisplay: "none", darkDisplay: "block" },
  );
  await popup.close();
  await triggerPage.close();
});

test("the header and discovery controls stay visible while results scroll", async () => {
  const { popup, triggerPage } = await openPopup();
  const layout = await popup.evaluate(async () => {
    const shell = document.querySelector(".popup");
    const header = document.querySelector(".header");
    const results = document.querySelector("#results");
    const query = document.querySelector("#title-query");
    await new Promise((resolve) => {
      const check = () =>
        document.querySelector("#event-list").getAttribute("aria-busy") ===
        "false"
          ? resolve()
          : setTimeout(check, 10);
      check();
    });
    document.querySelector("#event-list").style.height = "1200px";
    const initialHeaderTop = header.getBoundingClientRect().top;
    const initialQueryTop = query.getBoundingClientRect().top;
    results.scrollTop = 300;
    await new Promise((resolve) => requestAnimationFrame(resolve));
    return {
      headerPosition: getComputedStyle(header).position,
      headerTop: getComputedStyle(header).top,
      popupHeight: getComputedStyle(shell).height,
      popupOverflow: getComputedStyle(shell).overflowY,
      scrollTop: results.scrollTop,
      shellScrollTop: shell.scrollTop,
      headerMoved: header.getBoundingClientRect().top !== initialHeaderTop,
      queryMoved: query.getBoundingClientRect().top !== initialQueryTop,
    };
  });
  assert.deepEqual(layout, {
    headerPosition: "sticky",
    headerTop: "0px",
    popupHeight: "600px",
    popupOverflow: "hidden",
    scrollTop: 300,
    shellScrollTop: 0,
    headerMoved: false,
    queryMoved: false,
  });
  await popup.close();
  await triggerPage.close();
});

test("the popup follows the browser color scheme by default", async () => {
  const { popup, triggerPage } = await openPopup();
  await popup.emulateMediaFeatures([
    { name: "prefers-color-scheme", value: "dark" },
  ]);
  assert.deepEqual(
    await popup.evaluate(() => ({
      themeOverride: document.documentElement.dataset.theme ?? null,
      canvas: getComputedStyle(document.body).backgroundColor,
      paper: getComputedStyle(document.querySelector(".popup")).backgroundColor,
    })),
    {
      themeOverride: null,
      canvas: "rgb(16, 21, 17)",
      paper: "rgb(22, 27, 24)",
    },
  );
  await popup.close();
  await triggerPage.close();
});

test("the theme switch shows named icons at the design size", async () => {
  const { popup, triggerPage } = await openPopup();
  const options = await popup.$$eval(".theme-switch label", (labels) =>
    labels.map((label) => {
      const target = label.querySelector("input + span");
      const icon = label.querySelector("svg");
      const name = label.querySelector(".visually-hidden");
      return {
        value: label.querySelector("input").value,
        name: name?.textContent,
        tooltip: label.title,
        hiddenName: name ? getComputedStyle(name).clipPath : null,
        targetSize: [target.clientWidth, target.clientHeight],
        iconSize: icon ? [icon.clientWidth, icon.clientHeight] : null,
        decorative: icon?.getAttribute("aria-hidden"),
      };
    }),
  );
  assert.deepEqual(options, ["System", "Light", "Dark"].map((name) => ({
    value: name.toLowerCase(),
    name,
    tooltip: name,
    hiddenName: "inset(50%)",
    targetSize: [32, 28],
    iconSize: [18, 18],
    decorative: "true",
  })));
  for (const name of ["System", "Light", "Dark"]) {
    assert.ok(await popup.$(`::-p-aria(${name}[role="radio"])`));
  }
  await popup.close();
  await triggerPage.close();
});

test("theme icons show hover and keyboard focus in both appearances", async () => {
  const { popup, triggerPage } = await openPopup();
  for (const [scheme, hoverColor, focusColor] of [
    ["light", "rgb(230, 235, 223)", "rgb(82, 107, 63)"],
    ["dark", "rgb(59, 80, 53)", "rgb(211, 234, 169)"],
  ]) {
    await popup.emulateMediaFeatures([
      { name: "prefers-color-scheme", value: scheme },
    ]);
    await popup.hover("label[for='theme-light']");
    assert.equal(await popup.$eval("#theme-light + span", (target) =>
      getComputedStyle(target).backgroundColor), hoverColor);
    assert.equal(await popup.$eval("#theme-system", (input) => input.checked), true);
    await popup.mouse.move(0, 0);
    await popup.focus(".brand");
    await popup.keyboard.press("Tab");
    assert.deepEqual(await popup.$eval("#theme-system", (input) => ({
      checked: input.checked,
      focused: input.matches(":focus-visible"),
      outline: getComputedStyle(input.nextElementSibling).outlineColor,
      outlineWidth: getComputedStyle(input.nextElementSibling).outlineWidth,
    })), { checked: true, focused: true, outline: focusColor, outlineWidth: "2px" });
    await popup.keyboard.press("ArrowRight");
    assert.equal(await popup.$eval("#theme-light", (input) => input.checked), true);
    await popup.keyboard.press("ArrowLeft");
    assert.equal(await popup.$eval("#theme-system", (input) => input.checked), true);
    assert.equal(await popup.evaluate(() => localStorage.getItem("bee-there-theme")), null);
  }
  await popup.close();
  await triggerPage.close();
});

test("the theme switch persists an override and can return to system", async () => {
  const { popup, triggerPage } = await openPopup();
  await popup.emulateMediaFeatures([
    { name: "prefers-color-scheme", value: "dark" },
  ]);
  assert.equal(
    await popup.$eval("#theme-system", (input) => input.checked),
    true,
  );

  await popup.emulateMediaFeatures([
    { name: "prefers-color-scheme", value: "light" },
  ]);
  await popup.click("label[for='theme-dark']");
  assert.deepEqual(
    await popup.evaluate(() => ({
      selected: document.documentElement.dataset.theme,
      stored: localStorage.getItem("bee-there-theme"),
      paper: getComputedStyle(document.querySelector(".popup")).backgroundColor,
    })),
    { selected: "dark", stored: "dark", paper: "rgb(22, 27, 24)" },
  );

  await popup.emulateMediaFeatures([
    { name: "prefers-color-scheme", value: "dark" },
  ]);
  await popup.click("label[for='theme-light']");
  assert.deepEqual(
    await popup.evaluate(() => ({
      selected: document.documentElement.dataset.theme,
      stored: localStorage.getItem("bee-there-theme"),
      paper: getComputedStyle(document.querySelector(".popup")).backgroundColor,
    })),
    { selected: "light", stored: "light", paper: "rgb(252, 251, 247)" },
  );
  await popup.close();
  await triggerPage.close();

  const reopened = await openPopup();
  assert.equal(
    await reopened.popup.$eval("#theme-light", (input) => input.checked),
    true,
  );
  await reopened.popup.emulateMediaFeatures([
    { name: "prefers-color-scheme", value: "dark" },
  ]);
  await reopened.popup.click("label[for='theme-system']");
  assert.deepEqual(
    await reopened.popup.evaluate(() => ({
      selected: document.documentElement.dataset.theme ?? null,
      stored: localStorage.getItem("bee-there-theme"),
      paper: getComputedStyle(document.querySelector(".popup")).backgroundColor,
    })),
    { selected: null, stored: null, paper: "rgb(22, 27, 24)" },
  );
  await reopened.popup.close();
  await reopened.triggerPage.close();
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
      title: "No upcoming events",
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

test("the popup test clock stays fixed while real time passes", async () => {
  const { popup, triggerPage } = await openPopup();
  const fixedTime = Date.parse("2025-03-30T22:30:00Z");
  assert.equal(await popup.evaluate(() => Date.now()), fixedTime);
  await new Promise((resolve) => setTimeout(resolve, 100));
  assert.equal(await popup.evaluate(() => Date.now()), fixedTime);
  assert.equal(await popup.evaluate(() => new Date().getTime()), fixedTime);
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
  assert.deepEqual(
    [...request.searchParams],
    [
      ["from", "2025-03-30T22:00:00.000Z"],
      ["limit", "20"],
      ["offset", "0"],
    ],
  );
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
      source_name: "Community Events",
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
      sourceName: "Community Events ↗",
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
      sourceLabel: "Open Community Events source website (opens a new tab)",
    },
  );
  assert.equal(await popup.$(".event-title img"), null);
  await popup.close();
  await triggerPage.close();
});

test("title search sends a server query and preserves focus", async () => {
  const { popup } = await openPopup();
  await popup.waitForSelector("#title-query", { timeout: 1000 });
  await popup.type("#title-query", "Jazz");
  await popup.waitForFunction(
    () => document.querySelector("#status").textContent !== "Loading events…",
  );
  await new Promise((resolve) => setTimeout(resolve, 250));
  assert.equal(requests.at(-1).searchParams.get("q"), "Jazz");
  assert.equal(
    await popup.evaluate(() => document.activeElement.id),
    "title-query",
  );
  await popup.click("#clear-query");
  await new Promise((resolve) => setTimeout(resolve, 150));
  assert.equal(requests.at(-1).searchParams.has("q"), false);
});

test("category checkboxes combine with search, stay open, and reset separately", async () => {
  const { popup } = await openPopup();
  await popup.type("#title-query", "jazz");
  await popup.waitForSelector("#category-trigger", { timeout: 1000 });
  await popup.click("#category-trigger");
  assert.equal(
    await popup.$$eval("#category-menu input", (items) => items.length),
    11,
  );
  await popup.click("#category-music");
  await popup.click("#category-theatre");
  await new Promise((resolve) => setTimeout(resolve, 150));
  assert.deepEqual(requests.at(-1).searchParams.getAll("category").sort(), [
    "music",
    "theatre",
  ]);
  assert.equal(requests.at(-1).searchParams.get("q"), "jazz");
  assert.equal(await popup.$eval("#category-menu", (el) => el.hidden), false);
  await popup.keyboard.press("Escape");
  assert.equal(
    await popup.evaluate(() => document.activeElement.id),
    "category-trigger",
  );
  await popup.click('[aria-label="Remove Music category"]');
  await new Promise((resolve) => setTimeout(resolve, 100));
  assert.deepEqual(requests.at(-1).searchParams.getAll("category"), [
    "theatre",
  ]);
});

test("date presets and custom inclusive dates retain the last valid choice", async () => {
  const { popup } = await openPopup();
  await popup.waitForSelector("#date-trigger", { timeout: 1000 });
  await popup.click("#date-trigger");
  assert.equal(
    await popup.$eval('[data-date="today"] small', (el) => el.textContent),
    "Mon, 31 Mar",
  );
  assert.equal(
    await popup.$eval('[data-date="tomorrow"] small', (el) => el.textContent),
    "Tue, 1 Apr",
  );
  await popup.click('[data-date="tomorrow"]');
  assert.equal(
    await popup.$eval(
      "#date-trigger",
      (el) => getComputedStyle(el).backgroundColor,
    ),
    await popup.$eval(
      ".theme-switch",
      (el) => getComputedStyle(el).backgroundColor,
    ),
  );
  await new Promise((resolve) => setTimeout(resolve, 100));
  assert.equal(
    requests.at(-1).searchParams.get("from"),
    "2025-03-31T22:00:00.000Z",
  );
  assert.equal(
    requests.at(-1).searchParams.get("to"),
    "2025-04-01T22:00:00.000Z",
  );
  await popup.click("#date-trigger");
  assert.equal(
    await popup.$eval('[data-date="tomorrow"]', (el) =>
      el.getAttribute("aria-pressed"),
    ),
    "true",
  );
  await popup.click('[data-date="custom"]');
  await popup.type("#custom-start", "02 Apr 2025");
  assert.match(
    await popup.$eval("#calendar-month", (el) => el.textContent),
    /April 2025/,
  );
  await new Promise((resolve) => setTimeout(resolve, 100));
  assert.equal(
    requests.at(-1).searchParams.get("from"),
    "2025-04-01T22:00:00.000Z",
  );
  await popup.click("#mode-range");
  await popup.type("#custom-end", "05 Apr 2025");
  await new Promise((resolve) => setTimeout(resolve, 100));
  assert.equal(
    requests.at(-1).searchParams.get("to"),
    "2025-04-05T22:00:00.000Z",
  );
  const validRequestCount = requests.length;
  await popup.$eval("#custom-end", (input) => {
    input.value = "01 Apr 2025";
    input.dispatchEvent(new Event("input", { bubbles: true }));
  });
  assert.match(
    await popup.$eval("#date-feedback", (el) => el.textContent),
    /End must not precede start/,
  );
  assert.equal(requests.length, validRequestCount);
  await popup.keyboard.press("Escape");
  assert.equal(
    await popup.evaluate(() => document.activeElement.id),
    "date-trigger",
  );
  await popup.click("#date-trigger");
  await popup.click('[data-date="custom"]');
  assert.equal(
    await popup.$eval("#custom-end", (el) => el.value),
    "05 Apr 2025",
  );
});

test("custom calendar blocks past days and supports arrows and month keys", async () => {
  const { popup } = await openPopup();
  await popup.click("#date-trigger");
  await popup.click('[data-date="custom"]');
  await popup.waitForSelector('[data-day="2025-03-31"]', { timeout: 1000 });
  assert.equal(
    await popup.$eval('[data-day="2025-03-30"]', (el) => el.disabled),
    true,
  );
  await popup.focus('[data-day="2025-03-31"]');
  await popup.keyboard.press("ArrowLeft");
  assert.equal(
    await popup.evaluate(() => document.activeElement.dataset.day),
    "2025-03-31",
  );
  await popup.keyboard.press("ArrowRight");
  assert.equal(
    await popup.evaluate(() => document.activeElement.dataset.day),
    "2025-04-01",
  );
  await popup.keyboard.press("Enter");
  assert.equal(
    await popup.$eval("#custom-start", (el) => el.value),
    "01 Apr 2025",
  );
  await popup.keyboard.press("PageDown");
  assert.match(
    await popup.$eval("#calendar-month", (el) => el.textContent),
    /May 2025/,
  );
  await popup.keyboard.press("Enter");
  await new Promise((resolve) => setTimeout(resolve, 100));
  assert.equal(
    requests.at(-1).searchParams.get("from"),
    "2025-04-30T22:00:00.000Z",
  );
});

test("discovery choices persist and Clear all leaves theme unchanged", async () => {
  const { popup, triggerPage } = await openPopup();
  await popup.type("#title-query", "jazz");
  await popup.click("#category-trigger");
  await popup.click("#category-music");
  await popup.keyboard.press("Escape");
  await popup.click("#date-trigger");
  await popup.click('[data-date="tomorrow"]');
  await popup.click('label[for="theme-dark"]');
  await popup.close();
  await triggerPage.close();
  const reopened = await openPopup();
  assert.equal(
    await reopened.popup.$eval("#title-query", (el) => el.value),
    "jazz",
  );
  assert.equal(
    await reopened.popup.$eval("#category-music", (el) => el.checked),
    true,
  );
  assert.equal(
    await reopened.popup.$eval("#date-trigger span", (el) => el.textContent),
    "Tomorrow",
  );
  await reopened.popup.click("#clear-all");
  await new Promise((resolve) => setTimeout(resolve, 100));
  assert.equal(requests.at(-1).searchParams.has("q"), false);
  assert.equal(requests.at(-1).searchParams.has("category"), false);
  assert.equal(requests.at(-1).searchParams.has("to"), false);
  assert.equal(
    await reopened.popup.evaluate(() =>
      localStorage.getItem("bee-there-theme"),
    ),
    "dark",
  );
});

test("saved custom dates clamp or expire without clearing other filters", async () => {
  const { popup } = await openPopup();
  for (const [end, expectedFrom, expectedTo, notice] of [
    [
      "2025-04-03",
      "2025-03-30T22:00:00.000Z",
      "2025-04-03T22:00:00.000Z",
      /range now starts today/,
    ],
    ["2025-03-29", "2025-03-30T22:00:00.000Z", null, /saved dates have passed/],
  ]) {
    await popup.evaluate(
      (end) =>
        localStorage.setItem(
          "bee-there-discovery",
          JSON.stringify({
            query: "Jazz",
            categories: ["music"],
            date: { kind: "custom", start: "2025-03-28", end },
          }),
        ),
      end,
    );
    await popup.reload();
    await popup.waitForFunction(
      () =>
        document.querySelector("#event-list").getAttribute("aria-busy") ===
        "false",
    );
    assert.equal(requests.at(-1).searchParams.get("from"), expectedFrom);
    assert.equal(requests.at(-1).searchParams.get("to"), expectedTo);
    assert.equal(requests.at(-1).searchParams.get("q"), "Jazz");
    assert.deepEqual(requests.at(-1).searchParams.getAll("category"), [
      "music",
    ]);
    assert.match(
      await popup.$eval("#discovery-notice", (el) => el.textContent),
      notice,
    );
  }
});

test("superseded results cannot replace the latest search", async () => {
  let oldResponse;
  responseHandler = (request, response) => {
    const query = new URL(request.url, apiBaseUrl).searchParams.get("q");
    if (query === "old") oldResponse = response;
    else respondWithJson(response);
  };
  const { popup } = await openPopup();
  await popup.type("#title-query", "old");
  await new Promise((resolve) => setTimeout(resolve, 100));
  assert.ok(oldResponse);
  await popup.$eval("#title-query", (input) => {
    input.value = "new";
    input.dispatchEvent(new Event("input", { bubbles: true }));
  });
  await popup.waitForFunction(
    () =>
      document.querySelector("#event-list").getAttribute("aria-busy") ===
      "false",
  );
  respondWithJson(oldResponse, [
    {
      id: "old",
      title: "Stale",
      summary: "Old result",
      category: "music",
      starts_at: "2025-04-01T18:00:00Z",
      ends_at: null,
      location_name: null,
      source_name: "Source",
      source_url: "https://example.org",
    },
  ]);
  await new Promise((resolve) => setTimeout(resolve, 150));
  assert.equal(await popup.$(".event-card"), null);
  assert.equal(await popup.$eval("#title-query", (el) => el.value), "new");
});

test("infinite scroll loads every page and retries without losing earlier matches", async () => {
  const event = (index) => ({
    id: String(index),
    title: `Event ${index}`,
    summary: "Match",
    category: "music",
    starts_at: "2025-04-01T18:00:00Z",
    ends_at: null,
    location_name: null,
    source_name: "Source",
    source_url: "https://example.org",
  });
  let failNext = true;
  responseHandler = (request, response) => {
    const offset = Number(
      new URL(request.url, apiBaseUrl).searchParams.get("offset") || 0,
    );
    if (offset === 20 && failNext) {
      failNext = false;
      respondWithJson(response, [], 503);
      return;
    }
    respondWithJson(
      response,
      Array.from(
        { length: offset === 0 ? 20 : offset === 20 ? 20 : 3 },
        (_, index) => event(offset + index),
      ),
    );
  };
  const { popup } = await openPopup();
  await popup.waitForSelector(".event-card:nth-child(20)");
  await popup.waitForSelector("#results", { timeout: 1000 });
  const scroll = () =>
    popup.$eval("#results", (el) => {
      el.scrollTop = el.scrollHeight;
    });
  await scroll();
  await popup.waitForSelector("#retry-more", { timeout: 2000 });
  assert.equal(await popup.$$eval(".event-card", (cards) => cards.length), 20);
  await popup.click("#retry-more");
  await popup.waitForFunction(
    () => document.querySelectorAll(".event-card").length === 40,
  );
  await scroll();
  await popup.waitForFunction(
    () => document.querySelectorAll(".event-card").length === 43,
  );
  assert.deepEqual(
    requests.map((url) => url.searchParams.get("offset")),
    ["0", "20", "20", "40"],
  );
  assert.equal(requests[0].searchParams.get("limit"), "20");
  const positions = await popup.evaluate(() => ({
    shellScroll: document.querySelector(".popup").scrollTop,
    controlsTop: document.querySelector("#title-query").getBoundingClientRect()
      .top,
    resultsScroll: document.querySelector("#results").scrollTop,
  }));
  assert.equal(positions.shellScroll, 0);
  assert.ok(positions.controlsTop > 68 && positions.controlsTop < 220);
  assert.ok(positions.resultsScroll > 0);
});

test("updating keeps old cards inert, then shows filtered empty feedback", async () => {
  let pending;
  responseEvents = [
    {
      id: "one",
      title: "Existing",
      summary: "Earlier",
      category: "music",
      starts_at: "2025-04-01T18:00:00Z",
      ends_at: null,
      location_name: null,
      source_name: "Source",
      source_url: "https://example.org",
    },
  ];
  const { popup } = await openPopup();
  await popup.waitForSelector(".event-card");
  responseHandler = (_request, response) => {
    pending = response;
  };
  await popup.type("#title-query", "x");
  assert.equal(await popup.$$eval(".event-card", (cards) => cards.length), 1);
  assert.equal(await popup.$eval("#event-list", (el) => el.inert), true);
  assert.equal(
    await popup.$eval("#status", (el) => el.textContent),
    "Updating results…",
  );
  respondWithJson(pending, []);
  await popup.waitForFunction(
    () =>
      document.querySelector("#event-list").getAttribute("aria-busy") ===
      "false",
  );
  assert.equal(
    await popup.$eval(".state h3", (el) => el.textContent),
    "No matching events",
  );
  assert.equal(await popup.$eval("#event-list", (el) => el.inert), false);
  assert.equal(
    await popup.evaluate(() => document.activeElement.id),
    "title-query",
  );
});

test("narrow dark controls and bounded menus keep all provided icons local and sized", async () => {
  const action = await openPopup();
  const popupUrl = action.popup.url();
  await action.popup.close();
  const popup = await browser.newPage();
  await popup.setViewport({ width: 320, height: 600 });
  await popup.goto(popupUrl);
  await popup.click("#toggle-filters");
  await popup.click('label[for="theme-dark"]');
  await popup.click("#category-trigger");
  assert.equal(
    await popup.$eval(".search-field > img", (image) =>
      image.getAttribute("src"),
    ),
    "assets/discovery/search-dark.svg",
  );
  const layout = await popup.evaluate(() => {
    const shell = document.querySelector(".popup").getBoundingClientRect();
    const menu = document.querySelector("#category-menu");
    return {
      width: shell.width,
      overflow: document.querySelector(".popup").scrollWidth > shell.width,
      bounded:
        menu.getBoundingClientRect().bottom <=
        Math.min(600, window.innerHeight),
      scrollable: menu.scrollHeight > menu.clientHeight,
    };
  });
  assert.deepEqual(layout, {
    width: 320,
    overflow: false,
    bounded: true,
    scrollable: false,
  });
  await popup.setViewport({ width: 320, height: 500 });
  assert.equal(
    await popup.$eval(
      "#category-menu",
      (menu) =>
        menu.scrollHeight > menu.clientHeight &&
        menu.getBoundingClientRect().bottom <= window.innerHeight,
    ),
    true,
  );
  await popup.setViewport({ width: 320, height: 600 });
  await popup.screenshot({ path: "/tmp/beethere-discovery-narrow-dark.png" });
  await popup.keyboard.press("Escape");
  await popup.click("#date-trigger");
  await popup.click('[data-date="custom"]');
  const icons = await popup.$$eval(
    "#custom-menu img, .search-field > img, .filter-row img",
    (images) =>
      images
        .filter((image) => image.getClientRects().length)
        .map((image) => ({
          src: image.getAttribute("src"),
          loaded: image.complete && image.naturalWidth > 0,
          width: image.getBoundingClientRect().width,
          height: image.getBoundingClientRect().height,
        })),
  );
  assert.ok(
    icons.every(
      (icon) =>
        icon.src.startsWith("assets/discovery/") &&
        icon.loaded &&
        icon.width === 16 &&
        icon.height === 16,
    ),
  );
  await popup.screenshot({ path: "/tmp/beethere-discovery-custom-dark.png" });
});

test("failed filtered requests keep choices and ignore a superseded retry", async () => {
  responseHandler = (_request, response) => respondWithJson(response, [], 503);
  const { popup } = await openPopup();
  await popup.type("#title-query", "Jazz");
  await popup.waitForSelector("#retry");
  assert.equal(
    await popup.$eval(".state h3", (el) => el.textContent),
    "Could not load events",
  );
  await popup.evaluate(() => {
    globalThis.oldRetry = document.querySelector("#retry");
  });
  responseHandler = (_request, response) => respondWithJson(response, []);
  await popup.click("#clear-query");
  await popup.waitForFunction(
    () =>
      document.querySelector("#event-list").getAttribute("aria-busy") ===
      "false",
  );
  const count = requests.length;
  await popup.evaluate(() => globalThis.oldRetry.click());
  await new Promise((resolve) => setTimeout(resolve, 100));
  assert.equal(requests.length, count);
});

test("light discovery renders local design assets in their intended slots", async () => {
  responseEvents = [
    {
      id: "music",
      title: "City Jazz Weekend",
      summary: "Live jazz with local and guest musicians.",
      category: "music",
      starts_at: "2025-04-05T18:00:00Z",
      ends_at: null,
      location_name: "Cultural Station",
      source_name: "Community Events",
      source_url: "https://example.org/jazz",
    },
    {
      id: "theatre",
      title: "Jazz cabaret",
      summary: "A musical show with a jazz repertoire.",
      category: "theatre",
      starts_at: "2025-04-06T17:00:00Z",
      ends_at: null,
      location_name: "Youth Theatre",
      source_name: "Community Events",
      source_url: "https://example.org/cabaret",
    },
  ];
  const action = await openPopup();
  const url = action.popup.url();
  await action.popup.close();
  const popup = await browser.newPage();
  await popup.setViewport({ width: 420, height: 600 });
  await popup.goto(url);
  await popup.click("#toggle-filters");
  await popup.click('label[for="theme-light"]');
  await popup.waitForSelector(".event-card:nth-child(2)");
  await popup.screenshot({ path: "/tmp/beethere-discovery-default-light.png" });
  await popup.type("#title-query", "jazz");
  await popup.click("#category-trigger");
  await popup.click("#category-music");
  await popup.click("#category-theatre");
  await popup.screenshot({
    path: "/tmp/beethere-discovery-categories-light.png",
  });
  await popup.keyboard.press("Escape");
  await popup.click("#date-trigger");
  await popup.screenshot({
    path: "/tmp/beethere-discovery-date-menu-light.png",
  });
  await popup.click('[data-date="weekend"]');
  await popup.waitForFunction(
    () =>
      document.querySelector("#event-list").getAttribute("aria-busy") ===
      "false",
  );
  await popup.screenshot({
    path: "/tmp/beethere-discovery-combined-light.png",
  });
  const images = await popup.$$eval(".discovery-controls img", (items) =>
    items
      .filter((image) => image.getClientRects().length)
      .map((image) => ({
        src: image.getAttribute("src"),
        loaded: image.complete && image.naturalWidth > 0,
        width: image.getBoundingClientRect().width,
        height: image.getBoundingClientRect().height,
      })),
  );
  assert.ok(
    images.every(
      (image) => image.src.startsWith("assets/discovery/") && image.loaded,
    ),
  );
  assert.ok(
    images
      .filter((image) => image.src.endsWith("chip-close.svg"))
      .every((image) => image.width === 14 && image.height === 14),
  );
  assert.ok(
    images
      .filter((image) => !image.src.endsWith("chip-close.svg"))
      .every((image) => image.width === 16 && image.height === 16),
  );
  await popup.click("#date-trigger");
  await popup.click('[data-date="custom"]');
  await popup.type("#custom-start", "05 Apr 2025");
  await popup.click("#mode-range");
  await popup.type("#custom-end", "10 Apr 2025");
  await popup.screenshot({ path: "/tmp/beethere-discovery-custom-light.png" });
});

test("a calendar range draft highlights its start without changing the applied filter", async () => {
  const { popup } = await openPopup();
  await popup.click("#date-trigger");
  await popup.click('[data-date="tomorrow"]');
  await popup.click("#date-trigger");
  await popup.click('[data-date="custom"]');
  await popup.click("#mode-range");
  await popup.click("#next-month");
  const count = requests.length;
  await popup.click('[data-day="2025-04-05"]');
  assert.equal(
    await popup.$eval('[data-day="2025-04-05"]', (button) =>
      button.parentElement.getAttribute("aria-selected"),
    ),
    "true",
  );
  assert.equal(requests.length, count);
  assert.equal(
    await popup.$eval("#date-trigger span", (el) => el.textContent),
    "Tomorrow",
  );
  await popup.keyboard.press("Escape");
  await popup.click("#date-trigger");
  await popup.click('[data-date="custom"]');
  assert.equal(await popup.$eval("#custom-start", (el) => el.value), "");
});
