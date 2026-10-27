import assert from "node:assert/strict";
import { after, before, test } from "node:test";
import { spawnSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";
import puppeteer from "puppeteer";

const extensionDirectory = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "..",
);
const distributionDirectory = path.join(extensionDirectory, "dist");
let browser;

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
  const page = await browser.newPage();
  await extension.triggerAction(page);

  const popupTarget = await popupTargetPromise;
  const popup = await popupTarget.asPage();
  assert.ok(popup, "The action did not open a popup page");
  return { popup, triggerPage: page };
}

before(async () => {
  const result = spawnSync("npm", ["run", "build"], {
    cwd: extensionDirectory,
    encoding: "utf8",
  });
  assert.equal(result.status, 0, result.stderr || result.stdout);

  browser = await puppeteer.launch({
    enableExtensions: [distributionDirectory],
    headless: true,
  });
});

after(async () => {
  await browser?.close();
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
