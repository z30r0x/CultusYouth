// Pure helpers (no DOM) so they can be unit-tested with `node --test`.
export const DAY = 864e5;
const day0 = (d) => new Date(d.getFullYear(), d.getMonth(), d.getDate());

/** Whole days until the deadline (0 = today, negative = expired, null = no deadline listed). */
export function daysLeft(o, now = new Date()) {
  if (!o.deadline) return null;
  const [y, m, d] = o.deadline.split("-").map(Number);
  return Math.round((new Date(y, m - 1, d) - day0(now)) / DAY);
}
export const isOpen = (o, now) => { const n = daysLeft(o, now); return n === null || n >= 0; };
/** Soonest first; opportunities without a deadline go last. */
export const byDeadline = (a, b) => (a.deadline ?? "9999").localeCompare(b.deadline ?? "9999");
export const byNewest = (a, b) => (b.posted_at ?? "").localeCompare(a.posted_at ?? "");
/** Only http(s) links are ever rendered as hrefs. */
export function safeUrl(u) {
  try { const p = new URL(u); return ["http:", "https:"].includes(p.protocol) ? p.href : null; } catch { return null; }
}
