#!/bin/sh
set -eu

TIMESTAMP=$(date -u +"%Y%m%d_%H%M%S")
BACKUP_FILE="/backups/${POSTGRES_DB}_${TIMESTAMP}.sql.gz"

echo "[$(date)] Starting backup: $BACKUP_FILE"

export PGPASSWORD="$POSTGRES_PASSWORD"

pg_dump \
    -h "$PGHOST" \
    -U "$POSTGRES_USER" \
    -d "$POSTGRES_DB" \
    --no-owner \
    --no-acl \
    --compress=9 \
    -f "$BACKUP_FILE"

echo "[$(date)] Backup complete: $(ls -lh "$BACKUP_FILE" | awk '{print $5}')"

# Remove backups older than retention period
find /backups -name "*.sql.gz" -mtime "+${BACKUP_RETENTION_DAYS}" -delete

echo "[$(date)] Cleanup done. Backups: $(ls /backups/*.sql.gz 2>/dev/null | wc -l) files"
