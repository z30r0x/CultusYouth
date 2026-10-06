import test from "node:test";
import assert from "node:assert/strict";
import { daysLeft, isOpen, byDeadline, safeUrl } from "./utils.js";

const now = new Date(2026, 9, 6, 15, 0); // 6 Oct 2026, afternoon
test("daysLeft", () => {
  assert.equal(daysLeft({ deadline: "2026-10-06" }, now), 0);
  assert.equal(daysLeft({ deadline: "2026-10-09" }, now), 3);
  assert.equal(daysLeft({ deadline: "2026-10-01" }, now), -5);
  assert.equal(daysLeft({ deadline: null }, now), null);
});
test("isOpen keeps today and no-deadline, drops expired", () => {
  assert.ok(isOpen({ deadline: "2026-10-06" }, now));
  assert.ok(isOpen({ deadline: null }, now));
  assert.ok(!isOpen({ deadline: "2026-10-05" }, now));
});
test("byDeadline puts missing deadlines last", () => {
  const s = [{ deadline: null }, { deadline: "2026-11-01" }, { deadline: "2026-10-10" }].sort(byDeadline);
  assert.deepEqual(s.map((x) => x.deadline), ["2026-10-10", "2026-11-01", null]);
});
test("safeUrl blocks non-http schemes", () => {
  assert.equal(safeUrl("javascript:alert(1)"), null);
  assert.equal(safeUrl("data:text/html,x"), null);
  assert.ok(safeUrl("https://a.com/x"));
});
