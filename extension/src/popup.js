import { API_BASE_URL } from "./config.js";

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
const dateFormatter = new Intl.DateTimeFormat("en-CA-u-ca-gregory-nu-latn", {
  timeZone: EVENT_TIME_ZONE,
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
});
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

function dateParts(timestamp) {
  const parts = dateFormatter.formatToParts(new Date(timestamp));
  return Object.fromEntries(
    parts
      .filter((part) => part.type !== "literal")
      .map((part) => [part.type, Number(part.value)]),
  );
}

function compareDates(left, right) {
  return (
    left.year - right.year ||
    left.month - right.month ||
    left.day - right.day
  );
}

function startOfToday() {
  const target = dateParts(Date.now());
  const approximateMidnight = Date.UTC(
    target.year,
    target.month - 1,
    target.day,
  );
  let low = approximateMidnight - 36 * 60 * 60 * 1000;
  let high = approximateMidnight + 36 * 60 * 60 * 1000;

  while (low < high) {
    const middle = low + Math.floor((high - low) / 2);
    if (compareDates(dateParts(middle), target) < 0) {
      low = middle + 1;
    } else {
      high = middle;
    }
  }

  return new Date(low);
}

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
  status.className = "visually-hidden";
  status.textContent = "Loading events…";
  eventList.setAttribute("aria-busy", "true");
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

function showEmpty(status, eventList) {
  status.className = "visually-hidden";
  status.textContent = "No upcoming events.";
  eventList.replaceChildren(
    stateElement(
      "✳",
      "A quiet moment.",
      "No upcoming events right now. Come back soon for your next good plan.",
    ),
  );
}

function showError(status, eventList) {
  status.className = "visually-hidden";
  status.textContent = "Could not load events.";
  const state = stateElement(
    "↻",
    "A small bump in the road.",
    "We could not load the events. Please try again.",
  );
  const retry = textElement("button", "", "Try again");
  retry.id = "retry";
  retry.type = "button";
  retry.addEventListener("click", () => void requestEvents());
  state.append(retry);
  eventList.replaceChildren(state);
}

async function requestEvents() {
  const status = document.querySelector("#status");
  const eventList = document.querySelector("#event-list");
  removeRetry();
  showLoading(status, eventList);

  try {
    const url = new URL("/api/events", API_BASE_URL);
    url.searchParams.set("from", startOfToday().toISOString());
    const response = await fetch(url);
    if (!response.ok) {
      throw new Error(`Event request failed with status ${response.status}`);
    }
    const events = await response.json();
    if (!Array.isArray(events) || !events.every(isValidEvent)) {
      throw new TypeError("Event response is invalid");
    }

    eventList.setAttribute("aria-busy", "false");
    if (events.length === 0) {
      showEmpty(status, eventList);
    } else {
      status.className = "";
      status.textContent = "";
      eventList.replaceChildren(...events.map(renderEvent));
    }
  } catch {
    eventList.setAttribute("aria-busy", "false");
    showError(status, eventList);
  }
}

void requestEvents();
