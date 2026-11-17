import { addDays } from "./discovery-dates.js";

const EVENT_TIME_ZONE = "Europe/Belgrade";
const NO_SYNC_NOTICE =
  "One-time copy from BeeThere. Later event changes will not update this calendar entry.";

const localDayFormatter = new Intl.DateTimeFormat("en-CA", {
  timeZone: EVENT_TIME_ZONE,
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
});
const startDateFormatter = new Intl.DateTimeFormat("en-GB", {
  timeZone: EVENT_TIME_ZONE,
  year: "numeric",
  month: "long",
  day: "numeric",
});
const startTimeFormatter = new Intl.DateTimeFormat("en-GB", {
  timeZone: EVENT_TIME_ZONE,
  hour: "2-digit",
  minute: "2-digit",
  hourCycle: "h23",
});

function unknownEndNotice(startsAt) {
  const start = new Date(startsAt);
  const date = startDateFormatter.format(start);
  const time = startTimeFormatter.format(start);
  return (
    `STARTS: ${date} at ${time} (${EVENT_TIME_ZONE}).\n` +
    "End time unknown. Added as all-day because no end time was provided."
  );
}

function calendarEntry(event) {
  const allDay = event.ends_at === null;
  const start = allDay
    ? localDayFormatter.format(new Date(event.starts_at))
    : event.starts_at;
  return {
    title: event.title,
    allDay,
    start,
    end: allDay ? addDays(start, 1) : event.ends_at,
    timeZone: EVENT_TIME_ZONE,
    location: event.location_name?.trim(),
    description: [
      ...(allDay ? [unknownEndNotice(event.starts_at)] : []),
      `Source: ${event.source_url}`,
      NO_SYNC_NOTICE,
    ].join("\n\n"),
  };
}

function googleDate(value, allDay) {
  if (allDay) return value.replaceAll("-", "");
  return new Date(value)
    .toISOString()
    .replace(/[-:]/g, "")
    .replace(/\.\d{3}Z$/, "Z");
}

export function googleCalendarUrl(event) {
  const entry = calendarEntry(event);
  const url = new URL("https://calendar.google.com/calendar/render");
  url.search = new URLSearchParams({
    action: "TEMPLATE",
    text: entry.title,
    dates: `${googleDate(entry.start, entry.allDay)}/${googleDate(entry.end, entry.allDay)}`,
    ctz: entry.timeZone,
    details: entry.description,
  });
  if (entry.location) url.searchParams.set("location", entry.location);
  return url.href;
}
