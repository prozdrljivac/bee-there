import { API_BASE_URL } from "./config.js";
import { dateBounds, today, parseDay, formatDay } from "./discovery-dates.js";
import { createDatePicker } from "./date-picker.js";

const EVENT_TIME_ZONE = "Europe/Belgrade";
const EVENT_CATEGORIES = new Set([
  "theatre",
  "music",
  "comedy",
  "film",
  "exhibition",
  "festival",
  "sports",
  "community",
  "literature",
  "fair",
  "other",
]);
const eventDateFormatter = new Intl.DateTimeFormat("en-GB", {
  timeZone: EVENT_TIME_ZONE,
  year: "numeric",
  month: "long",
  day: "numeric",
});
const eventTimeFormatter = new Intl.DateTimeFormat("en-GB", {
  timeZone: EVENT_TIME_ZONE,
  hour: "2-digit",
  minute: "2-digit",
  hourCycle: "h23",
});
const eventMonthFormatter = new Intl.DateTimeFormat("en-GB", {
  timeZone: EVENT_TIME_ZONE,
  month: "short",
});
const eventDayFormatter = new Intl.DateTimeFormat("en-GB", {
  timeZone: EVENT_TIME_ZONE,
  day: "2-digit",
});

function textElement(tagName, className, text) {
  const element = document.createElement(tagName);
  element.className = className;
  element.textContent = text;
  return element;
}

function isAwareDateTime(value) {
  return (
    typeof value === "string" &&
    /(?:Z|[+-]\d{2}:\d{2})$/i.test(value) &&
    Number.isFinite(Date.parse(value))
  );
}

function isHttpUrl(value) {
  if (typeof value !== "string") {
    return false;
  }
  try {
    const url = new URL(value);
    return url.protocol === "http:" || url.protocol === "https:";
  } catch {
    return false;
  }
}

function isValidEvent(event) {
  return (
    event !== null &&
    typeof event === "object" &&
    typeof event.id === "string" &&
    typeof event.title === "string" &&
    typeof event.summary === "string" &&
    EVENT_CATEGORIES.has(event.category) &&
    isAwareDateTime(event.starts_at) &&
    (event.ends_at === null || isAwareDateTime(event.ends_at)) &&
    (event.location_name === null || typeof event.location_name === "string") &&
    typeof event.source_name === "string" &&
    isHttpUrl(event.source_url)
  );
}

function locationIcon() {
  const icon = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  icon.setAttribute("class", "location-icon");
  icon.setAttribute("viewBox", "0 0 24 24");
  icon.setAttribute("fill", "none");
  icon.setAttribute("stroke", "currentColor");
  icon.setAttribute("stroke-width", "1.7");
  icon.setAttribute("stroke-linecap", "round");
  icon.setAttribute("stroke-linejoin", "round");
  icon.setAttribute("aria-hidden", "true");
  const outline = document.createElementNS(
    "http://www.w3.org/2000/svg",
    "path",
  );
  outline.setAttribute("d", "M20 10c0 6-8 12-8 12S4 16 4 10a8 8 0 1 1 16 0Z");
  const center = document.createElementNS(
    "http://www.w3.org/2000/svg",
    "circle",
  );
  center.setAttribute("cx", "12");
  center.setAttribute("cy", "10");
  center.setAttribute("r", "2.5");
  icon.append(outline, center);
  return icon;
}

function renderEvent(event) {
  const start = new Date(event.starts_at);
  const card = document.createElement("article");
  card.className = "event event-card";

  const dateTile = document.createElement("div");
  dateTile.className = "date-tile";
  dateTile.setAttribute("aria-hidden", "true");
  dateTile.append(
    textElement("span", "", eventMonthFormatter.format(start)),
    textElement("strong", "", eventDayFormatter.format(start)),
  );

  const content = document.createElement("div");
  content.className = "event-content";
  const top = document.createElement("div");
  top.className = "event-top";
  top.append(
    textElement(
      "span",
      `category event-category ${event.category}`,
      event.category.toUpperCase(),
    ),
  );

  const time = document.createElement("time");
  time.className = "time";
  time.dateTime = event.starts_at;
  time.title = "Local time in Serbia";
  const end = event.ends_at ? new Date(event.ends_at) : null;
  const timeText = end
    ? `${eventTimeFormatter.format(start)}–${eventTimeFormatter.format(end)}`
    : eventTimeFormatter.format(start);
  time.append(
    textElement("span", "event-date", eventDateFormatter.format(start)),
    " · ",
    textElement("span", "event-time", timeText),
  );

  const venue = event.location_name?.trim();
  const location = document.createElement("div");
  location.className = venue
    ? "location event-location"
    : "location missing event-location";
  location.append(
    locationIcon(),
    textElement("span", "", venue || "Location to be announced"),
  );

  const sourceRow = document.createElement("div");
  sourceRow.className = "source";
  const source = textElement("a", "event-source", `${event.source_name} ↗`);
  source.href = event.source_url;
  source.target = "_blank";
  source.rel = "noopener noreferrer";
  source.setAttribute(
    "aria-label",
    `Open ${event.source_name} source website (opens a new tab)`,
  );
  sourceRow.append(source);

  content.append(
    top,
    textElement("h3", "event-title", event.title),
    textElement("p", "event-summary", event.summary),
    time,
    location,
    sourceRow,
  );
  card.append(dateTile, content);
  return card;
}

