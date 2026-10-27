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

function renderEvent(event) {
  const card = document.createElement("article");
  card.className = "event-card";
  card.append(
    textElement("h2", "event-title", event.title),
    textElement("p", "event-summary", event.summary),
    textElement(
      "p",
      "event-category",
      event.category.charAt(0).toUpperCase() + event.category.slice(1),
    ),
  );

  const start = new Date(event.starts_at);
  const time = document.createElement("time");
  time.dateTime = event.starts_at;
  time.append(
    textElement("span", "event-date", eventDateFormatter.format(start)),
    " ",
    textElement("span", "event-time", eventTimeFormatter.format(start)),
  );
  card.append(time);
  card.append(textElement("p", "event-location", event.location_name));

  const source = textElement("a", "event-source", event.source_name);
  source.href = event.source_url;
  source.target = "_blank";
  source.rel = "noopener noreferrer";
  card.append(source);
  return card;
}

function removeRetry() {
  document.querySelector("#retry")?.remove();
}

function showError(status) {
  status.textContent = "Could not load events.";
  const retry = textElement("button", "", "Retry");
  retry.id = "retry";
  retry.type = "button";
  retry.addEventListener("click", () => void requestEvents());
  status.after(retry);
}

async function requestEvents() {
  const status = document.querySelector("#status");
  const eventList = document.querySelector("#event-list");
  removeRetry();
  eventList.replaceChildren();
  status.textContent = "Loading events…";

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

    status.textContent = events.length === 0 ? "No upcoming events." : "";
    eventList.append(...events.map(renderEvent));
  } catch {
    showError(status);
  }
}

void requestEvents();
