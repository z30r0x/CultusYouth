import { card, h, initShell, loadOpps, mount, t } from "./common.js";
import { byDeadline, daysLeft, isOpen } from "./utils.js";

const $ = (s) => document.querySelector(s);
let open = [];

function countUp(el, v) {
  if (matchMedia("(prefers-reduced-motion: reduce)").matches || !v) { el.textContent = v; return; }
  const t0 = performance.now();
  (function f(now) { const k = Math.min((now - t0) / 800, 1); el.textContent = Math.round(v * (1 - (1 - k) ** 3)); if (k < 1) requestAnimationFrame(f); })(t0);
}
function render() {
  mount($("#soon"), open.slice(0, 5).map(card));
  if (!open.length) $("#soon").textContent = "—";
}

initShell(render);
$("#hs").onsubmit = (e) => { e.preventDefault(); location.href = "opportunities.html?q=" + encodeURIComponent($("#hq").value.trim().slice(0, 100)); };
["internship", "scholarship", "competition", "hackathon", "ctf", "workshop"].forEach((k) =>
  $("#hchips").append(h("a", { className: "chip", href: "opportunities.html?type=" + k, textContent: t("type." + k) })));

open = (await loadOpps()).filter((o) => isOpen(o)).sort(byDeadline);
countUp($("#n1"), open.length);
countUp($("#n2"), open.filter((o) => { const n = daysLeft(o); return n !== null && n <= 7; }).length);
render();
