"""
Base Django settings shared by every environment.

Environment-specific files (development.py / staging.py / production.py)
import everything from this module with `from .base import *` and then
override what differs for that environment.
"""

import sys
from datetime import timedelta
from pathlib import Path

import environ
from celery.schedules import crontab

# backend/config/settings/base.py -> backend/
BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env(
    DEBUG=(bool, False),
)

# Read backend/.env if present. Real deployments should set real
# environment variables instead of shipping a .env file.
env_file = BASE_DIR / '.env'
if env_file.exists():
    environ.Env.read_env(env_file)

SECRET_KEY = env('SECRET_KEY', default='django-insecure-change-me-in-env-file')

# Epic 10: Social Media Account Management - key used to encrypt stored social
# access tokens (common/crypto.py). Falls back to SECRET_KEY so no new env var
# is required in development; production should set this independently so
# rotating SECRET_KEY doesn't also break decryption of every stored token.
SOCIAL_TOKEN_ENCRYPTION_KEY = env('SOCIAL_TOKEN_ENCRYPTION_KEY', default='')

DEBUG = env.bool('DEBUG', default=False)

ALLOWED_HOSTS = env.list('ALLOWED_HOSTS', default=[])


# Application definition

DJANGO_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

THIRD_PARTY_APPS = [
    'rest_framework',
    'rest_framework_simplejwt.token_blacklist',
    'corsheaders',
    'drf_spectacular',
]

LOCAL_APPS = [
    'apps.authentication',
    'apps.companies',
    'apps.content_calendar',
    'apps.brand',
    'apps.ai_strategy',
    'apps.creative_generation',
    'apps.video_generation',
    'apps.notifications',
    'apps.social_accounts',
    'apps.activity_log',
    'apps.platform_settings',
    'apps.prompt_templates',
    'apps.publishing',
    'apps.whatsapp',
    'apps.analytics',
    'apps.subscriptions',
    'apps.reports',
    'apps.health',
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'
ASGI_APPLICATION = 'config.asgi.application'


# Database
# https://docs.djangoproject.com/en/5.0/ref/settings/#databases

DATABASE_URL = env('DATABASE_URL', default='') or f'sqlite:///{BASE_DIR / "db.sqlite3"}'

DATABASES = {
    'default': env.db_url_config(DATABASE_URL)
}


# Custom user model

AUTH_USER_MODEL = 'authentication.User'


# Password validation
# https://docs.djangoproject.com/en/5.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {'min_length': 8},
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/5.0/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = env('TIME_ZONE', default='UTC')

USE_I18N = True

USE_TZ = True


# Static & media files

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# Django REST Framework

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    # Epic 24 (Security: Rate limiting) - a blanket per-IP/per-user ceiling on every
    # endpoint, plus a much tighter 'login'/'password_reset' scope applied only to
    # those two views (see authentication/views.py) since brute-forcing credentials
    # is the attack that actually matters here, not normal API traffic.
    'DEFAULT_THROTTLE_CLASSES': (
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ),
    'DEFAULT_THROTTLE_RATES': {
        'anon': env('THROTTLE_RATE_ANON', default='100/min'),
        'user': env('THROTTLE_RATE_USER', default='300/min'),
        'login': env('THROTTLE_RATE_LOGIN', default='10/min'),
        'password_reset': env('THROTTLE_RATE_PASSWORD_RESET', default='5/min'),
    },
}

if 'test' in sys.argv:
    # Throttle counters live in the cache, not the DB, so they survive across
    # test methods/files within one test run (TestCase only rolls back the DB).
    # Real apps' test suites log in far more often per minute than a real user
    # ever would, so a real-world rate limit would make the suite order-dependent
    # and flaky rather than actually testing anything - the login-lockout feature
    # itself (tests.authentication.test_login_lockout) is unrelated to this and
    # is unaffected, since it's plain DB-backed logic, not cache-based throttling.
    REST_FRAMEWORK['DEFAULT_THROTTLE_RATES'] = {
        'anon': '100000/min', 'user': '100000/min', 'login': '100000/min', 'password_reset': '100000/min',
    }


# Simple JWT
# https://django-rest-framework-simplejwt.readthedocs.io/

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=env.int('ACCESS_TOKEN_LIFETIME_MINUTES', default=30)),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=env.int('REFRESH_TOKEN_LIFETIME_DAYS', default=7)),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': True,
    'AUTH_HEADER_TYPES': ('Bearer',),
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
}


# drf-spectacular (OpenAPI schema / docs)

