# Cultus Youth: Opportunities Hub & Assistant

> A bilingual (Arabic / English) static website that collects scholarships, internships, competitions, hackathons, CTFs and workshops from the Cultus Youth Telegram channel, sorts them by deadline, and helps students find the right one through filters and a built-in assistant.

***

## 📌 Project Overview

**Cultus Youth** fixes a simple problem: students miss good opportunities because the posts get buried in chats and feeds. The project has two parts:

- **`web/`**: a static site (no server, no build step) with a home page and an Opportunities page.
- **`scraper/`**: a Python tool you run on your own PC. It reads the Telegram channel, extracts a short title, deadline, apply link and labels from each post, **emails you the list for approval**, and only writes approved items to `web/data/opportunities.json`.

Nothing reaches the website until you approve it.

***

## ✨ Key Features

### 🌐 Website
- Arabic and English UI with automatic RTL/LTR switching (language saved in `localStorage`).
- Dark and light theme.
- Home page: search box, type chips, live counters (open / closing within 7 days) and a "Closing soon" ticker.
- Opportunities page:
  - Text search, filters by type, format (remote/onsite) and track
  - Sort by upcoming deadline or newest post
  - "Hide expired" toggle
  - Deadline badges: urgent (7 days or fewer), soon (14 days or fewer), far
  - "Suggest an opportunity" button (opens an email)
- Deep links such as `opportunities.html?type=scholarship` and `?q=flutter`.
- Respects `prefers-reduced-motion`.

### 🤖 Opportunity Assistant (chatbot)
- Runs **entirely in the browser**: no server, no API key, nothing is sent anywhere.
- Understands English and Arabic keywords (field, type, remote/onsite) through a lexicon in `matcher.js`.
- "Show all open opportunities" lists every open item, soonest deadline first.
- Otherwise returns up to 5 best matches, scored by tags (3 points each) and title words.
- Short Latin words such as `ai` must match as whole words, so "training" does not trigger AI.

> It is a rule-based matcher, not an LLM. The only LLM use is optional title generation in the scraper.

### 📥 Telegram Scraper
- Three modes: `topic` (forum topic), `search` (hashtag) and `channel` (public preview page, no login).
- Extracts:
  - **Deadline**: Arabic and English months, Arabic-Indic digits, `dd/mm/yyyy`, text dates. A date on a line with a deadline word wins, otherwise the latest date.
  - **Apply link**: prefers URLs on lines with "apply" words and skips Telegram/social links.
  - **Title**: first meaningful line (skips "new opportunity!" headers), 60 characters max.
  - **Labels**: tracks, remote/onsite, and type.
- Optional AI titles from a free OpenAI-compatible API (`pollinations` needs no key, `groq` needs `AI_API_KEY`). Output is grounding-checked and falls back to the heuristic on any error. The LLM never touches the deadline or the link.
- Skips duplicates, expired posts, posts from other years, and chit-chat.
- Approval flow: email list, `--review` one by one (approve / reject / edit / skip), or by id.

***

## 🔄 Data Flow

```text
Telegram channel
      ▼
[ fetch_opportunities.py ]  sanitize → extract → label → (optional AI title)
      ▼
 scraper/pending.json  ──► email with numbered list
      ▼
 you: --review / --approve / --reject
      ▼
 web/data/opportunities.json   (only approved items)
      ▼
 git push  ──►  hosting (GitHub Pages / Vercel) redeploys
      ▼
 Website + Assistant read the JSON in the browser
```

***

## 🚀 Getting Started

### Prerequisites
- Python 3.10+ and Node 18+ (Node only for tests)
- A Telegram API id and hash from https://my.telegram.org
- A Gmail account with an **App Password** (for approval emails)

### 1. Run the website locally
```bash
cd web && python -m http.server 8080
# open http://localhost:8080 (it must be served, not double-clicked)
```

### 2. Configure the scraper
```bash
cd scraper
pip install -r requirements.txt
cp .env.example .env      # then fill in your own values
```

| Variable | Purpose |
|---|---|
| `TG_API_ID`, `TG_API_HASH` | Your Telegram API credentials |
| `TG_MODE` | `topic`, `search` or `channel` |
| `TG_GROUP`, `TG_TOPIC_ID`, `TG_SEARCH`, `TG_PAGES` | Where to read from |
| `TG_LIMIT`, `TG_YEAR` | Max messages, target year (defaults to the current year) |
| `TG_DEFAULT_TYPE` | Force a type when a topic is dedicated to one |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_APP_PASSWORD`, `EMAIL_TO` | Approval emails |
| `AI_PROVIDER`, `AI_API_KEY`, `AI_URL`, `AI_MODEL` | Optional AI titles |
| `OUTPUT_FILE` | Defaults to `../web/data/opportunities.json` |

### 3. Fetch, approve, publish
```bash
python fetch_opportunities.py                  # fetch → pending → email you
python fetch_opportunities.py --review         # approve / reject / edit one by one
python fetch_opportunities.py --approve a1b2c3 d4e5f6   # or: all
python fetch_opportunities.py --reject a1b2c3
python fetch_opportunities.py --list           # show pending
python fetch_opportunities.py --resend         # email the pending list again

