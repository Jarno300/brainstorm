#!/bin/sh
set -eu

echo "[$(date)] Backup service starting — schedule: ${BACKUP_SCHEDULE}"

# Run an immediate backup on startup
/backup.sh

# Set up crontab
echo "${BACKUP_SCHEDULE} /backup.sh >> /proc/1/fd/1 2>&1" > /etc/crontabs/root

# Start cron in foreground
exec crond -f -l 2
