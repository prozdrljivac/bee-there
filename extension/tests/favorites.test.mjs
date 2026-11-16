import assert from "node:assert/strict";
import { afterEach, test } from "node:test";
import { loadFavorites, writeFavorites } from "../src/favorites.js";

const originalStorage = globalThis.localStorage;
afterEach(() => {
  if (originalStorage === undefined) delete globalThis.localStorage;
  else globalThis.localStorage = originalStorage;
});

function storageWith(value) {
  globalThis.localStorage = {
    getItem(key) {
      assert.equal(key, "bee-there-favorites");
      return value;
    },
    setItem(key, next) {
      assert.equal(key, "bee-there-favorites");
      value = next;
    },
  };
}

test("missing favorites start empty and IDs round trip without snapshots or caps", () => {
  storageWith(null);
  assert.deepEqual([...loadFavorites()], []);
  const ids = new Set(Array.from({ length: 3000 }, (_, index) => `event-${index}`));
  writeFavorites(ids);
  assert.deepEqual(loadFavorites(), ids);
});

test("saved IDs are deduplicated without dropping absent IDs", () => {
  storageWith('["absent-event","current-event","absent-event"]');
  assert.deepEqual([...loadFavorites()], ["absent-event", "current-event"]);
});

test("invalid favorites are not treated as an empty collection", () => {
  for (const saved of ["broken", "{}", '["event",42]']) {
    storageWith(saved);
    assert.throws(() => loadFavorites());
  }
});

test("storage failures propagate rather than reporting success", () => {
  const failure = new Error("Storage blocked");
  globalThis.localStorage = {
    getItem() { throw failure; },
    setItem() { throw failure; },
  };
  assert.throws(() => loadFavorites(), error => error === failure);
  assert.throws(() => writeFavorites(new Set(["event"])), error => error === failure);
});
