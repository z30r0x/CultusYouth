# Cultus Youth (100% free stack)

```
web/       the whole site + chatbot (static files, no server): index.html, opportunities.html, css/, js/, data/opportunities.json
scraper/   Python script you run on your PC: Telegram -> email for approval -> web/data/opportunities.json
```

## Free tools used
| Need | Tool (free) |
|---|---|
| Hosting the site | GitHub Pages, Vercel, Netlify or Cloudflare Pages |
| Chatbot | runs in the browser (`web/js/matcher.js`): no server, no API key |
| Reading Telegram | Telethon + your own free Telegram API id (my.telegram.org) |
| Approval emails | Gmail SMTP with an App Password |
| Updating the data | run the scraper locally, then `git push` |

## Run locally
```bash
cd web && python -m http.server 8080        # http://localhost:8080 (must be served, not double-clicked)

cd scraper && pip install -r requirements.txt && cp .env.example .env   # fill .env
python fetch_opportunities.py                  # fetch -> email you
python fetch_opportunities.py --approve all    # or ids from the email
git add ../web/data/opportunities.json && git commit -m "Update opportunities" && git push
```

## Deploy (GitHub Pages)
Repo -> Settings -> Pages -> deploy from branch `main`, folder `/web` (or use Vercel/Netlify with root directory `web`).
Every push of `opportunities.json` updates the site.

## What you must edit
- `web/js/config.js`: `SUGGEST_EMAIL`
- `web/index.html`: the `#` social links; founder bio in `web/js/i18n.js` (`founder.bio`)
- `scraper/.env`: Telegram + email settings
- `web/data/opportunities.json`: delete the 8 `sample/...` records before going live

## "Open" opportunities
Open = deadline today or later, or no deadline. The chatbot's "show all open" lists them soonest first (no-deadline last);
the Opportunities page hides expired ones by default.

## Tests
```bash
node --test web/js/utils.test.mjs web/js/matcher.test.mjs
cd scraper && python -m pytest -q
```

## Security
Scraped text is shown with `textContent` only; links must be http(s); a Content-Security-Policy limits scripts to this site;
the chatbot never sends anything to a server. Never commit `.env`, `*.session`, `pending.json` (blocked by `.gitignore`).
