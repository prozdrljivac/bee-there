import { API_BASE_URL } from "./config.js";

const EVENT_TIME_ZONE = "Europe/Belgrade";
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
  card.append(source);
  return card;
}

async function requestEvents() {
  const url = new URL("/api/events", API_BASE_URL);
  url.searchParams.set("from", startOfToday().toISOString());
  const response = await fetch(url);
  const events = await response.json();
  document.querySelector("#event-list").append(...events.map(renderEvent));
}

void requestEvents();
