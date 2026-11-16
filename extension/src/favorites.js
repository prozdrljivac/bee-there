const STORAGE_KEY = "bee-there-favorites";

export function loadFavorites() {
  const saved = JSON.parse(localStorage.getItem(STORAGE_KEY));
  if (saved === null) return new Set();
  if (!Array.isArray(saved) || !saved.every((id) => typeof id === "string")) {
    throw new TypeError("Invalid saved favorites");
  }
  return new Set(saved);
}

export function writeFavorites(ids) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify([...ids]));
}
