import test from "node:test";
import assert from "node:assert/strict";
import { match, tagsOf } from "./matcher.js";

const now = new Date(2026, 9, 6);
const O = [
  { id: "1", name: "Past thing", deadline: "2026-10-01", tracks: ["web"], type: "internship", mode: "remote" },
  { id: "2", name: "Later cyber bootcamp", deadline: "2026-10-30", tracks: ["cybersecurity"], type: "workshop", mode: "remote" },
  { id: "3", name: "No deadline language course", deadline: null, tracks: ["languages"], type: "scholarship", mode: "remote" },
  { id: "4", name: "Soon flutter internship", deadline: "2026-10-08", tracks: ["mobile"], type: "internship", mode: "onsite" },
];
test("show all: only open, soonest first, no-deadline last", () => {
  const r = match("show me all open opportunities", O, now);
  assert.equal(r.kind, "all");
  assert.deepEqual(r.items.map((o) => o.id), ["4", "2", "3"]);
  assert.equal(match("اعرض كل الفرص المتاحة", O, now).kind, "all");
});
test("matches in English and Arabic", () => {
  assert.equal(match("flutter internship", O, now).items[0].id, "4");
  assert.equal(match("أمن سيبراني", O, now).items[0].id, "2");
});
test("short words need whole-word match ('training' must not trigger ai)", () => {
  assert.ok(!tagsOf("training").has("ai"));
  assert.ok(tagsOf("AI projects").has("ai"));
});
test("no match", () => assert.equal(match("underwater basket weaving", O, now).kind, "none"));
