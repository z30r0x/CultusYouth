"""
Cultus Youth - Telegram opportunities fetcher.

Reads Arabic posts from ONE of:
  topic   : a topic inside a forum-style Telegram group   (Telethon, login required)
  search  : a channel/group filtered by hashtag/keyword    (Telethon, login required)
  channel : a public channel via t.me/s/<name>             (no login)

Extracts name / deadline / apply link, labels each post (track, mode, type),
sanitizes everything, and writes opportunities.json for the Opportunities page.

Deadlines written without a year are resolved relative to the POST's own date,
so the result never depends on the day you run the script.

New posts are NOT published directly: they go to pending.json and are emailed to you.
Approve / reject them with:  python fetch_opportunities.py --approve <id>... | all
                             python fetch_opportunities.py --reject  <id>... | all
Fix deadlines of existing records: python fetch_opportunities.py --refresh-dates
Config comes from environment variables / .env (see .env.example).
"""
import argparse
import hashlib
import html
import json
import os
import re
import smtplib
import ssl
import sys
from email.message import EmailMessage
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urlparse

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

OUTPUT = Path(os.getenv("OUTPUT_FILE", "opportunities.json"))      # approved, read by the website
PENDING = Path(os.getenv("PENDING_FILE", "pending.json"))          # awaiting your approval
REJECTED = Path(os.getenv("REJECTED_FILE", "rejected.json"))       # ids you rejected (never re-sent)
MAX_PER_EMAIL = 50
YEARLESS_GRACE_DAYS = 30   # a yearless date up to this many days BEFORE the post date stays in the post's year

# ============================================================ label rules
TRACKS = {
    "web": ["web", "ويب", "frontend", "backend", "full stack", "فرونت", "باك اند", "تطوير المواقع"],
    "mobile": ["mobile", "موبايل", "flutter", "android", "ios", "تطبيقات الجوال", "تطبيقات الموبايل"],
    "cybersecurity": ["cyber", "security", "الأمن السيبراني", "الامن السيبراني", "امن سيبراني", "اختراق", "ctf", "penetration"],
    "data": ["data", "بيانات", "analytics", "تحليل البيانات", "علم البيانات"],
    "ai": [" ai ", "ai.", "(ai)", "artificial intelligence", "machine learning", "ذكاء اصطناعي",
           "الذكاء الاصطناعي", "تعلم الآلة", "تعلم الالة", "deep learning", "llm"],
    "competitive programming": ["competitive programming", "icpc", "codeforces", "البرمجة التنافسية", "برمجة تنافسية"],
    "research": ["research", "بحث", "أبحاث", "ابحاث", "باحث", "phd", "ماجستير", "دكتوراه"],
    "languages": ["ielts", "toefl", "لغة", "لغات", "language", "الإنجليزية", "الانجليزية", "ألماني", "المانية", "فرنسي"],
}

# single label, first match wins -> most specific first
TYPES = [
    ("ctf", ["ctf", "capture the flag"]),
    ("hackathon", ["hackathon", "هاكاثون", "هاكاتون"]),
    ("scholarship", ["scholarship", "منحة", "منح ", "fellowship", "زمالة", "تمويل كامل"]),
    ("internship", ["internship", "intern ", "تدريب", "برنامج تدريبي", "co-op"]),
    ("competition", ["competition", "contest", "مسابقة", "مسابقات", "تحدي", "challenge"]),
    ("workshop", ["workshop", "ورشة", "ورشه", "webinar", "ويبينار", "bootcamp", "معسكر", "كورس", "دورة", "course"]),
]
VALID_TYPES = {t for t, _ in TYPES}

REMOTE_WORDS = ["remote", "online", "عن بعد", "اونلاين", "أونلاين", "اون لاين", "أون لاين", "افتراضي", "virtual"]
ONSITE_WORDS = ["onsite", "on-site", "in person", "in-person", "حضوري", "حضورياً", "حضوريا", "في مقر", "hybrid"]

# ============================================================ sanitization
CTRL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f\u202a-\u202e\u2066-\u2069]")  # control + bidi override chars
TAG_RE = re.compile(r"<[^>]*>")


