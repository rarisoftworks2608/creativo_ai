# Environment setup

## Prerequisites

| Tool | Version | Notes |
|---|---|---|
| Python | 3.12 | `py -3.12` on Windows |
| Node.js | 22 (≥ 20.19) | for the Vite frontend |
| PostgreSQL | 14+ | or `docker compose -f docker-compose.dev.yml up -d` (Postgres on port 5433) |
| Redis | 7 | Celery broker. Docker: `docker run -d --name creativo-redis -p 6379:6379 redis:7-alpine` |
| FFmpeg | any recent | video rendering. Windows: `winget install Gyan.FFmpeg`; macOS: `brew install ffmpeg`; Linux: `apt install ffmpeg`. Or set `FFMPEG_BINARY` to its full path. |

## Backend

```powershell
cd backend
py -3.12 -m venv venv
.\venv\Scripts\python -m pip install -r requirements\development.txt
# gTTS is installed separately because its pinned "click" version conflicts with
# huggingface_hub's (it only uses click for its own CLI, which this project never calls):
.\venv\Scripts\python -m pip install --no-deps -r requirements\no-deps.txt
copy .env.example .env
.\venv\Scripts\python manage.py migrate
.\venv\Scripts\python manage.py createsuperuser
```

On macOS/Linux use `python3.12 -m venv venv` and `venv/bin/python`.

## Frontend

```bash
cd frontend
npm install
cp .env.example .env    # VITE_API_URL=http://localhost:8000/api/v1
```

## Run the four processes

Everything at once on Windows: `powershell -ExecutionPolicy Bypass -File scripts\dev.ps1`.

Or run one terminal per process, from the repo root:

