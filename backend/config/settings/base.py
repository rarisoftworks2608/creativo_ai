"""
Base Django settings shared by every environment.

Environment-specific files (development.py / staging.py / production.py)
import everything from this module with `from .base import *` and then
override what differs for that environment.
"""

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
}