function removeRetry() {
  document.querySelector("#retry")?.remove();
}

function showLoading(status, eventList) {
  status.className = "";
  eventList.setAttribute("aria-busy", "true");
  if (eventList.querySelector(".event-card")) {
    status.textContent = "Updating results…";
    eventList.inert = true;
    eventList.classList.add("updating");
    return;
  }
  status.textContent = "Loading events…";
  eventList.replaceChildren();
  for (let index = 0; index < 2; index += 1) {
    const skeleton = document.createElement("div");
    skeleton.className = "skeleton";
    skeleton.setAttribute("aria-hidden", "true");
    skeleton.append(
      document.createElement("div"),
      document.createElement("div"),
      document.createElement("div"),
      document.createElement("div"),
    );
    eventList.append(skeleton);
  }
}

function stateElement(icon, title, message) {
  const state = document.createElement("div");
  state.className = "state";
  state.append(
    textElement("div", "state-icon", icon),
    textElement("h3", "", title),
    textElement("p", "", message),
  );
  return state;
}

function hasFilters() {
  return Boolean(
    queryInput.value ||
    selectedCategories.size ||
    datePicker.choice.kind !== "any",
  );
}

function clearAllChoices() {
  queryInput.value = "";
  clearQuery.hidden = true;
  selectedCategories.clear();
  updateCategories();
  datePicker.setChoice({ kind: "any" }, false);
  (discoveryFilters.hidden ? filtersToggle : queryInput).focus();
  void requestEvents();
}

function showEmpty(status, eventList) {
  const filtered = hasFilters();
  status.className = "";
  status.textContent = filtered ? "0 events" : "No upcoming events.";
  const state = stateElement(
    "",
    filtered ? "No matching events" : "No upcoming events",
    filtered
      ? "Try another title or remove a filter. Your current choices have been kept."
      : "No upcoming events right now. Come back soon for your next good plan.",
  );
  if (filtered) {
    const clear = textElement("button", "", "Clear all filters");
    clear.type = "button";
    clear.addEventListener("click", clearAllChoices);
    state.append(clear);
  }
  eventList.replaceChildren(state);
}

function showError(status, eventList) {
  const filtered = hasFilters();
  const version = requestVersion;
  status.className = "";
  status.textContent = filtered
    ? "Could not update events"
    : "Could not load events.";
  const state = stateElement(
    "",
    filtered ? "Could not load events" : "A small bump in the road.",
    filtered
      ? "Your search and filters are still here. Check your connection and try again."
      : "We could not load the events. Please try again.",
  );
  const retry = textElement("button", "", "Try again");
  retry.id = "retry";
  retry.type = "button";
  retry.addEventListener("click", () => {
    if (version === requestVersion) void requestEvents();
  });
  state.append(retry);
  eventList.replaceChildren(state);
}

function persistChoices() {
  try {
    localStorage.setItem(
      "bee-there-discovery",
      JSON.stringify({
        query: queryInput.value,
        categories: [...selectedCategories],
        date: datePicker.choice,
      }),
    );
  } catch {
    /* Storage can be unavailable in restricted browser profiles. */
  }
  document.querySelector("#clear-all").hidden =
    !queryInput.value &&
    !selectedCategories.size &&
    datePicker.choice.kind === "any";
}

const PAGE_SIZE = 20;
let requestVersion = 0;
let activeRequest;
let nextOffset = 0;
let hasMore = false;
let loadingPage = false;
let pageFailed = false;
const results = document.querySelector("#results");
const sentinel = document.querySelector("#results-sentinel");
const pageStatus = document.querySelector("#page-status");
const pageObserver = new IntersectionObserver(
  (entries) => {
    if (
      entries.some((entry) => entry.isIntersecting) &&
      hasMore &&
      !loadingPage &&
      !pageFailed
    )
      void requestEvents(true);
  },
  { root: results, rootMargin: "80px" },
);

