import assert from "node:assert/strict";
import { test } from "node:test";
import { googleCalendarUrl } from "../src/calendar-export.js";

const event = {
  title: "City Jazz Night",
  summary: "This summary must stay in BeeThere.",
  starts_at: "2027-01-15T19:00:00+01:00",
  ends_at: "2027-01-15T21:00:00+01:00",
  location_name: "Riverside Hall",
  source_url: "https://example.org/jazz-night",
};

test("a timed Google draft contains the known schedule and source, not the summary", () => {
  const link = googleCalendarUrl(event);
  assert.match(link, /^https:\/\/calendar\.google\.com\/calendar\/render\?/);
  const params = new URL(link).searchParams;
  assert.equal(params.get("action"), "TEMPLATE");
  assert.equal(params.get("text"), event.title);
  assert.equal(params.get("dates"), "20270115T180000Z/20270115T200000Z");
  assert.equal(params.get("ctz"), "Europe/Belgrade");
  assert.equal(params.get("location"), "Riverside Hall");
  assert.equal(
    params.get("details"),
    "Source: https://example.org/jazz-night\n\n" +
      "One-time copy from BeeThere. Later event changes will not update this calendar entry.",
  );
  assert.deepEqual([...params.keys()].sort(), [
    "action", "ctz", "dates", "details", "location", "text",
  ]);
});

test("timed drafts preserve overnight, summer and clock-change instants", () => {
  const schedules = [
    ["2027-01-15T23:30:00+01:00", "2027-01-16T01:30:00+01:00", "20270115T223000Z/20270116T003000Z"],
    ["2027-07-15T20:00:00+02:00", "2027-07-15T22:00:00+02:00", "20270715T180000Z/20270715T200000Z"],
    ["2027-03-28T01:30:00+01:00", "2027-03-28T03:30:00+02:00", "20270328T003000Z/20270328T013000Z"],
    ["2027-10-31T02:30:00+02:00", "2027-10-31T02:30:00+01:00", "20271031T003000Z/20271031T013000Z"],
  ];
  for (const [starts_at, ends_at, expected] of schedules) {
    const params = new URL(googleCalendarUrl({ ...event, starts_at, ends_at })).searchParams;
    assert.equal(params.get("dates"), expected);
    assert.equal(params.get("ctz"), "Europe/Belgrade");
  }
});

test("all-day entries use Belgrade dates through year, leap-day and DST boundaries", () => {
  const schedules = [
    ["2027-12-31T23:30:00Z", "20280101/20280102"],
    ["2028-02-28T23:30:00Z", "20280229/20280301"],
    ["2027-03-28T21:30:00Z", "20270328/20270329"],
    ["2027-10-31T23:30:00Z", "20271101/20271102"],
  ];
  for (const [starts_at, expected] of schedules) {
    const params = new URL(googleCalendarUrl({ ...event, starts_at, ends_at: null })).searchParams;
    assert.equal(params.get("dates"), expected);
  }
});

test("titles, venues and source links survive Unicode and URL punctuation without extra fields", () => {
  const title = "Café & Music + 🎵 #Live / " + "Long title ".repeat(100);
  const location_name = "  North & South + Gallery  ";
  const source_url = "https://example.org/event?ref=calendar&lang=en#tickets";
  const params = new URL(googleCalendarUrl({ ...event, title, location_name, source_url })).searchParams;
  assert.equal(params.get("text"), title);
  assert.equal(params.get("location"), location_name.trim());
  assert.ok(params.get("details").startsWith(`Source: ${source_url}\n\n`));
  assert.equal(params.has("lang"), false);
  assert.equal(params.has("summary"), false);
});

test("missing and blank venues leave the Google location unset", () => {
  for (const location_name of [null, "", "   "]) {
    const params = new URL(googleCalendarUrl({ ...event, location_name })).searchParams;
    assert.equal(params.has("location"), false);
  }
});

test("an unknown end becomes one all-day date in Novi Sad with the actual start first", () => {
  const params = new URL(googleCalendarUrl({
    ...event,
    starts_at: "2027-01-15T23:30:00Z",
    ends_at: null,
  })).searchParams;
  assert.equal(params.get("dates"), "20270116/20270117");
  assert.equal(
    params.get("details"),
    "STARTS: 16 January 2027 at 00:30 (Europe/Belgrade).\n" +
      "End time unknown. Added as all-day because no end time was provided.\n\n" +
      "Source: https://example.org/jazz-night\n\n" +
      "One-time copy from BeeThere. Later event changes will not update this calendar entry.",
  );
});