git add ../web/data/opportunities.json
git commit -m "Update opportunities"
git push                                       # this is what updates the live site
```

***

## ☁️ Deploying

> **Approving does not update the live site by itself.** The scraper runs on your PC and only changes the local JSON file. The site updates when that file is pushed to GitHub and the host redeploys.

### Vercel
1. Import the GitHub repo.
2. Set **Root Directory** to `web`, **Framework Preset** to *Other*, and leave the build command empty.
3. After setup, every `git push` that changes `web/data/opportunities.json` triggers a new deployment automatically.

### GitHub Pages
Repo → Settings → Pages → deploy from branch `main`, folder `/web`.

***

## 📂 Project Structure

```text
web/
  index.html, opportunities.html
  css/
    common.css          Tokens, nav, cards, chat widget, motion
    home.css            Home page only
    opportunities.css   Opportunities page only
  js/
    common.js           Language, theme, data loading, card rendering, chat widget
    home.js             Counters, ticker, search redirect
    opportunities.js    Filters, sorting, URL params
    matcher.js          Assistant logic (bilingual lexicon + scoring)
    utils.js            Pure helpers: daysLeft, isOpen, sorting, safeUrl
    i18n.js             All UI text, English + Arabic
    config.js           SUGGEST_EMAIL
    utils.test.mjs, matcher.test.mjs
  data/opportunities.json   Approved items (what the site reads)
  assets/                   logo.jpg, founder.jpg

scraper/
  fetch_opportunities.py    Fetch, extract, label, email, review
  test_fetch_opportunities.py
  requirements.txt, .env.example
```

***

## 🔐 Security & Privacy

- **No user data is collected.** The assistant runs in the browser and sends nothing to a server. The only things stored are the theme and language in `localStorage` (wrapped in try/catch).
- **XSS-safe rendering:** scraped text is only inserted with `textContent` and DOM APIs, never `innerHTML`.
- **Link safety:** only `http(s)` links are rendered (`safeUrl` on both the scraper and the site), with `rel="noopener noreferrer"`.
- **Sanitization in the scraper:** HTML tags and entities removed; control and bidi-override characters stripped.
- **Prompt-injection defense for AI titles:** the post is passed as data inside `<post>` tags, output is cut to one line, and a grounding check rejects output not found in the post.
- **Content-Security-Policy:** scripts only from this site; `connect-src 'self'`; `base-uri 'none'`.
- **Email:** fixed subject (no scraped text in headers), TLS enforced, App Password only.
- **Human approval gate:** nothing is published without you approving it.
- **Never commit** `.env`, `*.session`, `pending.json` or `rejected.json` (all in `.gitignore`).

> `.env.example` must contain placeholders only. If real Telegram credentials were ever committed, revoke and regenerate them at my.telegram.org.

***

## 🧪 Tests

```bash
node --test web/js/utils.test.mjs web/js/matcher.test.mjs
cd scraper && python -m pytest -q
```

Covered: deadline and day math, sorting, URL safety, assistant matching (EN/AR), Arabic date parsing, title and link extraction, sanitization, year/expiry filters, approval and review flow, AI title safety.

***

## ✏️ Before Going Live

- [ ] Set `SUGGEST_EMAIL` in `web/js/config.js`
- [ ] Check the social links in `web/index.html` (Telegram, WhatsApp and Facebook currently use a wrong `target` value; it should be `_blank`)
- [ ] Review the founder bio in `web/js/i18n.js` (`founder.bio`)
- [ ] Remove any leftover `sample/...` records from `web/data/opportunities.json`
- [ ] Fill in `scraper/.env` with your own credentials

***

## 🧪 Current Limitations

- The scraper is manual: you run it, approve, then push.
- The assistant matches keywords; it does not understand free-form sentences.
- Records marked `needs_review: true` are missing a link or deadline; fix them with `--review` → edit.
- Titles come from the first meaningful line unless AI titles are enabled.

***

## 🛠 Tech Stack

- **Frontend:** HTML, CSS, vanilla JavaScript (ES modules), no build step
- **i18n:** custom dictionary with RTL support (DM Sans + Noto Sans Arabic)
- **Scraper:** Python, Telethon, requests, BeautifulSoup, python-dotenv
- **Tests:** `node --test`, pytest
- **Hosting:** GitHub Pages, Vercel, Netlify or Cloudflare Pages (all free)