function eventRequestUrl(offset) {
  const url = new URL("/api/events", API_BASE_URL);
  for (const [key, value] of Object.entries(dateBounds(datePicker.choice)))
    url.searchParams.set(key, value);
  if (queryInput.value) url.searchParams.set("q", queryInput.value);
  for (const category of selectedCategories)
    url.searchParams.append("category", category);
  url.searchParams.set("limit", String(PAGE_SIZE));
  url.searchParams.set("offset", String(offset));
  return url;
}

function showPageError(version) {
  pageStatus.textContent = "Could not load more events.";
  const retry = textElement("button", "", "Try again");
  retry.id = "retry-more";
  retry.type = "button";
  retry.addEventListener("click", () => {
    if (version === requestVersion && !loadingPage) void requestEvents(true);
  });
  pageStatus.append(retry);
}

async function fetchEventPage(offset, signal) {
  const response = await fetch(eventRequestUrl(offset), { signal });
  if (!response.ok) {
    throw new Error(`Event request failed with status ${response.status}`);
  }
  const events = await response.json();
  if (!Array.isArray(events) || !events.every(isValidEvent)) {
    throw new TypeError("Event response is invalid");
  }
  return events;
}

function enableEventList(eventList) {
  eventList.setAttribute("aria-busy", "false");
  eventList.inert = false;
  eventList.classList.remove("updating");
}

async function requestEvents(append = false) {
  if (append && (loadingPage || !hasMore)) return;
  if (!append) {
    ++requestVersion;
    activeRequest?.abort();
    nextOffset = 0;
    hasMore = false;
    results.scrollTop = 0;
    persistChoices();
  }
  const version = requestVersion;
  const offset = nextOffset;
  activeRequest = new AbortController();
  loadingPage = true;
  pageFailed = false;
  pageObserver.unobserve(sentinel);
  pageStatus.replaceChildren();
  const status = document.querySelector("#status");
  const eventList = document.querySelector("#event-list");
  removeRetry();
  if (append) pageStatus.textContent = "Loading more events…";
  else showLoading(status, eventList);

  try {
    const events = await fetchEventPage(offset, activeRequest.signal);
    if (version !== requestVersion) return;
    nextOffset = offset + events.length;
    hasMore = events.length === PAGE_SIZE;
    enableEventList(eventList);
    if (append) eventList.append(...events.map(renderEvent));
    else if (!events.length) showEmpty(status, eventList);
    else eventList.replaceChildren(...events.map(renderEvent));
    if (nextOffset) {
      status.className = "";
      status.textContent = `${nextOffset}${hasMore ? "+" : ""} events · Earliest first`;
    }
    pageStatus.textContent = "";
  } catch {
    if (version !== requestVersion) return;
    enableEventList(eventList);
    pageFailed = true;
    if (append) showPageError(version);
    else showError(status, eventList);
  } finally {
    if (version === requestVersion) {
      loadingPage = false;
      if (hasMore && !pageFailed) pageObserver.observe(sentinel);
    }
  }
}

const selectedCategories = new Set();
const categoryMenu = document.querySelector("#category-menu");
const categoryTrigger = document.querySelector("#category-trigger");
const categoryChips = document.querySelector("#category-chips");
const categoryInputs = new Map();
function closeCategories(restoreFocus = false) {
  categoryMenu.hidden = true;
  categoryTrigger.setAttribute("aria-expanded", "false");
  if (restoreFocus) categoryTrigger.focus();
}
function updateDiscoveryIcons() {
  const theme = document.documentElement.dataset.theme;
  const dark =
    theme === "dark" ||
    (!theme && matchMedia("(prefers-color-scheme: dark)").matches);
  for (const image of document.querySelectorAll(
    'img[src^="assets/discovery/"]',
  )) {
    const name = image
      .getAttribute("src")
      .split("/")
      .at(-1)
      .replace("-dark.svg", ".svg");
    if (
      ["search.svg", "close.svg", "chevron.svg", "chip-close.svg"].includes(
        name,
      )
    ) {
      image.src = `assets/discovery/${dark ? name.replace(".svg", "-dark.svg") : name}`;
    }
  }
}
new MutationObserver(updateDiscoveryIcons).observe(document.documentElement, {
  attributes: true,
  attributeFilter: ["data-theme"],
});
matchMedia("(prefers-color-scheme: dark)").addEventListener(
  "change",
  updateDiscoveryIcons,
);

