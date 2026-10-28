const THEME_STORAGE_KEY = "bee-there-theme";
const THEME_OVERRIDES = new Set(["light", "dark"]);

function applyTheme(theme) {
  if (THEME_OVERRIDES.has(theme)) {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem(THEME_STORAGE_KEY, theme);
  } else {
    delete document.documentElement.dataset.theme;
    localStorage.removeItem(THEME_STORAGE_KEY);
  }
}

const savedTheme = localStorage.getItem(THEME_STORAGE_KEY);
if (THEME_OVERRIDES.has(savedTheme)) {
  document.documentElement.dataset.theme = savedTheme;
}

document.addEventListener("DOMContentLoaded", () => {
  const selectedTheme = THEME_OVERRIDES.has(savedTheme)
    ? savedTheme
    : "system";
  const selectedInput = document.querySelector(
    `input[name="theme"][value="${selectedTheme}"]`,
  );
  selectedInput.checked = true;

  for (const input of document.querySelectorAll('input[name="theme"]')) {
    input.addEventListener("change", () => {
      if (input.checked) {
        applyTheme(input.value);
      }
    });
  }
});