def clean_text(s, max_len=4000):
    """Plain text only: no HTML tags/entities, no control or bidi-override chars."""
    s = html.unescape(s or "")
    s = TAG_RE.sub("", s)
    s = CTRL_RE.sub("", s)
    return s.strip()[:max_len]


def safe_url(u):
    """Allow only http(s) URLs with a host. Blocks javascript:, data:, etc."""
    try:
        p = urlparse((u or "").strip())
    except ValueError:
        return None
    if p.scheme not in ("http", "https") or not p.netloc or len(u) > 500:
        return None
    return u.strip()


# ============================================================ date parsing
AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")

MONTHS = {
    1: ["january", "jan", "يناير", "كانون الثاني"],
    2: ["february", "feb", "فبراير", "شباط"],
    3: ["march", "mar", "مارس", "آذار"],
    4: ["april", "apr", "أبريل", "ابريل", "نيسان"],
    5: ["may", "مايو", "أيار"],
    6: ["june", "jun", "يونيو", "يونيه", "حزيران"],
    7: ["july", "jul", "يوليو", "يوليه", "تموز"],
    8: ["august", "aug", "أغسطس", "اغسطس", "آب"],
    9: ["september", "sept", "sep", "سبتمبر", "أيلول"],
    10: ["october", "oct", "أكتوبر", "اكتوبر", "تشرين الأول"],
    11: ["november", "nov", "نوفمبر", "تشرين الثاني"],
    12: ["december", "dec", "ديسمبر", "كانون الأول"],
}
MONTH_LOOKUP = {n: num for num, names in MONTHS.items() for n in names}
MONTH_RE = "|".join(sorted(map(re.escape, MONTH_LOOKUP), key=len, reverse=True))

DEADLINE_HINTS = ["آخر موعد", "اخر موعد", "الموعد النهائي", "ينتهي", "التقديم حتى", "التقديم قبل",
                  "قبل", "حتى", "deadline", "apply by", "closes", "last date", "due"]

NUM_DATE = re.compile(r"(\d{1,2})\s*[/\-.]\s*(\d{1,2})(?:\s*[/\-.]\s*(\d{2,4}))?")
TEXT_DMY = re.compile(rf"(\d{{1,2}})\s*(?:من\s*)?({MONTH_RE})\.?,?\s*(\d{{4}})?", re.I)
TEXT_MDY = re.compile(rf"({MONTH_RE})\.?\s*(\d{{1,2}})(?:st|nd|rd|th)?,?\s*(\d{{4}})?", re.I)


def _mk(y, m, d, ref):
    """Build a date. Explicit year wins. Missing year: use ref's year, or the next one
    if that date would fall more than YEARLESS_GRACE_DAYS before `ref` (the post date)."""
    try:
        if y is None:
            dt = date(ref.year, m, d)
            return date(ref.year + 1, m, d) if (ref - dt).days > YEARLESS_GRACE_DAYS else dt
        y = int(y)
        return date(y + 2000 if y < 100 else y, m, d)
    except ValueError:
        return None


def find_dates(line, ref):
    out = []
    for m in TEXT_DMY.finditer(line):
        out.append(_mk(m.group(3), MONTH_LOOKUP[m.group(2).lower()], int(m.group(1)), ref))
    for m in TEXT_MDY.finditer(line):
        out.append(_mk(m.group(3), MONTH_LOOKUP[m.group(1).lower()], int(m.group(2)), ref))
    for m in NUM_DATE.finditer(line):
        a, b, y = int(m.group(1)), int(m.group(2)), m.group(3)
        out.append(_mk(y, a, b, ref) if (b > 12 and a <= 12) else _mk(y, b, a, ref))  # default dd/mm
    return [d for d in out if d]


def extract_deadline(text, ref):
    """Date on/after a deadline keyword line; otherwise the latest date in the post.
    `ref` is the post's date (used only to infer a missing year)."""
    lines = text.translate(AR_DIGITS).splitlines()
    for i, line in enumerate(lines):
        if any(h in line.lower() for h in DEADLINE_HINTS):
            ds = find_dates(line, ref) or (find_dates(lines[i + 1], ref) if i + 1 < len(lines) else [])
            if ds:
                return ds[0].isoformat()
    every = [d for ln in lines for d in find_dates(ln, ref)]
    return max(every).isoformat() if every else None