function updateCategories() {
  categoryTrigger.classList.toggle(
    "active-filter",
    selectedCategories.size > 0,
  );
  categoryTrigger.querySelector("span").textContent = selectedCategories.size
    ? `Categories · ${selectedCategories.size}`
    : "Categories";
  categoryChips.replaceChildren();
  for (const [category, input] of categoryInputs)
    input.checked = selectedCategories.has(category);
  for (const category of selectedCategories) {
    const label = category[0].toUpperCase() + category.slice(1);
    const chip = textElement("button", "category-chip", label);
    chip.type = "button";
    chip.setAttribute("aria-label", `Remove ${label} category`);
    const icon = document.createElement("img");
    icon.src = "assets/discovery/chip-close.svg";
    icon.alt = "";
    chip.append(icon);
    chip.addEventListener("click", () => {
      selectedCategories.delete(category);
      updateCategories();
      categoryTrigger.focus();
      void requestEvents();
    });
    categoryChips.append(chip);
  }
  updateDiscoveryIcons();
}
for (const category of EVENT_CATEGORIES) {
  const label = document.createElement("label");
  const input = document.createElement("input");
  input.type = "checkbox";
  input.id = `category-${category}`;
  input.value = category;
  categoryInputs.set(category, input);
  input.addEventListener("change", () => {
    if (input.checked) selectedCategories.add(category);
    else selectedCategories.delete(category);
    updateCategories();
    void requestEvents();
  });
  label.append(input, category[0].toUpperCase() + category.slice(1));
  categoryMenu.querySelector(".category-options").append(label);
}
categoryTrigger.addEventListener("click", () => {
  datePicker.close();
  categoryMenu.hidden = !categoryMenu.hidden;
  categoryTrigger.setAttribute("aria-expanded", String(!categoryMenu.hidden));
  if (!categoryMenu.hidden) categoryMenu.querySelector("input").focus();
});
categoryMenu
  .querySelector("[data-close]")
  .addEventListener("click", () => closeCategories(true));
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && !categoryMenu.hidden) {
    event.preventDefault();
    closeCategories(true);
  }
});
document.addEventListener("click", (event) => {
  if (
    !categoryMenu.contains(event.target) &&
    !categoryTrigger.contains(event.target)
  )
    closeCategories();
});
const datePicker = createDatePicker(
  () => void requestEvents(),
  () => closeCategories(),
);
const filtersToggle = document.querySelector("#toggle-filters");
const discoveryFilters = document.querySelector("#discovery-filters");
filtersToggle.addEventListener("click", () => {
  closeCategories();
  datePicker.close();
  discoveryFilters.hidden = !discoveryFilters.hidden;
  filtersToggle.setAttribute("aria-expanded", String(!discoveryFilters.hidden));
  filtersToggle.textContent = discoveryFilters.hidden
    ? "Show filters"
    : "Hide filters";
});
const queryInput = document.querySelector("#title-query");
const clearQuery = document.querySelector("#clear-query");
queryInput.addEventListener("input", () => {
  clearQuery.hidden = !queryInput.value;
  void requestEvents();
});
clearQuery.addEventListener("click", () => {
  queryInput.value = "";
  clearQuery.hidden = true;
  queryInput.focus();
  void requestEvents();
});
document.querySelector("#clear-all").addEventListener("click", clearAllChoices);
try {
  const saved = JSON.parse(localStorage.getItem("bee-there-discovery"));
  if (saved && typeof saved.query === "string") queryInput.value = saved.query;
  if (Array.isArray(saved?.categories)) {
    for (const category of saved.categories)
      if (EVENT_CATEGORIES.has(category)) selectedCategories.add(category);
  }
  if (["any", "today", "tomorrow", "weekend"].includes(saved?.date?.kind))
    datePicker.setChoice(saved.date, false);
  if (saved?.date?.kind === "custom") {
    const { start, end } = saved.date;
    const validDay = (day) =>
      typeof day === "string" &&
      /^\d{4}-\d{2}-\d{2}$/.test(day) &&
      parseDay(formatDay(day)) === day;
    if (validDay(start) && validDay(end) && end >= start) {
      const notice = document.querySelector("#discovery-notice");
      if (end < today()) {
        notice.textContent =
          "Date filter reset. Your saved dates have passed. Showing any upcoming date.";
      } else if (start < today()) {
        datePicker.setChoice({ kind: "custom", start: today(), end }, false);
        notice.textContent = `Date range adjusted. Your range now starts today, ${formatDay(today(), false)}.`;
      } else datePicker.setChoice(saved.date, false);
      notice.hidden = !notice.textContent;
    }
  }
} catch {
  /* Ignore invalid or unavailable local preferences. */
}
clearQuery.hidden = !queryInput.value;
updateCategories();
void requestEvents();
