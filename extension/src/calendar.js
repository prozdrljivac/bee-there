import { today, addDays, formatDay } from "./discovery-dates.js";

function moveMonth(day, amount) {
  const date = new Date(`${day}T12:00:00Z`);
  const dayOfMonth = date.getUTCDate();
  date.setUTCDate(1);
  date.setUTCMonth(date.getUTCMonth() + amount);
  const lastDay = new Date(
    Date.UTC(date.getUTCFullYear(), date.getUTCMonth() + 1, 0),
  ).getUTCDate();
  date.setUTCDate(Math.min(dayOfMonth, lastDay));
  return date.toISOString().slice(0, 10);
}

export function createCalendar(onSelect) {
  const grid = document.querySelector("#calendar");
  const previous = document.querySelector("#previous-month");
  let focused = today();
  let selectedStart;
  let selectedEnd;

  function render(day = focused, focus = false) {
    focused = day < today() ? today() : day;
    const first = `${focused.slice(0, 7)}-01`;
    const month = new Date(`${first}T12:00:00Z`);
    document.querySelector("#calendar-month").textContent =
      month.toLocaleDateString("en-GB", {
        month: "long",
        year: "numeric",
        timeZone: "UTC",
      });
    previous.disabled = first <= `${today().slice(0, 7)}-01`;
    document.querySelector("#calendar-note").textContent =
      `Today: ${formatDay(today(), false)} · Past days are disabled`;
    grid.replaceChildren();
    const heading = document.createElement("div");
    heading.className = "calendar-week";
    heading.setAttribute("role", "row");
    for (const name of ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]) {
      const label = document.createElement("span");
      label.setAttribute("role", "columnheader");
      label.textContent = name;
      heading.append(label);
    }
    grid.append(heading);
    const offset = (month.getUTCDay() + 6) % 7;
    let row;
    for (let index = 0; index < offset + 31; index++) {
      const candidate = addDays(first, index - offset);
      if (candidate.slice(0, 7) !== first.slice(0, 7) && index >= offset) break;
      if (index % 7 === 0) {
        row = document.createElement("div");
        row.className = "calendar-week";
        row.setAttribute("role", "row");
        grid.append(row);
      }
      const cell = document.createElement("div");
      cell.setAttribute("role", "gridcell");
      row.append(cell);
      if (index < offset) continue;
      const button = document.createElement("button");
      button.type = "button";
      button.dataset.day = candidate;
      button.textContent = Number(candidate.slice(8));
      button.setAttribute("aria-label", formatDay(candidate));
      const selected = candidate === selectedStart || candidate === selectedEnd;
      cell.setAttribute("aria-selected", String(selected));
      button.classList.toggle(
        "in-range",
        Boolean(
          selectedStart &&
          selectedEnd &&
          candidate > selectedStart &&
          candidate < selectedEnd,
        ),
      );
      if (candidate === today()) button.setAttribute("aria-current", "date");
      button.disabled = candidate < today();
      button.tabIndex = candidate === focused ? 0 : -1;
      button.addEventListener("click", () => {
        focused = candidate;
        onSelect(candidate);
      });
      button.addEventListener("keydown", (event) => {
        const offsets = {
          ArrowLeft: -1,
          ArrowRight: 1,
          ArrowUp: -7,
          ArrowDown: 7,
        };
        let next;
        if (event.key in offsets) next = addDays(candidate, offsets[event.key]);
        if (event.key === "PageUp") next = moveMonth(candidate, -1);
        if (event.key === "PageDown") next = moveMonth(candidate, 1);
        if (event.key === "Home")
          next = addDays(
            candidate,
            -((new Date(`${candidate}T12:00:00Z`).getUTCDay() + 6) % 7),
          );
        if (event.key === "End")
          next = addDays(
            candidate,
            6 - ((new Date(`${candidate}T12:00:00Z`).getUTCDay() + 6) % 7),
          );
        if (!next) return;
        event.preventDefault();
        render(next, true);
      });
      cell.append(button);
    }
    if (focus) grid.querySelector(`[data-day="${focused}"]`)?.focus();
  }
  previous.addEventListener("click", () => render(moveMonth(focused, -1)));
  document
    .querySelector("#next-month")
    .addEventListener("click", () => render(moveMonth(focused, 1)));
  return {
    show(day) {
      render(day || today());
    },
    select(start, end) {
      selectedStart = start;
      selectedEnd = end;
      const hadFocus = grid.contains(document.activeElement);
      render(focused, hadFocus);
    },
  };
}
