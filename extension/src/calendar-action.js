import { googleCalendarUrl } from "./calendar-export.js";

let tooltipId = 0;

document.addEventListener("keydown", (event) => {
  if (event.key !== "Escape") return;
  for (const tooltip of document.querySelectorAll(".calendar-tooltip")) {
    tooltip.hidden = true;
  }
});

function withTooltip(link) {
  const control = document.createElement("span");
  control.className = "calendar-control";
  const tooltip = document.createElement("span");
  tooltip.className = "calendar-tooltip";
  tooltip.id = `calendar-tooltip-${++tooltipId}`;
  tooltip.setAttribute("role", "tooltip");
  tooltip.textContent = "Add to Google Calendar";
  tooltip.hidden = true;
  link.setAttribute("aria-describedby", tooltip.id);
  control.append(link, tooltip);

  function showTooltip() {
    tooltip.classList.remove("above");
    tooltip.hidden = false;
    const results = control.closest("#results");
    if (
      results &&
      tooltip.getBoundingClientRect().bottom > results.getBoundingClientRect().bottom
    ) {
      tooltip.classList.add("above");
    }
  }

  let hovered = false;
  control.addEventListener("pointerenter", (event) => {
    if (event.pointerType === "touch") return;
    hovered = true;
    showTooltip();
  });
  control.addEventListener("pointerleave", () => {
    hovered = false;
    if (document.activeElement !== link) tooltip.hidden = true;
  });
  link.addEventListener("focus", showTooltip);
  link.addEventListener("blur", () => {
    if (!hovered) tooltip.hidden = true;
  });
  return control;
}

function calendarIcon() {
  const icon = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  icon.setAttribute("viewBox", "0 0 16 16");
  icon.setAttribute("aria-hidden", "true");
  const outline = document.createElementNS("http://www.w3.org/2000/svg", "path");
  outline.setAttribute(
    "d",
    "M3.33 3.33h9.34c.73 0 1.33.6 1.33 1.34v8c0 .73-.6 1.33-1.33 1.33H3.33C2.6 14 2 13.4 2 12.67v-8c0-.74.6-1.34 1.33-1.34Z",
  );
  const detail = document.createElementNS("http://www.w3.org/2000/svg", "path");
  detail.setAttribute(
    "d",
    "M10.67 2v2.67M5.33 2v2.67M2 7.33h12M8 9v3M6.5 10.5h3",
  );
  icon.append(outline, detail);
  return icon;
}

export function createCalendarAction(event) {
  const link = document.createElement("a");
  link.className = "calendar-action";
  link.href = googleCalendarUrl(event);
  link.target = "_blank";
  link.rel = "noopener noreferrer";
  link.setAttribute(
    "aria-label",
    `Add ${event.title} to Google Calendar (opens a new tab)`,
  );
  link.append(calendarIcon());
  return withTooltip(link);
}
