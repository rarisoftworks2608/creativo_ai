# Creativo AI: AI Marketing Automation Platform

A multi-tenant SaaS platform that runs an agency's whole content lifecycle for its client
companies: brand profile → AI content strategy → monthly content calendar → AI creatives
and videos → client approval (with one AI regeneration) → publishing to Instagram,
Facebook and LinkedIn → analytics → monthly reports, with WhatsApp notifications and
manually managed subscriptions.

| | |
|---|---|
| **Backend** | Python 3.12 · Django 5 · Django REST Framework · PostgreSQL · Celery + Redis · FFmpeg |
| **Frontend** | React 19 · Vite · React Router (responsive, light and dark mode) |
| **AI** | Provider-agnostic: Anthropic / Groq / OpenAI (text), Cloudflare / Gemini / Hugging Face / OpenAI (images), gTTS voice-over, Hugging Face / Replicate motion |
| **Integrations** | Meta Graph API (Facebook Pages, Instagram), LinkedIn REST API, WhatsApp Business Cloud API, SMTP, S3/R2 |
| **DevOps** | Docker · Docker Compose · Nginx + Let's Encrypt · GitHub Actions · Sentry |

## Modules

| Epic | Module | Where |
|---|---|---|
| 01 | Authentication & users, JWT, roles, page-level access control | Team, Access |
| 02–03 | Companies, clients, onboarding, brand management | Companies → Brand |
| 04 | Content calendar with Excel import | Company → Calendar |
| 05 | AI content strategy | Company → Strategy |
| 06 | AI creative generation (3 variations, brand-aware layout) | Company → Creatives |
| 07 | AI video generation: script, scenes, voice-over, subtitles, music, brand end card, scene editing and re-render | Company → Videos, Music Library |
| 08 | Media library, S3/R2 storage | Company → Media |
| 09 | Content approval workflow: approve or request changes, one automatic regeneration, full history, reminders | Approvals |
| 10 | Social accounts: OAuth for Facebook/Instagram/LinkedIn, Page/organization picker, token refresh | Company → Social accounts |
| 11 | Publishing & scheduling: publish now / schedule, multi-platform, queue, retries, history | Publishing |
| 12 | WhatsApp automation: notification group, templates, delivery log, webhook | Company → WhatsApp, WhatsApp |
| 13–14 | Notification center, admin and client dashboards | Bell, Dashboard |
| 15 | Analytics: reach, engagement, top posts, best platform and content type, follower growth | Analytics |
| 16 | Reports: monthly and on-demand, PDF / Excel / CSV, emailed and sent on WhatsApp | Reports |
| 17 | Subscriptions & usage: plans, limits, usage meters, manual billing | Subscriptions |
| 18–21 | Activity log, admin settings, client settings, prompt library | System menu |
| 22–25 | Automation engine, background jobs, security, multi-tenancy | Jobs, System health |
| 26–28 | DevOps, tests, documentation | this repo |

## Quick start: local development (Windows)

Prerequisites: Python 3.12, Node 22, PostgreSQL (or Docker), Redis (Docker is easiest) and
FFmpeg for video rendering (`winget install Gyan.FFmpeg`).

```powershell
# 1. Backend
cd backend
py -3.12 -m venv venv
.\venv\Scripts\python -m pip install -r requirements\development.txt
.\venv\Scripts\python -m pip install --no-deps -r requirements\no-deps.txt
copy .env.example .env          # then edit DATABASE_URL, SECRET_KEY, API keys
.\venv\Scripts\python manage.py migrate
.\venv\Scripts\python manage.py createsuperuser

# 2. Frontend
cd ..\frontend
npm install
copy .env.example .env

# 3. Run everything (Redis container + API + worker + beat + Vite, each in its own window)
cd ..
powershell -ExecutionPolicy Bypass -File scripts\dev.ps1
```

Then open <http://localhost:5173>. The API docs are at <http://127.0.0.1:8000/api/docs/>.

Prefer to run the processes yourself? See [docs/environment-setup.md](docs/environment-setup.md#run-the-four-processes).
Need PostgreSQL and Redis without installing them? Run `docker compose -f docker-compose.dev.yml up -d`.

## Quick start: everything in Docker

```bash
cp backend/.env.example backend/.env   # set SECRET_KEY + API keys
docker compose up -d --build
docker compose exec backend python manage.py createsuperuser
```

Open <http://localhost>. For production with HTTPS see [docs/deployment.md](docs/deployment.md).

## Documentation

| Document | For |
|---|---|
| [Environment setup](docs/environment-setup.md) | Local development and every environment variable |
| [Deployment](docs/deployment.md) | Docker Compose production, SSL, backups, monitoring, upgrades |
| [Architecture](docs/architecture.md) | How the pieces fit together |
| [API reference](docs/api.md) | Every endpoint (interactive version at `/api/docs/`) |
| [Database reference](docs/database.md) | Every table and field |
| [Meta setup guide](docs/meta-setup-guide.md) | **Facebook / Instagram auto-posting and WhatsApp** |
| [LinkedIn setup guide](docs/linkedin-setup-guide.md) | LinkedIn Company Page posting |
| [Admin guide](docs/admin-guide.md) | Day-to-day use for the agency team |
| [Client guide](docs/client-guide.md) | What clients see and do |
| [FAQ](docs/faq.md) · [Troubleshooting](docs/troubleshooting.md) | Common questions and fixes |
| [Contributing](CONTRIBUTING.md) | Branching, tests, pull requests |
| [Product plan](project_plan.md) | Epics, sprint plan, status |

## Tests

```bash
cd backend && python manage.py test        # needs PostgreSQL (or set DATABASE_URL to SQLite)
cd frontend && npm run lint && npm run build
```

CI (`.github/workflows/ci.yml`) runs both, plus migration and deployment checks, on every
push and pull request.
