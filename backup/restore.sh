#!/bin/sh
# Database restore script
# Usage: ./restore.sh <backup_file.sql.gz>
set -eu

if [ $# -lt 1 ]; then
    echo "Usage: $0 <backup_file.sql.gz>"
    echo "       Restores a gzipped pg_dump into the database."
    echo ""
    echo "Environment variables required:"
    echo "  PGHOST, POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB"
    exit 1
fi

BACKUP_FILE="$1"

if [ ! -f "$BACKUP_FILE" ]; then
    echo "Error: $BACKUP_FILE not found"
    exit 1
fi

export PGPASSWORD="$POSTGRES_PASSWORD"

echo "Restoring from: $BACKUP_FILE"
echo "Target: $POSTGRES_USER@$PGHOST/$POSTGRES_DB"
echo ""
echo "WARNING: This will overwrite existing data!"
echo "Press Ctrl+C within 5 seconds to cancel..."
sleep 5

# Drop and recreate to ensure clean restore
psql -h "$PGHOST" -U "$POSTGRES_USER" -d postgres -c "DROP DATABASE IF EXISTS ${POSTGRES_DB};"
psql -h "$PGHOST" -U "$POSTGRES_USER" -d postgres -c "CREATE DATABASE ${POSTGRES_DB} OWNER ${POSTGRES_USER};"

gunzip -c "$BACKUP_FILE" | psql -h "$PGHOST" -U "$POSTGRES_USER" -d "$POSTGRES_DB"

echo ""
echo "Restore complete!"