SPECTACULAR_SETTINGS = {
    'TITLE': 'AI Marketing Automation Platform API',
    'DESCRIPTION': 'API documentation for the AI digital marketing automation SaaS platform.',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
}


# CORS
# https://github.com/adamchainz/django-cors-headers

CORS_ALLOWED_ORIGINS = env.list('CORS_ALLOWED_ORIGINS', default=[])
CORS_ALLOW_CREDENTIALS = True


# Email
# Defaults to the console backend so password-reset emails are visible
# in the server log until a real provider is configured per environment.

EMAIL_BACKEND = env('EMAIL_BACKEND', default='django.core.mail.backends.console.EmailBackend')
DEFAULT_FROM_EMAIL = env('DEFAULT_FROM_EMAIL', default='no-reply@example.com')
EMAIL_HOST = env('EMAIL_HOST', default='')
EMAIL_PORT = env.int('EMAIL_PORT', default=587)
EMAIL_HOST_USER = env('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = env('EMAIL_HOST_PASSWORD', default='')
EMAIL_USE_TLS = env.bool('EMAIL_USE_TLS', default=True)

# Base URL of the frontend app, used to build links inside emails
# (e.g. password reset links).
FRONTEND_URL = env('FRONTEND_URL', default='http://localhost:5173')

# Epic 13: Notification Center - Email. Off by default so notifications don't
# start emailing real inboxes (EMAIL_HOST/EMAIL_HOST_PASSWORD above may already
# be pointed at a live SMTP provider) until explicitly turned on per environment.
SEND_NOTIFICATION_EMAILS = env.bool('SEND_NOTIFICATION_EMAILS', default=False)


# AI text provider (Epic 05: AI Content Strategy)
# 'anthropic' reads ANTHROPIC_API_KEY / 'groq' reads GROQ_API_KEY - both read
# directly by their own SDK from the environment (set it in .env), not
# duplicated here. AI_TEXT_MODEL must match whichever provider is active
# (e.g. claude-opus-5 for anthropic, openai/gpt-oss-120b for groq).

AI_TEXT_PROVIDER = env('AI_TEXT_PROVIDER', default='anthropic')
AI_TEXT_MODEL = env('AI_TEXT_MODEL', default='claude-opus-5')


# AI image provider (Epic 06: AI Creative Generation)
# 'gemini' reads GEMINI_API_KEY, read directly by the google-genai SDK from
# the environment (set it in .env) - deliberately not duplicated here.
# 'huggingface' reads HF_TOKEN (free to create, no card required) and runs
# on Hugging Face's own serverless compute (see HuggingFaceImageProvider).
# 'cloudflare' reads CF_ACCOUNT_ID + CF_API_TOKEN and runs FLUX.1 [schnell]
# on Cloudflare Workers AI - free (10,000 Neurons/day, resets daily, see
# CloudflareImageProvider). AI_IMAGE_MODEL must match whichever provider is
# active (e.g. gemini-3.1-flash-image for gemini,
# stabilityai/stable-diffusion-3-medium-diffusers for huggingface,
# @cf/black-forest-labs/flux-1-schnell for cloudflare).

AI_IMAGE_PROVIDER = env('AI_IMAGE_PROVIDER', default='gemini')
AI_IMAGE_MODEL = env('AI_IMAGE_MODEL', default='gemini-3.1-flash-image')

# Optional per-image cost for usage/cost tracking (Epic 06: Generation Management).
# Left blank by default since real pricing should be confirmed against the
# provider's current rate card rather than assumed - cost_usd stays null until set.
AI_IMAGE_COST_PER_IMAGE_USD = env('AI_IMAGE_COST_PER_IMAGE_USD', default='')

# 'openai' (AI_IMAGE_PROVIDER=openai) reads OPENAI_API_KEY directly from the environment.
# gpt-image-1 sizes: 1024x1024, 1024x1536 (portrait - closest to the 4:5 layout), 1536x1024.
# Quality: low | medium | high | auto - higher quality costs more per image.
OPENAI_IMAGE_SIZE = env('OPENAI_IMAGE_SIZE', default='1024x1536')
OPENAI_IMAGE_QUALITY = env('OPENAI_IMAGE_QUALITY', default='medium')


# AI voice-over provider (Epic 07: AI Video Generation)
# gTTS is free and needs no API key - it works out of the box.

AI_VOICE_PROVIDER = env('AI_VOICE_PROVIDER', default='gtts')


# AI motion (video generation) provider (Epic 07: AI Video Generation)
# 'huggingface' reads HF_TOKEN (free to create, no card required - same token as
# HuggingFaceImageProvider, Epic 06) and generates text-to-video via Hugging Face's
# Inference Providers, routed to fal-ai and billed against the free monthly HF
# credit ($0.10/month - a couple of scenes' worth; falls back to zoom/pan once
# spent). AI_VIDEO_MODEL must be a model that route supports
# (e.g. Wan-AI/Wan2.2-TI2V-5B).
# 'replicate' reads REPLICATE_API_TOKEN, read directly by ReplicateVideoProvider
# from the environment (set it in .env) - deliberately not duplicated here. No
# free tier - billed per second of generated video, but proper image-to-video
# (animates the actual scene image) and much higher quality. AI_VIDEO_MODEL must
# then be a Replicate image-to-video model slug (e.g. wan-video/wan-2.2-i2v-fast).

AI_VIDEO_PROVIDER = env('AI_VIDEO_PROVIDER', default='huggingface')
AI_VIDEO_MODEL = env('AI_VIDEO_MODEL', default='Wan-AI/Wan2.2-TI2V-5B')
REPLICATE_API_TOKEN = env('REPLICATE_API_TOKEN', default='')

# Video rendering (Epic 07: Processing - FFmpeg, Compression). FFMPEG_BINARY may be a
# full path (e.g. C:/ffmpeg/bin/ffmpeg.exe); blank = look it up on PATH, then fall back
# to the binary bundled by the optional `imageio-ffmpeg` pip package if it's installed.
FFMPEG_BINARY = env('FFMPEG_BINARY', default='')
# H.264 CRF (lower = better quality/bigger file; 18-28 is sensible) and x264 preset.
VIDEO_CRF = env.int('VIDEO_CRF', default=23)
VIDEO_PRESET = env('VIDEO_PRESET', default='veryfast')


# Public URLs (Epic 11: Publishing, Epic 12: WhatsApp)
# Instagram and WhatsApp download media from a URL rather than accepting an upload, so
# that URL must be reachable from the public internet. In production this is your
# domain (or CDN/S3 bucket); in local development use a tunnel (e.g. `cloudflared tunnel
# --url http://localhost:8000` or ngrok) and put its https URL here.
BACKEND_PUBLIC_URL = env('BACKEND_PUBLIC_URL', default='http://localhost:8000')
PUBLIC_MEDIA_BASE_URL = env('PUBLIC_MEDIA_BASE_URL', default='')


# Social OAuth (Epic 10: Social Media Account Management)
# Meta (Facebook Pages + Instagram professional accounts) - create an app at
# developers.facebook.com (see docs/meta-setup-guide.md). Blank = OAuth "Connect with
# Facebook" stays disabled and accounts can only be connected by pasting a token.
META_APP_ID = env('META_APP_ID', default='')
META_APP_SECRET = env('META_APP_SECRET', default='')
META_GRAPH_API_VERSION = env('META_GRAPH_API_VERSION', default='v23.0')
# Optional Facebook Login for Business configuration ID - when set it's used instead of
# the scope list below (the configuration itself defines the permissions).
META_LOGIN_CONFIG_ID = env('META_LOGIN_CONFIG_ID', default='')
META_OAUTH_SCOPES = env.list('META_OAUTH_SCOPES', default=[
    'pages_show_list', 'pages_read_engagement', 'pages_manage_posts', 'read_insights',
    'business_management', 'instagram_basic', 'instagram_content_publish', 'instagram_manage_insights',
])

# LinkedIn - create an app at linkedin.com/developers (see docs/linkedin-setup-guide.md).
# Posting as a Company Page needs the "Community Management API" product approved.
LINKEDIN_CLIENT_ID = env('LINKEDIN_CLIENT_ID', default='')
LINKEDIN_CLIENT_SECRET = env('LINKEDIN_CLIENT_SECRET', default='')
# LinkedIn versioned REST API (YYYYMM). Each version is supported for about a year -
# bump this when LinkedIn sunsets the one in use.
LINKEDIN_API_VERSION = env('LINKEDIN_API_VERSION', default='202601')
LINKEDIN_OAUTH_SCOPES = env.list('LINKEDIN_OAUTH_SCOPES', default=[
    'openid', 'profile', 'w_member_social', 'r_organization_social', 'w_organization_social',
    'rw_organization_admin',
])

# The provider redirects the browser back to the *frontend* (FRONTEND_URL/oauth/callback/<provider>),
# which then hands the code to the API. Register exactly these URLs in the Meta/LinkedIn apps:
#   {SOCIAL_OAUTH_REDIRECT_BASE}/oauth/callback/meta
#   {SOCIAL_OAUTH_REDIRECT_BASE}/oauth/callback/linkedin
SOCIAL_OAUTH_REDIRECT_BASE = env('SOCIAL_OAUTH_REDIRECT_BASE', default='') or FRONTEND_URL


# WhatsApp Business Cloud API (Epic 12: WhatsApp Automation)
# 'console' (default) logs messages instead of sending them, so the whole workflow can
# be built and tested before a WhatsApp Business account exists. Switch to 'meta' once
# the values below are filled in (see docs/meta-setup-guide.md, part C).
WHATSAPP_PROVIDER = env('WHATSAPP_PROVIDER', default='console')
WHATSAPP_ACCESS_TOKEN = env('WHATSAPP_ACCESS_TOKEN', default='')
WHATSAPP_PHONE_NUMBER_ID = env('WHATSAPP_PHONE_NUMBER_ID', default='')
WHATSAPP_BUSINESS_ACCOUNT_ID = env('WHATSAPP_BUSINESS_ACCOUNT_ID', default='')
WHATSAPP_API_VERSION = env('WHATSAPP_API_VERSION', default='') or META_GRAPH_API_VERSION
# Webhook (delivery/read receipts): {BACKEND_PUBLIC_URL}/api/v1/whatsapp/webhook/
WHATSAPP_WEBHOOK_VERIFY_TOKEN = env('WHATSAPP_WEBHOOK_VERIFY_TOKEN', default='')
WHATSAPP_APP_SECRET = env('WHATSAPP_APP_SECRET', default='') or META_APP_SECRET


# Media storage (Epic 08: Storage - S3/R2, CDN)
# Local disk by default. Set USE_S3_STORAGE=True to store uploads/generated media in
# AWS S3 or Cloudflare R2 (R2: set AWS_S3_ENDPOINT_URL=https://<account>.r2.cloudflarestorage.com).
USE_S3_STORAGE = env.bool('USE_S3_STORAGE', default=False)
if USE_S3_STORAGE:
    AWS_ACCESS_KEY_ID = env('AWS_ACCESS_KEY_ID', default='')
    AWS_SECRET_ACCESS_KEY = env('AWS_SECRET_ACCESS_KEY', default='')
    AWS_STORAGE_BUCKET_NAME = env('AWS_STORAGE_BUCKET_NAME', default='')
    AWS_S3_ENDPOINT_URL = env('AWS_S3_ENDPOINT_URL', default='') or None
    AWS_S3_REGION_NAME = env('AWS_S3_REGION_NAME', default='') or None
    # Public CDN/custom domain in front of the bucket (e.g. media.example.com), optional.
    AWS_S3_CUSTOM_DOMAIN = env('AWS_S3_CUSTOM_DOMAIN', default='') or None
    # Media must be fetchable by Instagram/WhatsApp, so URLs are unsigned by default -
    # the bucket (or CDN) needs public read on the media prefix.
    AWS_QUERYSTRING_AUTH = env.bool('AWS_QUERYSTRING_AUTH', default=False)
    AWS_DEFAULT_ACL = None
    AWS_S3_FILE_OVERWRITE = False
    AWS_LOCATION = env('AWS_LOCATION', default='media')
    STORAGES = {
        'default': {'BACKEND': 'storages.backends.s3.S3Storage'},
        'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
    }


# Logging (Epic 26: Monitoring - Application logs)
LOG_LEVEL = env('LOG_LEVEL', default='INFO')
LOG_DIR = Path(env('LOG_DIR', default=str(BASE_DIR / 'logs')))
LOG_TO_FILE = env.bool('LOG_TO_FILE', default=False)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'standard': {'format': '%(asctime)s %(levelname)s [%(name)s] %(message)s'},
    },
    'handlers': {
        'console': {'class': 'logging.StreamHandler', 'formatter': 'standard'},
    },
    'root': {'handlers': ['console'], 'level': LOG_LEVEL},
    'loggers': {
        'django': {'handlers': ['console'], 'level': 'INFO', 'propagate': False},
        'django.request': {'handlers': ['console'], 'level': 'WARNING', 'propagate': False},
        'apps': {'handlers': ['console'], 'level': LOG_LEVEL, 'propagate': False},
        'celery': {'handlers': ['console'], 'level': 'INFO', 'propagate': False},
    },
}
if LOG_TO_FILE:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    LOGGING['handlers']['file'] = {
        'class': 'logging.handlers.RotatingFileHandler',
        'filename': str(LOG_DIR / 'app.log'),
        'maxBytes': 10 * 1024 * 1024,
        'backupCount': 5,
        'formatter': 'standard',
        'encoding': 'utf-8',
    }
    for logger_config in [LOGGING['root'], *LOGGING['loggers'].values()]:
        logger_config['handlers'].append('file')

