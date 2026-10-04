#!/bin/sh
# Database + media backup for the Docker deployment (Epic 26: Backup).
#   ./scripts/backup.sh                 -> backups/db-YYYYmmdd-HHMM.sql.gz + backups/media-YYYYmmdd-HHMM.tar.gz
#   KEEP_DAYS=30 ./scripts/backup.sh    -> keep 30 days of backups (default 14)
# Schedule it with cron on the server, e.g.:  0 2 * * * cd /srv/creativo_ai && ./scripts/backup.sh
# Copy the backups/ folder off the server (S3, R2, rsync) - a backup on the same disk is not a backup.
set -e

COMPOSE="${COMPOSE:-docker compose}"
STAMP="$(date +%Y%m%d-%H%M)"
DIR="${BACKUP_DIR:-backups}"
KEEP_DAYS="${KEEP_DAYS:-14}"
DB_USER="${POSTGRES_USER:-creativo}"
DB_NAME="${POSTGRES_DB:-creativo}"
mkdir -p "$DIR"

echo "Backing up database $DB_NAME..."
$COMPOSE exec -T db pg_dump -U "$DB_USER" -d "$DB_NAME" --no-owner --format=plain | gzip > "$DIR/db-$STAMP.sql.gz"

echo "Backing up media files..."
$COMPOSE run --rm --no-deps -v "$(pwd)/$DIR:/backup" --entrypoint sh backend \
  -c "tar -czf /backup/media-$STAMP.tar.gz -C /app media"

echo "Removing backups older than $KEEP_DAYS days..."
find "$DIR" -name 'db-*.sql.gz' -mtime +"$KEEP_DAYS" -delete
find "$DIR" -name 'media-*.tar.gz' -mtime +"$KEEP_DAYS" -delete

echo "Done: $DIR/db-$STAMP.sql.gz and $DIR/media-$STAMP.tar.gz"