def post_date(post, fallback):
    """The post's own date (so the year is inferred from when it was posted); `fallback` if unknown."""
    try:
        return datetime.fromisoformat(post["posted_at"]).date()
    except (TypeError, ValueError, KeyError):
        return fallback


# ============================================================ field extraction
URL_RE = re.compile(r"https?://[^\s)>\]]+")
APPLY_HINTS = ["رابط التقديم", "للتقديم", "سجل", "apply", "register", "التسجيل"]
SKIP_DOMAINS = ("t.me/", "telegram.me/", "wa.me/", "chat.whatsapp.com", "instagram.com",
                "facebook.com", "x.com", "twitter.com")
JUNK = re.compile(r"[#@]\S+|https?://\S+|[\U0001F000-\U0001FAFF\u2600-\u27BF\u2B50\u200d\ufe0f•●▪]+")
NAME_PREFIX = re.compile(r"^(فرصة|فرصه|إعلان|اعلان|opportunity|new)\s*[:：\-–]\s*", re.I)


def extract_link(links, text):
    cands = [u for u in dict.fromkeys(list(links) + URL_RE.findall(text))
             if safe_url(u) and not any(s in u for s in SKIP_DOMAINS)]
    if not cands:
        return None
    for line in text.splitlines():
        if any(h in line.lower() for h in APPLY_HINTS):
            for u in URL_RE.findall(line):
                if u in cands:
                    return u
    return cands[0]


def extract_name(text):
    for line in text.splitlines():
        name = NAME_PREFIX.sub("", JUNK.sub("", line).strip()).strip(" -–:|*_")
        if len(name) >= 6:
            return name[:120]
    return "Untitled opportunity"


def _has(text, words):
    return any(w.lower() in text for w in words)


def label(text, default_type=None):
    t = f" {text.lower()} "
    tracks = [k for k, w in TRACKS.items() if _has(t, w)]
    otype = next((k for k, w in TYPES if _has(t, w)), default_type)
    remote, onsite = _has(t, REMOTE_WORDS), _has(t, ONSITE_WORDS)
    mode = "onsite" if onsite else "remote" if remote else None   # hybrid/both -> onsite
    return tracks, mode, otype


def build_record(post, today, default_type=None):
    text = clean_text(post["text"])
    tracks, mode, otype = label(text, default_type)
    deadline = extract_deadline(text, post_date(post, today))
    link = extract_link(post["links"], text)
    return {
        "id": str(post["post_id"]),
        "name": extract_name(text),
        "deadline": deadline,
        "apply_url": link,
        "tracks": tracks,
        "mode": mode,
        "type": otype,
        "posted_at": post["posted_at"],
        "source_url": safe_url(post.get("source_url")),
        "needs_review": not (otype and link and deadline),
    }


# ============================================================ sources
def _post_from_msg(msg, group, topic_id):
    from telethon.tl.types import MessageEntityTextUrl
    links = []
    for ent, txt in msg.get_entities_text():
        links.append(ent.url if isinstance(ent, MessageEntityTextUrl) else txt)
    slug = group if isinstance(group, str) else None
    src = None
    if slug:
        src = f"https://t.me/{slug}/{topic_id}/{msg.id}" if topic_id else f"https://t.me/{slug}/{msg.id}"
    return {"post_id": f"{group}/{msg.id}", "source_url": src, "posted_at": msg.date.isoformat(),
            "text": msg.raw_text, "links": [u for u in links if safe_url(u)]}


def fetch_telethon(group, topic_id=None, search=None, limit=100):
    """Modes 'topic' and 'search'. First run asks for phone + login code, saves cultus.session."""
    from telethon.sync import TelegramClient
    group = int(group) if str(group).lstrip("-").isdigit() else group
    kwargs = {"limit": limit}
    if topic_id:
        kwargs["reply_to"] = int(topic_id)
    if search:
        kwargs["search"] = search
    posts = []
    with TelegramClient("cultus", int(os.environ["TG_API_ID"]), os.environ["TG_API_HASH"]) as client:
        for msg in client.iter_messages(group, **kwargs):
            if msg.raw_text:
                posts.append(_post_from_msg(msg, group, topic_id))
    return posts


