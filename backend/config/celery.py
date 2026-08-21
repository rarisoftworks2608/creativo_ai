"""Celery application (Epic 06: Generation Management - Queue).

Run a worker with:
    celery -A config worker -l info --pool=solo   # --pool=solo is required on Windows
"""

import os

from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')

app = Celery('config')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
