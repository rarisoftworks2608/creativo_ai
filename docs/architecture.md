# Architecture

```
            Admin / Client (browser, desktop or phone)
                              │
                     React SPA (Vite build)
                              │  JWT over HTTPS (/api/v1)
                              ▼
   Nginx ──► Django REST API (gunicorn) ──► PostgreSQL (all business data)
                │        │
                │        └──► Media storage (local volume or S3/R2), public /media
                ▼
             Redis ◄──── Celery beat (schedules)
                │
                ▼
          Celery worker(s) ──► AI providers (text / image / voice / motion)
                │          ──► FFmpeg (video rendering)
                │          ──► Meta Graph API (Facebook, Instagram), LinkedIn API
                │          ──► WhatsApp Cloud API, SMTP
                ▼
         Analytics snapshots → Reports (PDF / Excel / CSV)
```

## Backend layout (`backend/apps/`)

| App | Responsibility |
|---|---|
| `authentication` | Email-based users (Admin / Client roles), JWT, login history, lockout, password reset, profile and notification preferences |
| `companies` | Tenants (Company), client memberships with page-level permissions, dashboard stats, job queue, media library |
| `brand` | Brand profile (identity, guidelines, marketing info) and asset library |
| `ai_strategy` | Brand context and AI strategy generation; the provider-agnostic text client lives here |
| `content_calendar` | Calendar items, Excel import/export, automation sweep, **approval workflow + review history** (`ContentReviewEvent`), approval queue |
| `creative_generation` | Image + copy variations, layout compositor, image provider clients (Cloudflare, Gemini, Hugging Face, OpenAI) |
| `video_generation` | Script → scenes → visuals → (AI motion) → voice-over → subtitles → FFmpeg render; music library, brand end card, scene editing/re-render |
| `social_accounts` | Connected accounts (encrypted tokens), OAuth for Meta + LinkedIn, token refresh and expiry checks |
| `publishing` | `PublishJob` queue, platform publishers (Facebook, Instagram, LinkedIn), scheduling, retries |
| `whatsapp` | Per-company config and notification group, template mappings, sending providers (console / Meta), delivery log, webhook |
| `analytics` | Post metrics (latest + history), daily follower snapshots, sync logs, aggregation |
| `reports` | Report builders (5 client + 6 admin types), PDF/Excel/CSV exporters, monthly automation, email/WhatsApp delivery |
| `subscriptions` | Plans, subscriptions with overrides, manual billing, usage calculation, optional limit enforcement |
| `notifications` | In-app notifications (plus email mirror), reminder tasks |
| `activity_log` | Audit trail (who, what, when, IP, old → new values) |
| `platform_settings` | Live admin settings singleton (AI provider overrides, publishing, reports, limits, …) |
| `prompt_templates` | Versioned prompt guidance injected into generation |
| `health` | Health checks, `wait_for_db`, `generate_reference_docs` |

`common/` holds cross-cutting helpers: role permissions, the company-scoping mixin, token
encryption, AI provider resolution and email helpers.

## Key design decisions

- **Multi-tenancy.** Every tenant table has a `company` FK. Company-scoped endpoints resolve
  the company from the URL through `CompanyScopedMixin`, which 404s for clients of other
  companies and for pages a client hasn't been granted.
- **Long work never runs in a request.** Generation, rendering, publishing, WhatsApp,
  analytics sync and report generation are Celery tasks. The UI polls job status.
- **Exactly-once publishing.** A job is claimed atomically (`QUEUED → PROCESSING` with a
  conditional update), so a duplicate enqueue can't double-post. Retries go back through
  the scheduler with exponential backoff, so a worker restart never loses one.
- **Replaceable AI.** Each modality has an abstract provider plus a factory.
  `common.ai_config` resolves the active provider and model (Admin Settings override →
  `.env`).
- **Secrets.** Social and OAuth tokens are Fernet-encrypted at rest and never returned by
  the API (masked preview only). The OAuth `state` is signed and bound to the company and
  admin.
- **Graceful degradation.** A missing API key, FFmpeg, AI motion credit or public media URL
  fails the specific job with a clear message (or falls back, for example AI motion →
  zoom/pan) instead of breaking the workflow.
- **Auditability.** Every important action writes an `ActivityLog` row. The content
  lifecycle also writes `ContentReviewEvent`s.

## Content lifecycle

```
Calendar item (draft/scheduled)
   │  beat sweep every 15 min, or "Generate now"   (quota checked)
   ▼
GENERATING ──► creative variations / rendered video ──► PENDING_APPROVAL
   │                                         (client + WhatsApp notified, reminder after N hours)
   ├── Approve (variation locked in) ──► APPROVED ──► [auto-schedule if enabled]
   │                                                   PublishJob per account (SCHEDULED)
   │                                                   beat every minute ──► QUEUED ──► PROCESSING
   │                                                   ──► PUBLISHED (item PUBLISHED) / retry / FAILED
   └── Request changes ──► REJECTED ──► one automatic regeneration ──► PENDING_APPROVAL
                                         (second rejection → manual revision by the team)
Published posts ──► analytics sync (interval) ──► dashboards ──► monthly report (day N) ──► email + WhatsApp
```

## Scheduled jobs (Celery beat)

| Job | Schedule |
|---|---|
| Auto-generate due content | every 15 min |
| Dispatch due publish jobs (+ recover stuck ones) | every minute |
| Approval reminders | hourly |
| Draft-content reminders to admins | daily 09:00 |
| Analytics sync (respects the interval setting) | hourly |
| Follower snapshots | daily 02:30 |
| Monthly reports (on the configured day) | daily 06:00 |
| Subscription expiry / renewal reminders / overdue invoices | daily 07:00 |
| Storage usage recalculation | daily 04:00 |
| Social token refresh / expiry checks | daily 03:00 / 08:00 |
