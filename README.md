# LeadFlow AI

An AI front desk for dental and physiotherapy clinics. A chat widget on the clinic's website answers visitors' questions **only from the clinic's own information**, cites where each answer came from, and, when a visitor wants an appointment or the assistant doesn't know, takes their details and alerts the team.

> **Status: phase 1 of 4, a working demo, not a finished product.** The clinic, its prices and its content are fictional. Read [What is and isn't done](#what-is-and-isnt-done) before showing it to a client.

## What it does

- **Grounded answers.** The assistant searches the clinic's documents, and Claude (or, with no API key, a built-in extractive answerer) writes the reply. Every answer shows its sources. A cited passage that wasn't actually retrieved is discarded, and an answer that cites nothing is not trusted. If the information isn't there, the assistant says so and offers to take a message instead of guessing.
- **Safety first.** Messages that look like emergencies (chest pain, difficulty breathing, a swollen face, self-harm) get a fixed reply pointing to 999, NHS 111 or Samaritans. No AI is involved, and the assistant is instructed never to diagnose or advise on treatment.
- **Lead capture with consent.** Visitors can leave their name and contact details, with an explicit permission tick box. Each lead gets a priority, a category and a score from simple, readable rules (not AI), so it works with no API key.
- **Team alerts.** Each new lead is posted to Slack (or any webhook that accepts `{"text": "..."}`). Failed sends are retried with growing delays, every attempt is recorded, and a failed alert can be resent from the dashboard.
- **Clinic dashboard** (React) at `/admin`: leads with status tracking, full conversations, a list of questions the assistant couldn't answer (so you know what to add), a knowledge base editor that takes effect immediately, and a copy-and-paste install snippet.
- **Built-in protection.** Rate limits on chat, leads and login; a daily cap on Claude calls; conversation length limits; the admin area is off unless a password is set.

## Try it

You need Python 3.11+ and Node 20+. No API key is required.

```bash
# 1. Backend
cd backend
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env                                    # then set LEADFLOW_ADMIN_PASSWORD

# 2. Dashboard (builds into frontend/dist, which the API serves at /admin)
cd ../frontend && npm install && npm run build && cd ../backend

# 3. Run with the fictional demo clinic loaded
LEADFLOW_SEED_DEMO=1 uvicorn app.main:create_app --factory --reload
```

Then open:

| URL | What |
|---|---|
| http://127.0.0.1:8000/demo | A made-up clinic website with the chat widget |
| http://127.0.0.1:8000/admin/ | The clinic dashboard (use the password from `.env`) |
| http://127.0.0.1:8000/docs | The API reference |

Add `ANTHROPIC_API_KEY` to `.env` to have Claude write the answers, and `LEADFLOW_NOTIFY_WEBHOOK_URL` to send team alerts to Slack. For dashboard development, run `npm run dev` in `frontend/` (it proxies `/api` to port 8000).

### Put the chat on a website

```html
<script src="https://YOUR-API-ADDRESS/widget.js" defer></script>
```

If the website is on a different address from the API, set `LEADFLOW_ALLOWED_ORIGINS` to it.

## How it works

```
Visitor's browser                           Server (FastAPI)
┌──────────────┐   POST /api/chat    ┌──────────────────────────────────────────┐
│ widget.js    │ ──────────────────▶ │ 1. emergency check → fixed safe reply    │
│ (one file)   │                     │ 2. BM25 search over the clinic's passages │
│              │ ◀────────────────── │ 3. Claude writes a cited answer           │
│              │  answer + sources   │    ↳ validated; any failure → offline     │
│              │                     │ 4. answer saved with its sources          │
│              │   POST /api/leads   │                                          │
│              │ ──────────────────▶ │ 5. rule-based triage → saved lead         │
└──────────────┘                     │ 6. background task → Slack, with retries  │
                                     └──────────────────────────────────────────┘
Clinic staff ── /admin (React, bearer token) ── leads · conversations · gaps · knowledge base
```

The code is small on purpose. The parts worth reading:

| File | What it does |
|---|---|
| `backend/app/assistant.py` | The Claude call: system prompt, data escaping, structured output, citation checks, fallback |
| `backend/app/retrieval.py` | Chunking and BM25 search, with no embeddings or extra services |
| `backend/app/triage.py` | Emergency detection and lead triage (whole-word matching) |
| `backend/app/notify.py` | Slack delivery: retry rules, a delivery log, no secret URLs in logs |
| `backend/app/security.py` | Admin tokens, rate limiter, client address handling |

## Configuration

All settings are environment variables; see [`backend/.env.example`](backend/.env.example). The important ones:

| Variable | Default | Purpose |
|---|---|---|
| `LEADFLOW_ADMIN_PASSWORD` | *(empty: admin off)* | Dashboard password |
| `ANTHROPIC_API_KEY` | *(empty: offline answerer)* | Enables Claude answers |
| `LEADFLOW_AI_DAILY_LIMIT` | `200` | Claude calls per day before falling back to offline |
| `LEADFLOW_NOTIFY_WEBHOOK_URL` | *(empty: alerts off)* | Slack-compatible webhook, https only |
| `DATABASE_URL` | SQLite file | Use a Postgres URL (for example Neon) for a public demo |

## Tests

```bash
cd backend && pytest -q && ruff check . && ruff format --check .
cd ../frontend && npm run build
```

51 backend tests cover retrieval, triage, the assistant (using a fake Claude client: valid and invalid citations, refusals, failures, prompt-injection escaping, the daily cap), notification retries, the API, admin access and rate limits. CI runs the same checks on every push.

## What is and isn't done

**Done and tested**
- Everything in [What it does](#what-it-does), end to end against a real running server, including real HTTP webhook delivery and the dashboard in a real browser (desktop and a 375px phone width).

**Not yet verified**
- **The live Claude call.** It is tested against a fake client that mirrors the SDK's `messages.parse` shape, and it has not yet been run against the real API. Run it once with your own key and check a few answers before you show anyone.
- **Answer quality on real clinic content.** The demo content is small. A real clinic's documents need checking, and phase 3 adds a scored test set for exactly this.

**Deliberately not in phase 1**
- Booking into a real calendar. Visitors request a time, and staff confirm by phone or email. (Google Calendar is planned.)
- Several clinics on one install, per-clinic logins, billing, email/WhatsApp/SMS channels, and conversation retention controls.

**Before using it with real patients**
- This is a demo. The assistant gives practice information, never medical advice, but you are responsible for what a real deployment says.
- Conversations and leads contain personal data, and possibly health information. Get proper advice on UK GDPR, a privacy notice, how long to keep data, and a data processing agreement with the clinic. Nothing here replaces that.
- The rate limiter is in memory (fine for one server), and the admin login is a single shared password.

## Roadmap

1. **Phase 1, now:** single clinic, grounded chat, lead capture, Slack alerts, dashboard.
2. **Phase 2:** several clinics, per-clinic login, API keys and usage caps.
3. **Phase 3:** scored accuracy test set, import content from a web page or PDF, weekly report, human handover inbox.
4. **Phase 4:** Google Calendar booking, follow-up reminders, billing, landing page.

## Free hosting for a public demo

Cloudflare Pages or GitHub Pages for any static site, Render's free web service for the API (it sleeps when idle, so the first request takes about a minute), and Neon's free Postgres for the database. Free tiers change, so check their current terms. A real clinic should not run on free tiers.
