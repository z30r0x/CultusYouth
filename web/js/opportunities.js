import { card, h, initShell, loadOpps, mount, t } from "./common.js";
import { SUGGEST_EMAIL } from "./config.js";
import { byDeadline, byNewest, isOpen } from "./utils.js";

const $ = (s) => document.querySelector(s);
const TYPES = ["internship", "scholarship", "competition", "hackathon", "ctf", "workshop"];
const TRACKS = ["web", "mobile", "cybersecurity", "data", "ai", "competitive programming", "research", "languages"];
let all = [], track = "";
const params = new URLSearchParams(location.search);

function filtered() {
  const q = $("#q").value.toLowerCase().trim(), type = $("#type").value, mode = $("#mode").value, hide = $("#hide").getAttribute("aria-pressed") === "true";
  return all
    .filter((o) => (!q || `${o.name} ${o.type} ${o.mode} ${(o.tracks || []).join(" ")}`.toLowerCase().includes(q))
      && (!type || o.type === type) && (!mode || o.mode === mode) && (!track || (o.tracks || []).includes(track)) && (!hide || isOpen(o)))
    .sort($("#sort").value === "n" ? byNewest : byDeadline);
}
function render() {
  const r = filtered();
  mount($("#grid"), r.map(card));
  $("#empty").hidden = r.length > 0;
  $("#count").textContent = t("count", { n: r.length, o: all.filter((o) => isOpen(o)).length, m: all.length });
}
function buildControls() {
  const keep = { type: $("#type").value, mode: $("#mode").value };
  mount($("#type"), [h("option", { value: "", textContent: t("f.type") }), ...TYPES.map((k) => h("option", { value: k, textContent: t("type." + k) }))]);
  mount($("#mode"), [h("option", { value: "", textContent: t("f.mode") }), ...["remote", "onsite"].map((k) => h("option", { value: k, textContent: t("mode." + k) }))]);
  $("#type").value = keep.type; $("#mode").value = keep.mode;
  mount($("#sort"), [h("option", { value: "d", textContent: t("sort.d") }), h("option", { value: "n", textContent: t("sort.n") })]);
  mount($("#tracks"), [["", t("track.all")], ...TRACKS.map((k) => [k, t("track." + k)])].map(([k, label]) =>
    h("button", { className: "chip" + (k === track ? " on" : ""), textContent: label, onclick: () => { track = k; buildControls(); render(); } })));
}

initShell(() => { buildControls(); render(); });
buildControls();
$("#q").value = (params.get("q") || "").slice(0, 100);
if (TYPES.includes(params.get("type"))) $("#type").value = params.get("type");
["#q", "#type", "#mode", "#sort"].forEach((s) => $(s).addEventListener("input", render));
$("#hide").onclick = (e) => { const b = e.currentTarget; const on = b.getAttribute("aria-pressed") !== "true"; b.setAttribute("aria-pressed", on); b.classList.toggle("on", on); render(); };
$("#suggest").href = `mailto:${SUGGEST_EMAIL}?subject=${encodeURIComponent("Opportunity suggestion")}`;
all = await loadOpps();
render();
