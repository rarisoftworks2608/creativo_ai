"""Blocks until the database accepts connections (Epic 26: container start-up ordering).

Used by docker/entrypoint.sh so the backend, worker and beat containers don't crash-loop
while PostgreSQL is still starting.
"""

import time

from django.core.management.base import BaseCommand, CommandError
from django.db import connections
from django.db.utils import OperationalError


class Command(BaseCommand):
    help = 'Wait until the default database is reachable.'

    def add_arguments(self, parser):
        parser.add_argument('--timeout', type=int, default=90, help='Seconds to wait before giving up.')

    def handle(self, *args, **options):
        deadline = time.monotonic() + options['timeout']
        while True:
            try:
                connections['default'].ensure_connection()
            except OperationalError as exc:
                if time.monotonic() > deadline:
                    raise CommandError(f'Database still unreachable after {options["timeout"]}s: {exc}') from exc
                self.stdout.write('Waiting for the database...')
                time.sleep(2)
            else:
                self.stdout.write(self.style.SUCCESS('Database is available.'))
                return
