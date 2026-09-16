# Grievance Desk — AI Ticketing & Webmail Monitoring Platform

An enterprise grievance ticketing system with automatic intent classification, SLA
breach sentinel, WhatsApp/email webhook intake, voice commands, and real outbound SMTP
receipts.

## Tech Stack

- **Frontend:** React 19 + Vite 6 (JavaScript), Tailwind CSS v4, Recharts, lucide-react
- **Backend:** FastAPI (Python 3.12), SQLAlchemy 2 async + asyncpg
- **Database:** PostgreSQL 16
- **AI:** Google Gemini (`gemini-2.5-flash`) with a rule-based keyword fallback when no key is set
- **Auth:** JWT (server-issued, cached in `localStorage`)
- **Deployment:** Docker Compose (Postgres + FastAPI + nginx-served frontend)

> No Firebase. Inbound IMAP polling is simulated; outbound customer receipts use real SMTP.

## Project Layout

```
backend/            FastAPI application (app/, requirements.txt, Dockerfile, .env.example)
frontend/           React + Vite SPA (src/, index.html, vite.config.js, Dockerfile, nginx.conf)
docker-compose.yml  Orchestrates db + backend + frontend
```

## Quick Start (Docker Compose)

Prerequisites: Docker with Compose v2.

```bash
# 1. (Optional) Configure secrets
cp backend/.env.example backend/.env
#    fill in GEMINI_API_KEY and SMTP_* as needed

# 2. Build and start everything (Postgres, API, frontend)
docker compose up --build

# 3. Open the app
#    Frontend:   http://localhost:8080
#    Backend API: http://localhost:8000/api/health
```

Compose passes host environment variables into the backend; the same names as
`backend/.env.example` (e.g. `GEMINI_API_KEY`, `SMTP_HOST`, `SMTP_USERNAME`,
`SMTP_PASSWORD`, `SMTP_FROM_EMAIL`). A `backend/.env` file overrides Compose defaults
when also referenced via an env file directive — for most setups the Compose
environment mapping above is enough.

## Local Development

**Backend** (needs PostgreSQL running locally):

```bash
cd backend
cp .env.example .env        # edit DATABASE_URL to point at your local Postgres
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

The server runs Alembic migrations (`alembic upgrade head`) and seeds a default admin +
demo tickets on startup (`/api/health` confirms it is up). To make a schema change: edit
`app/models.py`, then from `backend/` run:

```bash
alembic revision --autogenerate -m "describe the change"
alembic upgrade head   # or just restart the app — it runs this automatically
```

**Frontend:**

```bash
cd frontend
npm install
npm run dev                 # http://localhost:5173
```

`vite.config.js` proxies `/api` to `http://localhost:8000`, so the SPA and backend
share the same origin during development.

## Testing

```bash
cd backend
pip install -r requirements-dev.txt
pytest
```

Runs against a throwaway SQLite database (no Postgres needed) — covers the full complaint
pipeline (register org → AI classify → Complaint ID → assign → status/escalate → notify),
Alembic migrations (including the upgrade path from a pre-Alembic database), the
business-hours SLA calendar, mail-loop/bounce detection, and the notification retry queue.

## Default Admin Account

| Field | Value |
|---|---|
| User ID / Email | `Fillip` (or `fillip.admin@grievancedesk.org`) |
| Password | `Admin_123$$` |

Other users can self-register from the sign-up screen (role `User`).

## Configuration (`.env`)

All variables are UI-configurable where relevant. Key ones:

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | asyncpg connection string |
| `JWT_SECRET` | Signing secret for access tokens (change in prod) |
| `GEMINI_API_KEY` / `GEMINI_MODEL` | AI classifier/voice; empty → rule fallback |
| `SMTP_HOST/PORT/USERNAME/PASSWORD/FROM_EMAIL` | Real outbound receipts; empty → in-app only |
| `CORS_ORIGINS` | Comma-separated allowed origins |
| `FRONTEND_URL` | Public SPA URL; used to build "Open Ticket" deep links (`?ticket=ID`) inside notification emails |
| `WHATSAPP_ACCESS_TOKEN` / `WHATSAPP_PHONE_NUMBER_ID` | Meta WhatsApp Cloud API; empty → outbound WhatsApp sends are skipped (inbound intake still works) |
| `WHATSAPP_APP_SECRET` | Verifies Meta's inbound webhook signature; strongly recommended once a real number is connected |

## Feature Highlights