def fetch_public_channel(username, pages=3):
    """Mode 'channel': public preview page, no login."""
    import requests
    from bs4 import BeautifulSoup
    posts, before = [], None
    for _ in range(pages):
        url = f"https://t.me/s/{username}" + (f"?before={before}" if before else "")
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0 (CultusYouthBot)"}, timeout=20)
        r.raise_for_status()
        wraps = BeautifulSoup(r.text, "html.parser").select(".tgme_widget_message_wrap")
        if not wraps:
            break
        for w in wraps:
            msg, body, tm = (w.select_one(".tgme_widget_message"), w.select_one(".tgme_widget_message_text"),
                             w.select_one("time"))
            if not msg or not body:
                continue
            for br in body.find_all("br"):
                br.replace_with("\n")
            pid = msg["data-post"]
            posts.append({"post_id": pid, "source_url": f"https://t.me/{pid}",
                          "posted_at": tm["datetime"] if tm and tm.has_attr("datetime") else None,
                          "text": body.get_text("\n"), "links": [a["href"] for a in body.find_all("a", href=True)]})
        before = int(wraps[0].select_one(".tgme_widget_message")["data-post"].split("/")[1])
    return posts


def fetch_posts():
    mode = os.getenv("TG_MODE", "topic").lower()
    group = os.getenv("TG_GROUP")
    if not group:
        sys.exit("Set TG_GROUP in .env")
    if mode == "topic":
        return fetch_telethon(group, topic_id=os.environ["TG_TOPIC_ID"], limit=int(os.getenv("TG_LIMIT", 100)))
    if mode == "search":
        return fetch_telethon(group, search=os.environ["TG_SEARCH"], limit=int(os.getenv("TG_LIMIT", 100)))
    if mode == "channel":
        return fetch_public_channel(group, pages=int(os.getenv("TG_PAGES", 3)))
    sys.exit("TG_MODE must be topic, search or channel")


