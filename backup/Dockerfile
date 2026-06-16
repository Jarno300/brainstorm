FROM postgres:15-alpine

RUN apk add --no-cache dcron tzdata

COPY backup.sh /backup.sh
COPY entrypoint.sh /entrypoint.sh

RUN chmod +x /backup.sh /entrypoint.sh

# Create the cron schedule from env var
ENV BACKUP_SCHEDULE="0 2 * * *"
ENV BACKUP_RETENTION_DAYS=30
ENV POSTGRES_USER=raguser
ENV POSTGRES_DB=ragdb

ENTRYPOINT ["/entrypoint.sh"]