| # | Process | Command |
|---|---|---|
| 1 | Django API (http://127.0.0.1:8000) | `cd backend; .\venv\Scripts\python manage.py runserver` |
| 2 | Celery worker (AI generation, rendering, publishing, WhatsApp, reports) | `cd backend; .\venv\Scripts\celery -A config worker -l info --pool=solo` |
| 3 | Celery beat (scheduled publishing, reminders, analytics sync, monthly reports) | `cd backend; .\venv\Scripts\celery -A config beat -l info -s "$env:TEMP\creativo-celerybeat-schedule"` |
| 4 | Frontend (http://localhost:5173) | `cd frontend; npm run dev` |

- `--pool=solo` is required on Windows.
- `-s` keeps beat's schedule file out of the repo.
- Without the worker and beat, the app still opens, but generation, publishing and every
  scheduled job stand still.

## Environment variables (`backend/.env`)

Only `SECRET_KEY` and `DATABASE_URL` are needed to start. Everything else switches a
feature on.

### Core

| Variable | Default | Description |
|---|---|---|
| `SECRET_KEY` | insecure dev key | Django secret. Use a long random value in production. |
| `DEBUG` | `False` | `True` locally (development settings set it automatically). |
| `ALLOWED_HOSTS` | | Comma-separated hostnames (production). |
| `CSRF_TRUSTED_ORIGINS` | | `https://app.yourdomain.com` (production). |
| `TIME_ZONE` | `UTC` | Server timezone, for example `Asia/Kolkata`. Calendar times are interpreted in it. |
| `DATABASE_URL` | SQLite file | `postgres://user:pass@host:5432/dbname` |
| `REDIS_URL` | `redis://localhost:6379/0` | Celery broker and results. |
| `CORS_ALLOWED_ORIGINS` | localhost:5173 | Frontend origins allowed to call the API. |
| `FRONTEND_URL` | `http://localhost:5173` | Used in email links, WhatsApp links and OAuth redirects. |
| `ACCESS_TOKEN_LIFETIME_MINUTES` / `REFRESH_TOKEN_LIFETIME_DAYS` | 30 / 7 | JWT lifetimes. |
| `SOCIAL_TOKEN_ENCRYPTION_KEY` | `SECRET_KEY` | Key that encrypts stored social and OAuth tokens. Set it separately in production. |

### Email

| Variable | Description |
|---|---|
| `EMAIL_BACKEND` | `django.core.mail.backends.smtp.EmailBackend` for real delivery (console by default) |
| `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_USE_TLS`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `DEFAULT_FROM_EMAIL` | SMTP provider settings |
| `SEND_NOTIFICATION_EMAILS` | Seed value for Admin Settings → "Send notification emails" |

### AI providers

Providers and models can also be switched at runtime in **Admin Settings → AI providers**.
Keys always stay in `.env`.

| Variable | Description |
|---|---|
| `AI_TEXT_PROVIDER` / `AI_TEXT_MODEL` | `anthropic` (`ANTHROPIC_API_KEY`), `groq` (`GROQ_API_KEY`), `openai` (`OPENAI_API_KEY`) |
| `AI_IMAGE_PROVIDER` / `AI_IMAGE_MODEL` | `cloudflare` (`CF_ACCOUNT_ID` + `CF_API_TOKEN`, free daily allowance), `gemini` (`GEMINI_API_KEY`), `huggingface` (`HF_TOKEN`), `openai` (`OPENAI_API_KEY`, model `gpt-image-1`) |
| `OPENAI_IMAGE_SIZE` / `OPENAI_IMAGE_QUALITY` | `1024x1536` / `medium` |
| `AI_IMAGE_COST_PER_IMAGE_USD` | Optional per-image cost for usage and cost tracking |
| `AI_VOICE_PROVIDER` | `gtts` (free, no key) |
| `AI_VIDEO_PROVIDER` / `AI_VIDEO_MODEL` | `huggingface` (free monthly credit) or `replicate` (`REPLICATE_API_TOKEN`). Falls back to zoom/pan animation when unavailable. |
| `FFMPEG_BINARY`, `VIDEO_CRF`, `VIDEO_PRESET` | Rendering binary path and H.264 quality/speed (23 / `veryfast`) |

**Switching image generation to OpenAI later** takes either step below; nothing else
changes:

- Set `OPENAI_API_KEY`, `AI_IMAGE_PROVIDER=openai` and `AI_IMAGE_MODEL=gpt-image-1`, then
  restart.
- Or add `OPENAI_API_KEY` and pick *openai* under Admin Settings → AI providers.

### Publishing, social OAuth and WhatsApp

See [meta-setup-guide.md](meta-setup-guide.md) and [linkedin-setup-guide.md](linkedin-setup-guide.md).

| Variable | Description |
|---|---|
| `BACKEND_PUBLIC_URL` | Public URL of the backend. Instagram and WhatsApp download media from it. In local development use a tunnel URL. |
| `PUBLIC_MEDIA_BASE_URL` | Optional: public base URL that serves the media folder (bucket/CDN) |
| `META_APP_ID`, `META_APP_SECRET`, `META_LOGIN_CONFIG_ID`, `META_GRAPH_API_VERSION` | Facebook / Instagram OAuth and publishing |
| `LINKEDIN_CLIENT_ID`, `LINKEDIN_CLIENT_SECRET`, `LINKEDIN_API_VERSION` | LinkedIn OAuth and publishing |
| `SOCIAL_OAUTH_REDIRECT_BASE` | Where providers redirect back to (defaults to `FRONTEND_URL`) |
| `WHATSAPP_PROVIDER` | `console` (log only) or `meta` |
| `WHATSAPP_ACCESS_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_BUSINESS_ACCOUNT_ID`, `WHATSAPP_API_VERSION` | WhatsApp Cloud API |
| `WHATSAPP_WEBHOOK_VERIFY_TOKEN`, `WHATSAPP_APP_SECRET` | Delivery-receipt webhook |

### Storage and monitoring

| Variable | Description |
|---|---|
| `USE_S3_STORAGE` | `True` to store media in S3 or Cloudflare R2 |
| `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_STORAGE_BUCKET_NAME`, `AWS_S3_ENDPOINT_URL`, `AWS_S3_REGION_NAME`, `AWS_S3_CUSTOM_DOMAIN` | Bucket settings (R2 endpoint: `https://<account>.r2.cloudflarestorage.com`) |
| `LOG_LEVEL`, `LOG_TO_FILE`, `LOG_DIR` | Application logs (rotating `logs/app.log` when enabled) |
| `SENTRY_DSN` | Error tracking in production and staging |

## Frontend variables (`frontend/.env`)

| Variable | Description |
|---|---|
| `VITE_API_URL` | `http://localhost:8000/api/v1` locally; `/api/v1` behind the bundled Nginx |

## Useful commands

```bash
python manage.py test                       # backend tests
python manage.py generate_reference_docs    # refresh docs/api.md + docs/database.md
python manage.py spectacular --file schema.yml --validate   # OpenAPI schema
python manage.py wait_for_db                # used by Docker start-up
npm run lint && npm run build               # frontend checks
```
