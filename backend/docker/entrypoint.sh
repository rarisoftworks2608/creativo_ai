#!/bin/sh
# Container entrypoint for the backend, Celery worker and Celery beat (Epic 26).
#   WAIT_FOR_DB=1        wait for PostgreSQL before starting (default on)
#   RUN_MIGRATIONS=1     apply migrations first (set on the backend service only)
#   DJANGO_SUPERUSER_EMAIL / DJANGO_SUPERUSER_PASSWORD
#                        create the first admin login if it doesn't exist yet
set -e

if [ "${WAIT_FOR_DB:-1}" = "1" ]; then
  python manage.py wait_for_db --timeout "${DB_WAIT_TIMEOUT:-90}"
fi

if [ "${RUN_MIGRATIONS:-0}" = "1" ]; then
  python manage.py migrate --noinput
  if [ -n "${DJANGO_SUPERUSER_EMAIL}" ] && [ -n "${DJANGO_SUPERUSER_PASSWORD}" ]; then
    python manage.py createsuperuser --noinput --email "${DJANGO_SUPERUSER_EMAIL}" 2>/dev/null \
      && echo "Created admin ${DJANGO_SUPERUSER_EMAIL}" \
      || echo "Admin ${DJANGO_SUPERUSER_EMAIL} already exists - skipping"
  fi
fi

exec "$@"
