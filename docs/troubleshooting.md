# Troubleshooting

Start with **System Health** (admin menu). It checks the database, Redis, Celery workers,
storage, FFmpeg and every integration's configuration.

| Symptom | Likely cause | Fix |
|---|---|---|
| Generation stays "Queued" forever | No Celery worker running | Start it: `celery -A config worker -l info --pool=solo` (Windows needs `--pool=solo`). |
| Scheduled posts never go out | Celery **beat** not running, or the publishing kill switch is off | Start beat (`celery -A config beat …`). Check Admin Settings → Publishing enabled. |
| `Error 10061 connecting to localhost:6379` | Redis isn't running | `docker start creativo-redis` (or run Redis). |
| Video fails: "FFmpeg is not installed" | FFmpeg missing on the worker machine | `winget install Gyan.FFmpeg`, or set `FFMPEG_BINARY` to the exe path. Restart the worker. |
| Video renders without music | Music library empty, or the track was deactivated | Upload tracks in Music Library. |
| "…API credentials are not configured" | Provider key missing in `.env` | Add the key and restart the backend and worker. Admin Settings shows which keys are set. |
| Cloudflare images fail after many generations | Free daily allowance used up | Wait for the daily reset, or switch providers in Admin Settings. |
| Instagram publish fails: "needs a public media URL" / "media could not be fetched" | Media URL not reachable from the internet | Set `BACKEND_PUBLIC_URL` (domain, or tunnel locally) or use S3/R2. See the [Meta guide](meta-setup-guide.md#part-d-make-media-reachable-for-instagram). |
| Account shows **Expired** | Token revoked, password changed, or app removed | *Social accounts → Reconnect / Continue with Facebook*. |
| "Continue with Facebook" button disabled | `META_APP_ID` / `META_APP_SECRET` not set | Set them and restart. Click "how to enable" for the steps. |
| OAuth error "redirect_uri mismatch" | Redirect URI not registered exactly | Copy the URI shown in Admin Settings → Integrations into the Meta/LinkedIn app. |
| LinkedIn shows only the personal profile | Community Management API not approved | Request it in the LinkedIn developer portal. |
| WhatsApp messages show "Skipped" | No active template for that event | Map one under WhatsApp → Templates. |
| WhatsApp messages stay "Sent" (never "Delivered") | Webhook not configured | Meta guide, Part E step 6. |
| WhatsApp shows "test mode" banner | `WHATSAPP_PROVIDER=console` | Add the Cloud API credentials and set `WHATSAPP_PROVIDER=meta`. |
| Analytics empty after publishing | Not synced yet, or the token lacks insights permission | Click **Sync now**. Check *Sync history* for the error. Reconnect with all permissions. |
| "…limit reached for this period" (403) | Plan limit hit with enforcement on | Raise the limit or upgrade the plan (Company → Subscription), or turn enforcement off. |
| Client can't see a page | Page not granted | **Access**: tick the page for that client. |
| Monthly reports not generated | Disabled, beat not running, or a different day configured | Admin Settings → Analytics & reports. Check beat is running. |
| Emails not arriving | Console email backend | Configure SMTP (`EMAIL_BACKEND=…smtp.EmailBackend` + `EMAIL_*`). |
| Times are off by 5.5 hours | Server `TIME_ZONE` is UTC | Set `TIME_ZONE=Asia/Kolkata` (and Admin Settings → timezone). |
| Docker: backend restarts in a loop | Database not ready, or bad `.env` | `docker compose logs backend`. The entrypoint waits for the database for 90 s. |
| Docker: HTTP redirects to HTTPS without a certificate | Production settings with SSL redirect | Use `SECURE_SSL_REDIRECT=False` until HTTPS is set up (default in `docker-compose.yml`). |
| `pip install` fails on the gTTS / click conflict | gTTS installed together with the rest | Install it separately: `pip install --no-deps -r requirements/no-deps.txt`. |

## Getting logs

- Local: each terminal window shows its process's logs.
- Docker: `docker compose logs -f backend worker beat web`. With `LOG_TO_FILE=True` there's
  also a rotating `app.log` in the `logs` volume.
- Production errors: Sentry, when `SENTRY_DSN` is set.
