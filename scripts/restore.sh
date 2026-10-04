#!/bin/sh
# Restores a database (and optionally media) backup made by scripts/backup.sh (Epic 26: Disaster recovery).
#   ./scripts/restore.sh backups/db-20261001-0200.sql.gz [backups/media-20261001-0200.tar.gz]
# WARNING: replaces the current database contents.
set -e

DB_FILE="$1"
MEDIA_FILE="$2"
COMPOSE="${COMPOSE:-docker compose}"
DB_USER="${POSTGRES_USER:-creativo}"
DB_NAME="${POSTGRES_DB:-creativo}"

[ -f "$DB_FILE" ] || { echo "Usage: $0 <db-backup.sql.gz> [media-backup.tar.gz]"; exit 1; }

printf "This will REPLACE database %s with %s. Type 'yes' to continue: " "$DB_NAME" "$DB_FILE"
read -r answer
[ "$answer" = "yes" ] || { echo "Aborted."; exit 1; }

echo "Stopping app services..."
$COMPOSE stop backend worker beat

echo "Recreating database..."
$COMPOSE exec -T db psql -U "$DB_USER" -d postgres -c "DROP DATABASE IF EXISTS \"$DB_NAME\" WITH (FORCE);"
$COMPOSE exec -T db psql -U "$DB_USER" -d postgres -c "CREATE DATABASE \"$DB_NAME\" OWNER \"$DB_USER\";"
gunzip -c "$DB_FILE" | $COMPOSE exec -T db psql -U "$DB_USER" -d "$DB_NAME" -q

if [ -n "$MEDIA_FILE" ]; then
  echo "Restoring media..."
  $COMPOSE run --rm --no-deps -v "$(pwd)/$(dirname "$MEDIA_FILE"):/backup" --entrypoint sh backend \
    -c "rm -rf /app/media/* && tar -xzf /backup/$(basename "$MEDIA_FILE") -C /app"
fi

echo "Starting app services..."
$COMPOSE up -d backend worker beat
echo "Restore complete."