# ============================================================ state files
def _load(path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def _save(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def short_id(post_id):
    return hashlib.sha1(post_id.encode()).hexdigest()[:6]


# ============================================================ email (plain text only)
def format_email_body(recs):
    lines = [f"{len(recs)} new opportunities are waiting for your approval.",
             "Links come from Telegram posts: verify them before clicking.", ""]
    for r in recs:
        lines += [f"[{r['short_id']}] {r['name']}",
                  f"  Type: {r['type'] or '?'} | Mode: {r['mode'] or '?'} | Tracks: {', '.join(r['tracks']) or '?'}",
                  f"  Deadline: {r['deadline'] or '?'}",
                  f"  Apply: {r['apply_url'] or '-'}",
                  f"  Source: {r['source_url'] or '-'}"]
        if r["needs_review"]:
            lines.append("  ! Some fields were not detected - check the source post")
        lines.append("")
    lines += ["Approve: python fetch_opportunities.py --approve <id> [<id> ...]   (or: --approve all)",
              "Reject:  python fetch_opportunities.py --reject <id> [<id> ...]"]
    return "\n".join(lines)


def email_configured():
    return all(os.getenv(k) for k in ("SMTP_HOST", "SMTP_USER", "SMTP_APP_PASSWORD", "EMAIL_TO"))


def send_email(recs):
    """Fixed subject (no scraped text in headers), plain-text body, TLS enforced, app password from env."""
    host, user = os.environ["SMTP_HOST"], os.environ["SMTP_USER"]
    port = int(os.getenv("SMTP_PORT", 465))
    msg = EmailMessage()
    msg["Subject"] = f"Cultus Youth: {len(recs)} new opportunities to review"
    msg["From"], msg["To"] = user, os.environ["EMAIL_TO"]
    msg.set_content(format_email_body(recs))
    ctx = ssl.create_default_context()
    if port == 465:
        with smtplib.SMTP_SSL(host, port, context=ctx, timeout=30) as smtp:
            smtp.login(user, os.environ["SMTP_APP_PASSWORD"])
            smtp.send_message(msg)
    else:
        with smtplib.SMTP(host, port, timeout=30) as smtp:
            smtp.starttls(context=ctx)
            smtp.login(user, os.environ["SMTP_APP_PASSWORD"])
            smtp.send_message(msg)


def notify_pending():
    pending = _load(PENDING, [])
    todo = [r for r in pending if not r.get("emailed")][:MAX_PER_EMAIL]
    if not todo:
        return
    if not email_configured():
        print("[!] Email not configured (SMTP_* / EMAIL_TO). Run with --list to see pending items.")
        return
    try:
        send_email(todo)
    except (smtplib.SMTPException, OSError) as e:
        print(f"[!] Email failed ({type(e).__name__}); items stay pending and will be retried.", file=sys.stderr)
        return
    sent = {r["id"] for r in todo}
    for r in pending:
        if r["id"] in sent:
            r["emailed"] = True
    _save(PENDING, pending)
    print(f"Emailed {len(todo)} opportunities for review.")


# ============================================================ collect / approve / reject / refresh
def collect():
    today = date.today()
    default_type = os.getenv("TG_DEFAULT_TYPE") or None
    if default_type not in VALID_TYPES | {None}:
        sys.exit(f"TG_DEFAULT_TYPE must be one of {sorted(VALID_TYPES)}")

    pending = _load(PENDING, [])
    seen = {o["id"] for o in _load(OUTPUT, [])} | {r["id"] for r in pending} | set(_load(REJECTED, []))

    new = 0
    for post in fetch_posts():
        rec = build_record(post, today, default_type)
        if rec["id"] in seen or not (rec["apply_url"] or rec["deadline"] or rec["type"]):
            continue
        rec.update(short_id=short_id(rec["id"]), emailed=False)
        pending.append(rec)
        seen.add(rec["id"])
        new += 1
    _save(PENDING, pending)
    print(f"+{new} new pending, {len(pending)} awaiting approval")
    notify_pending()


def resolve(ids, approve):
    pending = _load(PENDING, [])
    approved = {o["id"]: o for o in _load(OUTPUT, [])}
    rejected = set(_load(REJECTED, []))
    chosen = pending if "all" in ids else [r for r in pending if r["short_id"] in set(ids)]
    unknown = set(ids) - {"all"} - {r["short_id"] for r in pending}
    for r in chosen:
        if approve:
            approved[r["id"]] = {k: v for k, v in r.items() if k not in ("short_id", "emailed")}
        else:
            rejected.add(r["id"])
    chosen_ids = {r["id"] for r in chosen}
    _save(PENDING, [r for r in pending if r["id"] not in chosen_ids])
    _save(REJECTED, sorted(rejected))
    items = sorted(approved.values(), key=lambda o: o["posted_at"] or "", reverse=True)
    _save(OUTPUT, items)
    print(f"{'Approved' if approve else 'Rejected'} {len(chosen)}; unknown ids: {sorted(unknown) or 'none'}")


def refresh_dates():
    """Re-parse deadlines of existing records (approved + pending) with the post-date-based year logic.
    Only posts still inside the TG_LIMIT / TG_PAGES fetch window are updated."""
    today = date.today()
    default_type = os.getenv("TG_DEFAULT_TYPE") or None
    fresh = {}
    for post in fetch_posts():
        rec = build_record(post, today, default_type)
        fresh[rec["id"]] = rec["deadline"]
    for path in (OUTPUT, PENDING):
        data, changed = _load(path, []), 0
        for r in data:
            if r["id"] in fresh and r.get("deadline") != fresh[r["id"]]:
                r["deadline"] = fresh[r["id"]]
                r["needs_review"] = not (r.get("type") and r.get("apply_url") and r["deadline"])
                changed += 1
        _save(path, data)
        print(f"{path.name}: {changed} deadlines updated")


def main():
    ap = argparse.ArgumentParser(description="Cultus Youth opportunities fetcher")
    ap.add_argument("--approve", nargs="+", metavar="ID", help="short ids from the email, or 'all'")
    ap.add_argument("--reject", nargs="+", metavar="ID", help="short ids from the email, or 'all'")
    ap.add_argument("--list", action="store_true", help="show pending items")
    ap.add_argument("--refresh-dates", action="store_true", help="re-parse deadlines of existing records")
    args = ap.parse_args()
    if args.approve:
        resolve(args.approve, True)
    elif args.reject:
        resolve(args.reject, False)
    elif args.list:
        for r in _load(PENDING, []):
            print(f"[{r['short_id']}] {r['name']} | {r['deadline']} | {r['apply_url']}")
    elif args.refresh_dates:
        refresh_dates()
    else:
        collect()


if __name__ == "__main__":
    main()