- **AI intake classification** — categorizes inbound messages into `Support` / `Enquiry` with a confidence score; auto-creates a ticket and (if configured) sends an SMTP receipt.
- **Mail-loop protection** — inbound IMAP polling skips auto-replies, bounces/DSNs, and mail from the mailbox's own address so acknowledgement emails can't spawn duplicate tickets.
- **Needs-Attention queue** — tickets the pipeline couldn't fully notify on (missing contact email, a failed send, an escalation with no authority configured) are flagged with a reason and surfaced to the OrgAdmin in a dashboard banner and on the ticket itself (`GET /tickets?needsAttention=true`).
- **Deep-linked notification emails** — resolver/authority/customer emails link straight to the ticket in the app instead of a bare "log in and search" instruction.
- **WhatsApp outbound (Meta Cloud API)** — registered/resolved/escalated notices are sent back to WhatsApp complainants, not just built and discarded; the real inbound webhook verifies Meta's `X-Hub-Signature-256` once an App Secret is configured.
- **Google Forms integration** — Org Settings generates a per-org Apps Script (`onFormSubmit` trigger) that posts clean, labeled form answers straight to the intake webhook — more reliable than parsing the "new submission" notification email.
- **WhatsApp Business Intake** — real inbound messages via Meta's Cloud API webhook are classified and turned into tickets the same way as email.
- **Multi-Mailbox Management** — connect webmail accounts (IMAP/SMTP/CPanel); test SMTP handshake and dispatch test receipts.
- **SLA Breach Sentinel** — 48h/6h (Support/Enquiry) windows by default, configurable per org; breach detection and escalation status.
- **Business-hours SLA calendar** — optional, per-org: SLA due dates only accumulate during configured business days/hours in a chosen timezone, skipping holidays, so a Friday-evening complaint doesn't breach over the weekend.
- **SLA clock pause** — a resolver can mark a ticket "Awaiting Customer" to pause breach/escalation checks while blocked on the customer; resuming extends the due date by the paused duration instead of losing that time.
- **Pre-breach SLA warnings** — the assigned resolver gets a one-time email once a ticket crosses 80% of its SLA window, before it breaches.
- **Escalation ladder readiness check** — Team Management flags when there's no active Resolver or no Tier-1 Escalation Authority configured, before it becomes a silent gap.
- **Setup Readiness Checklist** — on the Dashboard, checks SMTP/AI/Resolver/mailbox setup against real org state and links straight to what's missing, plus a one-click path to send a real end-to-end test complaint.
- **Notification retry queue** — a transient email/WhatsApp send failure (timeout, rate-limit) is retried automatically with exponential backoff instead of being a one-shot attempt; permanent failures (bad config) are surfaced, not retried.
- **Multi-replica safe** — mailbox polling, SLA escalation, and notification retries take a Postgres advisory lock, so running more than one backend container never double-sends.
- **Public complaint tracking** — complainants check status themselves at `/track` with their Complaint ID + the email/mobile they filed with, seeing status, SLA/escalation state, and the reply thread — no login, no "any update?" email needed.
- **AI-suggested replies** — a resolver can draft a reply with one click (Gemini, or a usable fallback template with no key configured); always shown for review/edit before sending, never auto-sent.
- **Workload-aware assignment** — round robin now narrows to whichever active Resolver(s) currently carry the fewest open tickets before rotating, instead of blindly cycling regardless of who's already overloaded.
- **Low-confidence review flag** — a classification below 60% confidence doesn't silently drive routing/SLA as if it were certain; the ticket is still created and assigned (never blocked), but flagged for a human to verify the category.
- **Analytics** — Recharts dashboards for volume, category, status, and channel.
- **AI Voice Commands** — Hindi/Hinglish/English; backend Gemini interpretation with a local rule fallback.

## API Endpoints (prefix `/api`)

- `POST /auth/register`, `POST /auth/login`, `GET /auth/me`
- `GET /tickets` (filters: `search`, `tstatus`, `category`, `sla`, `needsAttention`), `POST /tickets/seed`, `POST /tickets/{id}/status`, `POST /tickets/{id}/replies`, `POST /tickets/{id}/awaiting-customer`, `POST /tickets/{id}/suggest-reply`
- `GET|PUT /settings`, `GET|PUT /settings/api-key`, `POST /settings/verify-key`
- `POST /webhook/external/{api_key}/intake` — real intake endpoint for external integrations (website forms, Zapier/CRM webhooks, Google Forms Apps Script)
- `GET|POST /webhook/external/{api_key}/whatsapp` — Meta/Twilio WhatsApp webhook (verification handshake + inbound messages)
- `POST /smtp/verify`, `POST /smtp/send-receipt`
- `POST /whatsapp/send-test`
- `POST /ai-voice-command`, `GET /health`
- `POST /public/track` — unauthenticated; Complaint ID + email/mobile → status (backs the `/track` page)
- Mailboxes: `GET|POST /mailboxes` (and delete / status / test-receipt)