// Chatbot logic, runs in the browser: no server, no API key. Works on the already-loaded opportunities.json.
import { byDeadline, isOpen } from "./utils.js";

export const LEXICON = {
  web: ["web", "ويب", "frontend", "backend", "html", "react", "موقع", "مواقع"],
  mobile: ["mobile", "موبايل", "flutter", "android", "ios", "تطبيقات", "فلاتر"],
  cybersecurity: ["cyber", "security", "hacking", "سيبراني", "أمن", "امن", "اختراق"],
  data: ["data", "بيانات", "analytics", "python", "pandas"],
  ai: ["ai", "ml", "machine learning", "ذكاء", "تعلم الآلة", "تعلم الالة"],
  "competitive programming": ["competitive", "icpc", "codeforces", "تنافسية", "خوارزميات", "algorithms"],
  research: ["research", "masters", "master", "phd", "بحث", "أبحاث", "ماجستير", "دكتوراه"],
  languages: ["language", "ielts", "toefl", "german", "لغة", "لغات", "الماني", "ألماني", "انجليزي"],
  internship: ["internship", "intern", "training", "تدريب"],
  scholarship: ["scholarship", "funded", "fellowship", "منحة", "منح", "زمالة"],
  competition: ["competition", "contest", "مسابقة", "مسابقات"],
  hackathon: ["hackathon", "هاكاثون"],
  ctf: ["ctf"],
  workshop: ["workshop", "bootcamp", "course", "ورشة", "دورة", "معسكر"],
  remote: ["remote", "online", "عن بعد", "اونلاين", "أونلاين"],
  onsite: ["onsite", "on-site", "in person", "حضوري"],
};
const ALL_RE = /\b(all|every|everything|available|open|list|show)\b|كل|جميع|المتاح|المفتوح|اعرض|عرض/i;
const SKIP = new Set(["the", "and", "for", "with", "show", "all", "open"]);

export function tagsOf(msg) {
  const low = ` ${msg.toLowerCase()} `;
  const toks = new Set(low.match(/[a-z0-9]+/g) ?? []);
  const hit = (w) => (/^[a-z0-9 -]+$/.test(w) ? (w.length <= 3 ? toks.has(w) : low.includes(w)) : low.includes(w)); // short Latin words must match whole words
  return new Set(Object.entries(LEXICON).filter(([, ws]) => ws.some(hit)).map(([k]) => k));
}

/** -> { kind: "all" | "matches" | "none", items }. Only open opportunities, soonest deadline first. */
export function match(msg, opps, now = new Date(), limit = 5) {
  const open = opps.filter((o) => isOpen(o, now)).sort(byDeadline);
  const tags = tagsOf(msg);
  const words = (msg.toLowerCase().match(/[a-z0-9\u0600-\u06ff]{3,}/g) ?? []).filter((w) => !SKIP.has(w));
  if (ALL_RE.test(msg) && !tags.size) return { kind: "all", items: open };
  const score = (o) => {
    const own = new Set([...(o.tracks ?? []), o.type, o.mode]);
    const name = (o.name ?? "").toLowerCase();
    return 3 * [...tags].filter((t) => own.has(t)).length + words.filter((w) => name.includes(w)).length;
  };
  const hits = open.map((o) => [score(o), o]).filter(([s]) => s > 0).sort((a, b) => b[0] - a[0]).slice(0, limit).map(([, o]) => o);
  return hits.length ? { kind: "matches", items: hits } : { kind: "none", items: [] };
}
