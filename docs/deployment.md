# Deployment

The recommended production setup is **one Linux server running Docker Compose**: PostgreSQL,
Redis, the Django API (gunicorn), a Celery worker, Celery beat, and Nginx serving the React
app, proxying the API and terminating HTTPS. A 2 vCPU / 4 GB server is enough to start.
Video rendering is the heaviest job.

## 1. Server preparation

```bash
# Ubuntu 22.04/24.04
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER        # log out/in afterwards
git clone <your-repo-url> /srv/creativo_ai && cd /srv/creativo_ai
```

Point your domain's DNS **A record** (for example `app.yourdomain.com`) at the server, and
open ports 80 and 443.

## 2. Configuration

```bash
cp backend/.env.example backend/.env
```

Set at least the following in `backend/.env`:

```
SECRET_KEY=<long random string>
SOCIAL_TOKEN_ENCRYPTION_KEY=<another long random string>
TIME_ZONE=Asia/Kolkata
FRONTEND_URL=https://app.yourdomain.com
BACKEND_PUBLIC_URL=https://app.yourdomain.com
CORS_ALLOWED_ORIGINS=https://app.yourdomain.com
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend   # + EMAIL_* settings
# AI keys, META_*, LINKEDIN_*, WHATSAPP_* as you obtain them
```

`DATABASE_URL` and `REDIS_URL` are set by Compose; don't put them in `.env` for Docker.

Create a root `.env` next to `docker-compose.yml` for Compose itself:

```
DOMAIN=app.yourdomain.com
LETSENCRYPT_EMAIL=you@yourdomain.com
ALLOWED_HOSTS=app.yourdomain.com
CSRF_TRUSTED_ORIGINS=https://app.yourdomain.com
POSTGRES_PASSWORD=<strong password>
DJANGO_SUPERUSER_EMAIL=admin@yourdomain.com      # first admin login, created on first start
DJANGO_SUPERUSER_PASSWORD=<strong password>
```

## 3. First start with HTTPS

```bash
chmod +x scripts/*.sh
./scripts/init-letsencrypt.sh          # obtains the certificate, then starts the full stack
```

From then on:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

Certificates renew automatically: the `certbot` service checks twice a day.

**Without HTTPS** (internal testing, or another proxy such as Cloudflare in front): run
`docker compose up -d --build` and open `http://server-ip`.

## 4. What runs where

| Service | Image | Role |
|---|---|---|
| `db` | postgres:16 | data (volume `postgres_data`) |
| `redis` | redis:7 | Celery broker (volume `redis_data`) |
| `backend` | `./backend` | gunicorn + Django; runs migrations on start (`RUN_MIGRATIONS=1`) |
| `worker` | `./backend` | Celery worker: AI generation, video rendering, publishing, WhatsApp, reports, analytics |
| `beat` | `./backend` | Celery beat: every-minute publishing dispatch, reminders, analytics sync, monthly reports, subscription checks |
| `web` | `./frontend` | Nginx: React app, `/api` and `/admin` proxy, `/static`, public `/media` |
| `certbot` | certbot | certificate renewals (prod override only) |
| `flower` | mher/flower | optional Celery dashboard: `docker compose --profile monitoring up -d flower` |

Media lives in the `media` volume, or in S3/R2 when `USE_S3_STORAGE=True`. `/media/` must
stay publicly readable, because Instagram and WhatsApp download post media from it.

## 5. Operations

| Task | Command |
|---|---|
| Logs | `docker compose logs -f backend worker beat` (plus `logs` volume → `app.log`) |
| Django shell | `docker compose exec backend python manage.py shell` |
| Create an admin | `docker compose exec backend python manage.py createsuperuser` |
| Health | `curl https://app.yourdomain.com/api/v1/health/`; admins see full detail on **System health** |
| Scale workers | `docker compose up -d --scale worker=3` |
| Upgrade | `git pull && docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build` (migrations run automatically) |

## 6. Backups and disaster recovery

```bash
./scripts/backup.sh                       # backups/db-*.sql.gz + backups/media-*.tar.gz, keeps 14 days
crontab -e   →   0 2 * * * cd /srv/creativo_ai && ./scripts/backup.sh >> backups/backup.log 2>&1
./scripts/restore.sh backups/db-20261001-0200.sql.gz backups/media-20261001-0200.tar.gz
```

Copy `backups/` off the server regularly, for example with `rclone` to S3, R2 or Google
Drive. If you use S3/R2 for media, enable bucket versioning instead of archiving media.

**Recovery drill:**

1. Provision a new server.
2. Clone the repo and restore both `.env` files.
3. `docker compose up -d db`
4. Run `./scripts/restore.sh` with the latest backups.
5. `docker compose ... up -d`

## 7. Monitoring

- **Errors:** set `SENTRY_DSN` (Django and Celery are instrumented).
- **Uptime:** point an uptime monitor (UptimeRobot, Better Stack, …) at `/api/v1/health/`.
- **Celery:** the optional Flower dashboard, or the platform's own **Jobs** page (failed and
  queued jobs across generation, publishing, reports and analytics).
- **Logs:** set `LOG_TO_FILE=True` for a rotating `app.log` in the `logs` volume.

## 8. Without Docker

You can also run the stack the traditional way:

- gunicorn behind Nginx.
- Celery worker and beat as systemd services.
- The built frontend (`npm run build` → `frontend/dist`) served by Nginx with
  `try_files $uri /index.html`.

Mirror the locations in `frontend/nginx.conf`, run `python manage.py collectstatic` and
`migrate` on each deploy, and install FFmpeg on the worker machine.

## Branching and release flow

`feature/*` → pull request into `develop` (CI must pass) → test on staging → merge
`develop` into `main` → deploy. See [CONTRIBUTING.md](../CONTRIBUTING.md).
