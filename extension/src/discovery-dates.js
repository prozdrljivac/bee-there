const localDateFormatter = new Intl.DateTimeFormat("en-CA", {
  timeZone: "Europe/Belgrade",
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
});

export function today() {
  return localDateFormatter.format(new Date());
}

export function addDays(day, count) {
  const date = new Date(`${day}T12:00:00Z`);
  date.setUTCDate(date.getUTCDate() + count);
  return date.toISOString().slice(0, 10);
}

const months = [
  "Jan",
  "Feb",
  "Mar",
  "Apr",
  "May",
  "Jun",
  "Jul",
  "Aug",
  "Sep",
  "Oct",
  "Nov",
  "Dec",
];

export function formatDay(day, withYear = true) {
  const [year, month, date] = day.split("-").map(Number);
  return `${String(date).padStart(2, "0")} ${months[month - 1]}${withYear ? ` ${year}` : ""}`;
}

export function parseDay(text) {
  const match = /^(\d{1,2}) ([A-Za-z]{3}) (\d{4})$/.exec(text.trim());
  if (!match) return null;
  const month = months.findIndex(
    (value) => value.toLowerCase() === match[2].toLowerCase(),
  );
  if (month < 0) return null;
  const day = `${match[3]}-${String(month + 1).padStart(2, "0")}-${match[1].padStart(2, "0")}`;
  const parsed = new Date(`${day}T12:00:00Z`);
  return Number.isFinite(parsed.getTime()) &&
    parsed.toISOString().slice(0, 10) === day
    ? day
    : null;
}

function midnight(day) {
  const noon = Date.parse(`${day}T12:00:00Z`);
  let low = noon - 36 * 3600000;
  let high = noon;
  while (low < high) {
    const middle = low + Math.floor((high - low) / 2);
    if (localDateFormatter.format(new Date(middle)) < day) low = middle + 1;
    else high = middle;
  }
  return new Date(low).toISOString();
}

export function dateBounds(choice, currentDay = today()) {
  let start = currentDay;
  let end = currentDay;
  if (choice.kind === "any") return { from: midnight(start) };
  if (choice.kind === "tomorrow") start = end = addDays(currentDay, 1);
  if (choice.kind === "weekend") {
    const weekday = new Date(`${currentDay}T12:00:00Z`).getUTCDay();
    start = addDays(currentDay, weekday === 0 ? 0 : (6 - weekday + 7) % 7);
    end = addDays(start, weekday === 0 ? 0 : 1);
  }
  if (choice.kind === "custom") ({ start, end } = choice);
  return { from: midnight(start), to: midnight(addDays(end, 1)) };
}