# Error tracking (Epic 26: Monitoring) - initialized in production.py/staging.py when set.
SENTRY_DSN = env('SENTRY_DSN', default='')


# Celery / Redis (Epic 06: Generation Management - Queue)

REDIS_URL = env('REDIS_URL', default='redis://localhost:6379/0')
CELERY_BROKER_URL = env('CELERY_BROKER_URL', default=REDIS_URL)
CELERY_RESULT_BACKEND = env('CELERY_RESULT_BACKEND', default=REDIS_URL)
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TASK_TRACK_STARTED = True
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True

# Scheduled jobs (Epic 12/13/22) - requires `celery -A config beat` running alongside
# the worker, or these schedules never fire.
CELERY_BEAT_SCHEDULE = {
    'auto-generate-due-content': {
        # Every 15 minutes rather than a single daily slot, so a calendar item's actual
        # scheduled_time (not just scheduled_date) is honored reasonably promptly - see
        # apps.content_calendar.tasks.auto_generate_due_content for why a once-daily run
        # can't do that.
        'task': 'apps.content_calendar.tasks.auto_generate_due_content',
        'schedule': crontab(minute='*/15'),
    },
    'send-content-reminders': {
        'task': 'apps.notifications.tasks.send_content_reminders',
        'schedule': crontab(hour=9, minute=0),
    },
    'check-social-account-expiry': {
        'task': 'apps.social_accounts.tasks.check_social_account_expiry',
        'schedule': crontab(hour=8, minute=0),
    },
    'refresh-social-tokens': {
        'task': 'apps.social_accounts.tasks.refresh_expiring_tokens',
        'schedule': crontab(hour=3, minute=0),
    },
    # Epic 11: Publishing & Scheduling - picks up every scheduled post whose time has come.
    'dispatch-due-publish-jobs': {
        'task': 'apps.publishing.tasks.dispatch_due_publish_jobs',
        'schedule': crontab(minute='*'),
    },
    # Epic 09/12: remind clients about content still waiting for their approval.
    'send-approval-reminders': {
        'task': 'apps.notifications.tasks.send_approval_reminders',
        'schedule': crontab(minute=5),
    },
    # Epic 15: Analytics - runs hourly, but each company is only synced once per
    # PlatformSettings.analytics_sync_interval_hours.
    'sync-analytics': {
        'task': 'apps.analytics.tasks.sync_all_analytics',
        'schedule': crontab(minute=20),
    },
    'snapshot-account-metrics': {
        'task': 'apps.analytics.tasks.snapshot_all_account_metrics',
        'schedule': crontab(hour=2, minute=30),
    },
    # Epic 16: Reports - runs daily, generates last month's reports on the configured day.
    'generate-monthly-reports': {
        'task': 'apps.reports.tasks.generate_monthly_reports',
        'schedule': crontab(hour=6, minute=0),
    },
    # Epic 17: subscription expiry/renewal reminders + storage usage snapshot.
    'check-subscriptions': {
        'task': 'apps.subscriptions.tasks.check_subscriptions',
        'schedule': crontab(hour=7, minute=0),
    },
    'recalculate-storage-usage': {
        'task': 'apps.subscriptions.tasks.recalculate_storage_usage',
        'schedule': crontab(hour=4, minute=0),
    },
}

# One task at a time per worker process - video renders and publishing uploads are
# long-running, so prefetching more would just starve the other worker processes.
CELERY_WORKER_PREFETCH_MULTIPLIER = env.int('CELERY_WORKER_PREFETCH_MULTIPLIER', default=1)


if 'test' in sys.argv:
    # The test suite must not depend on a developer's local .env (e.g. a machine with
    # SEND_NOTIFICATION_EMAILS=True would otherwise send extra emails in tests that
    # assume the default). Tests that need these on use @override_settings.
    SEND_NOTIFICATION_EMAILS = False
    WHATSAPP_PROVIDER = 'console'
    PUBLIC_MEDIA_BASE_URL = ''
