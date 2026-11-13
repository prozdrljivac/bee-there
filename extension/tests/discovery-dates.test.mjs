import assert from "node:assert/strict";
import { test } from "node:test";

test("Belgrade local dates have DST-safe inclusive day bounds", async () => {
  const { dateBounds } = await import("../src/discovery-dates.js");
  assert.deepEqual(
    dateBounds(
      { kind: "custom", start: "2025-03-30", end: "2025-03-30" },
      "2025-03-29",
    ),
    {
      from: "2025-03-29T23:00:00.000Z",
      to: "2025-03-30T22:00:00.000Z",
    },
  );
  assert.deepEqual(
    dateBounds(
      { kind: "custom", start: "2025-10-26", end: "2025-10-26" },
      "2025-10-25",
    ),
    {
      from: "2025-10-25T22:00:00.000Z",
      to: "2025-10-26T23:00:00.000Z",
    },
  );
});

test("relative dates recalculate and Sunday keeps the remaining weekend", async () => {
  const { dateBounds } = await import("../src/discovery-dates.js");
  assert.deepEqual(dateBounds({ kind: "any" }, "2025-03-30"), {
    from: "2025-03-29T23:00:00.000Z",
  });
  assert.deepEqual(dateBounds({ kind: "today" }, "2025-03-30"), {
    from: "2025-03-29T23:00:00.000Z",
    to: "2025-03-30T22:00:00.000Z",
  });
  assert.deepEqual(dateBounds({ kind: "tomorrow" }, "2025-03-30"), {
    from: "2025-03-30T22:00:00.000Z",
    to: "2025-03-31T22:00:00.000Z",
  });
  assert.deepEqual(dateBounds({ kind: "weekend" }, "2025-03-30"), {
    from: "2025-03-29T23:00:00.000Z",
    to: "2025-03-30T22:00:00.000Z",
  });
  assert.deepEqual(dateBounds({ kind: "weekend" }, "2025-03-31"), {
    from: "2025-04-04T22:00:00.000Z",
    to: "2025-04-06T22:00:00.000Z",
  });
});
