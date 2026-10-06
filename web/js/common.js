// Shared by both pages: language, theme, data loading, card rendering, and the chatbot widget.
import { T } from "./i18n.js";
import { match } from "./matcher.js";
import { daysLeft, safeUrl } from "./utils.js";

const $ = (s) => document.querySelector(s);
const store = {
  get: (k, d) => { try { return localStorage.getItem(k) ?? d; } catch { return d; } },
  set: (k, v) => { try { localStorage.setItem(k, v); } catch { /* storage blocked: ignore */ } },
};
export function h(tag, props = {}, ...kids) { const e = Object.assign(document.createElement(tag), props); e.append(...kids); return e; }

export let lang = store.get("cy-lang", "en") === "ar" ? "ar" : "en";
export const t = (k, vars = {}) => (T[lang][k] ?? T.en[k] ?? k).replace(/\{(\w+)\}/g, (_, v) => vars[v] ?? "");
const locale = () => (lang === "ar" ? "ar-EG-u-nu-latn" : "en");

export function applyLang() {
  document.documentElement.lang = lang;
  document.documentElement.dir = lang === "ar" ? "rtl" : "ltr";
  document.querySelectorAll("[data-i18n]").forEach((e) => (e.textContent = t(e.dataset.i18n)));
  document.querySelectorAll("[data-i18n-ph]").forEach((e) => (e.placeholder = t(e.dataset.i18nPh)));
  document.querySelectorAll("[data-i18n-aria]").forEach((e) => { e.setAttribute("aria-label", t(e.dataset.i18nAria)); e.title = t(e.dataset.i18nAria); });
  document.title = t(document.body.dataset.title) + " | Cultus Youth";
  $("#lang").textContent = lang === "ar" ? "EN" : "ع";
}
export function initShell(onLang = () => {}) {
  document.documentElement.dataset.theme = store.get("cy-theme", "dark");
  $("#theme").onclick = () => {
    const r = document.documentElement; r.dataset.theme = r.dataset.theme === "dark" ? "light" : "dark"; store.set("cy-theme", r.dataset.theme);
  };
  $("#lang").onclick = () => { lang = lang === "ar" ? "en" : "ar"; store.set("cy-lang", lang); applyLang(); onLang(); };
  applyLang();
  initChat();
  const io = new IntersectionObserver((es) => es.forEach((e) => e.isIntersecting && (e.target.classList.add("in"), io.unobserve(e.target))), { threshold: 0.1 });
  document.querySelectorAll("section").forEach((s) => { s.classList.add("reveal"); io.observe(s); });
}

// ---- data -----------------------------------------------------------------
export async function loadOpps() {
  try {
    const r = await fetch("data/opportunities.json", { cache: "no-cache" });
    if (!r.ok) throw new Error(r.status);
    const data = await r.json();
    return Array.isArray(data) ? data : [];
  } catch (e) { console.error("Could not load opportunities", e); return []; }
}

// ---- rendering (DOM APIs only: scraped text is never parsed as HTML) -------
export function closes(n) {
  if (n === null) return t("nodl");
  if (n < 0) return t("expired");
  if (n === 0) return t("today");
  if (n === 1) return t("tomorrow");
  if (lang === "ar" && n === 2) return "يغلق خلال يومين";
  if (lang === "ar" && n <= 10) return `يغلق خلال ${n} أيام`;
  return t("in", { n });
}
export const dlClass = (n) => (n === null ? "far" : n <= 7 ? "urgent" : n <= 14 ? "soon" : "far");
const lbl = (prefix, v) => (v ? t(`${prefix}.${v}`) : "");
const link = (cls, href, text) => { const u = safeUrl(href); return u ? h("a", { className: cls, href: u, target: "_blank", rel: "noopener noreferrer", textContent: text }) : null; };

export function card(o) {
  const n = daysLeft(o);
  const sep = lang === "ar" ? "، " : ", ";
  const meta = [lbl("type", o.type), lbl("mode", o.mode)].filter(Boolean).join(sep);
  const date = o.deadline ? new Date(o.deadline + "T00:00:00").toLocaleDateString(locale(), { day: "numeric", month: "short", year: "numeric" }) : "";
  const tags = h("div", { className: "tags" }, ...(o.tracks || []).map((x) => h("span", { className: "tag", textContent: lbl("track", x) || x })));
  const row = h("div", { className: "row" }, ...[link("btn", o.apply_url, t("apply")), link("meta", o.source_url, t("tg"))].filter(Boolean));
  return h("article", { className: "card" },
    h("span", { className: "meta", textContent: meta }),
    h("h3", { textContent: o.name }), tags,
    h("div", {}, h("span", { className: "dl " + dlClass(n), textContent: closes(n) }), h("span", { className: "meta", textContent: date ? ` (${date})` : "" })),
    row);
}
export function mount(container, nodes) { nodes.forEach((n, i) => n.style?.setProperty("--i", i)); container.replaceChildren(...nodes); }

// ---- chatbot widget ---------------------------------------------------------
function addMsg(text, cls, items = []) {
  const m = h("div", { className: "m " + cls, textContent: text });
  items.forEach((o) => {
    const n = daysLeft(o);
    const mini = h("div", { className: "mini" }, h("strong", { textContent: o.name }), h("br"),
      h("span", { textContent: [lbl("type", o.type), closes(n)].filter(Boolean).join(" · ") }), h("br"));
    mini.append(h("a", { href: "opportunities.html?q=" + encodeURIComponent(o.name), textContent: t("see") }));
    const ap = link("", o.apply_url, t("apply")); if (ap) mini.append(" · ", ap);
    m.append(mini);
  });
  $("#msgs").append(m); $("#msgs").scrollTop = 1e9;
}
async function ask(text) {
  text = text.trim().slice(0, 500); if (!text) return;
  addMsg(text, "u");
  const dots = h("div", { className: "m b" }, h("span", { className: "dots" }, h("i"), h("i"), h("i")));
  $("#msgs").append(dots);
  const [{ kind, items }] = await Promise.all([loadOpps().then((o) => match(text, o)), new Promise((r) => setTimeout(r, 500))]);
  dots.remove();
  addMsg(t("bot." + (kind === "all" && !items.length ? "empty" : kind), { n: items.length }), "b", items);
}
function openChat(on) {
  $("#chat").classList.toggle("open", on); $("#fab").setAttribute("aria-expanded", on);
  if (on && !$("#msgs").children.length) {
    addMsg(t("chat.hi"), "b");
    ["q.all", "q.1", "q.2", "q.3"].forEach((k) => $("#qc").append(h("button", { className: "chip", textContent: t(k), onclick: () => ask(t(k)) })));
  }
}
function initChat() {
  $("#fab").onclick = () => openChat(!$("#chat").classList.contains("open"));
  $("#cx").onclick = () => openChat(false);
  $("#cf").onsubmit = (e) => { e.preventDefault(); const i = $("#ci"); ask(i.value); i.value = ""; };
}
