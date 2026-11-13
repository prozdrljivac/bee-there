import { today, formatDay, parseDay, dateBounds } from "./discovery-dates.js";
import { createCalendar } from "./calendar.js";

const presetLabels = {
  any: "Date · Any",
  today: "Today",
  tomorrow: "Tomorrow",
  weekend: "This weekend",
};

export function createDatePicker(onChange, beforeOpen) {
  const trigger = document.querySelector("#date-trigger");
  const menu = document.querySelector("#date-menu");
  const custom = document.querySelector("#custom-menu");
  const start = document.querySelector("#custom-start");
  const end = document.querySelector("#custom-end");
  const feedback = document.querySelector("#date-feedback");
  let applied = { kind: "any" };
  let range = false;
  let activeInput = start;
  const calendar = createCalendar((day) => {
    if (range && activeInput === end) end.value = formatDay(day);
    else {
      start.value = formatDay(day);
      if (range) {
        end.value = "";
        activeInput = end;
      }
    }
    validate();
  });
  start.addEventListener("focus", () => {
    activeInput = start;
  });
  end.addEventListener("focus", () => {
    activeInput = end;
  });

  function setChoice(choice, notify = true) {
    applied = choice;
    trigger.classList.toggle("active-filter", choice.kind !== "any");
    for (const button of menu.querySelectorAll("[data-date]")) {
      button.setAttribute(
        "aria-pressed",
        String(button.dataset.date === choice.kind),
      );
    }
    trigger.querySelector("span").textContent =
      choice.kind === "custom"
        ? choice.start === choice.end
          ? formatDay(choice.start, false)
          : `${formatDay(choice.start, false)}–${formatDay(choice.end, false)}`
        : presetLabels[choice.kind];
    if (notify) onChange(choice);
  }

  function close(restoreFocus = false) {
    menu.hidden = custom.hidden = true;
    trigger.setAttribute("aria-expanded", "false");
    if (restoreFocus) trigger.focus();
  }

  function setMode(isRange) {
    range = isRange;
    document
      .querySelector("#mode-single")
      .setAttribute("aria-pressed", String(!range));
    document
      .querySelector("#mode-range")
      .setAttribute("aria-pressed", String(range));
    document.querySelector("#end-label").hidden = !range;
    document.querySelector("#start-label").textContent = range
      ? "From"
      : "Date";
    validate();
  }

  function validate() {
    const first = parseDay(start.value);
    const last = range ? parseDay(end.value) : first;
    const past = (first && first < today()) || (last && last < today());
    const reversed = first && last && last < first;
    const invalid =
      past ||
      reversed ||
      (start.value && !first) ||
      (range && end.value && !last);
    start.setAttribute("aria-invalid", String(Boolean(invalid)));
    end.setAttribute("aria-invalid", String(Boolean(invalid)));
    feedback.classList.toggle("date-error", Boolean(invalid));
    if (invalid) {
      feedback.textContent =
        past || reversed
          ? "Choose today or later. End must not precede start."
          : "Use a valid date in DD MMM YYYY format.";
      return;
    }
    calendar.select(first, last);
    if (!first || !last) {
      feedback.textContent = range
        ? "Choose an end date. The previous date filter stays active."
        : "Choose a date. The previous date filter stays active.";
      return;
    }
    feedback.textContent = `${range ? "Range" : "Date"} applied · ${formatDay(first)}${range ? `–${formatDay(last)} (inclusive)` : ""}`;
    if (
      applied.kind !== "custom" ||
      applied.start !== first ||
      applied.end !== last
    )
      setChoice({ kind: "custom", start: first, end: last });
  }

  function updatePresetDetails() {
    const dayLabel = new Intl.DateTimeFormat("en-GB", {
      timeZone: "Europe/Belgrade",
      weekday: "short",
    });
    const shortLabel = new Intl.DateTimeFormat("en-GB", {
      timeZone: "Europe/Belgrade",
      day: "numeric",
      month: "short",
    });
    for (const kind of ["today", "tomorrow", "weekend"]) {
      const button = menu.querySelector(`[data-date="${kind}"]`);
      let detail = button.querySelector("small");
      if (!detail) {
        detail = document.createElement("small");
        button.append(detail);
      }
      const bounds = dateBounds({ kind });
      detail.textContent =
        kind === "weekend"
          ? `${shortLabel.format(new Date(bounds.from))}–${shortLabel.format(new Date(Date.parse(bounds.to) - 1))}`
          : `${dayLabel.format(new Date(bounds.from))}, ${shortLabel.format(new Date(bounds.from))}`;
    }
  }

  trigger.addEventListener("click", () => {
    if (!menu.hidden || !custom.hidden) return close();
    beforeOpen();
    updatePresetDetails();
    setChoice(applied, false);
    menu.hidden = false;
    trigger.setAttribute("aria-expanded", "true");
    menu.querySelector("[data-date]").focus();
  });
  for (const button of menu.querySelectorAll("[data-date]")) {
    button.addEventListener("click", () => {
      const kind = button.dataset.date;
      if (kind !== "custom") {
        setChoice({ kind });
        close(true);
        return;
      }
      menu.hidden = true;
      custom.hidden = false;
      start.value = applied.kind === "custom" ? formatDay(applied.start) : "";
      end.value =
        applied.kind === "custom" && applied.end !== applied.start
          ? formatDay(applied.end)
          : "";
      setMode(Boolean(end.value));
      calendar.show(applied.kind === "custom" ? applied.start : today());
      start.focus();
    });
  }
  for (const button of document.querySelectorAll(
    "#date-menu [data-close], #custom-menu [data-close]",
  ))
    button.addEventListener("click", () => close(true));
  document
    .querySelector("#mode-single")
    .addEventListener("click", () => setMode(false));
  document
    .querySelector("#mode-range")
    .addEventListener("click", () => setMode(true));
  function handleDateInput(event) {
    validate();
    const day = parseDay(event.target.value);
    if (day && day >= today()) calendar.show(day);
  }
  start.addEventListener("input", handleDateInput);
  end.addEventListener("input", handleDateInput);
  document.querySelector("#clear-date").addEventListener("click", () => {
    setChoice({ kind: "any" });
    close(true);
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && (!menu.hidden || !custom.hidden)) {
      event.preventDefault();
      close(true);
    }
  });
  document.addEventListener("click", (event) => {
    const path = event.composedPath();
    if (
      !path.includes(trigger) &&
      !path.includes(menu) &&
      !path.includes(custom)
    )
      close();
  });
  return {
    setChoice,
    close,
    get choice() {
      return applied;
    },
  };
}
