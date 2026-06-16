import os
from celery import Celery
from app.config import CELERY_BROKER_URL, CELERY_RESULT_BACKEND, SENTRY_DSN, SENTRY_TRACES_SAMPLE_RATE, APP_ENV

# ── Sentry for Celery workers ─────────────────────────────
if SENTRY_DSN:
    import sentry_sdk
    from sentry_sdk.integrations.celery import CeleryIntegration

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        environment=APP_ENV,
        traces_sample_rate=SENTRY_TRACES_SAMPLE_RATE,
        send_default_pii=False,
        integrations=[CeleryIntegration()],
    )

celery_app = Celery(
    "brainstorm",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
    include=["app.tasks.classification_tasks"],
)

# ── Pool configuration ──────────────────────────────────────
# Default to prefork (multi-process) in production for real concurrency.
# In development (especially Windows), solo/single-threaded is fine.
# Override with CELERY_POOL env var: solo | prefork | gevent | threads
CELERY_POOL = os.getenv("CELERY_POOL", "prefork")

# Number of worker processes (prefork only)
CELERY_CONCURRENCY = int(os.getenv("CELERY_CONCURRENCY", "4"))

# Task timeouts
CELERY_TASK_SOFT_TIME_LIMIT = int(os.getenv("CELERY_TASK_SOFT_TIME_LIMIT", "180"))   # seconds
CELERY_TASK_TIME_LIMIT = int(os.getenv("CELERY_TASK_TIME_LIMIT", "300"))              # seconds

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    # Concurrency
    worker_pool=CELERY_POOL,
    worker_concurrency=CELERY_CONCURRENCY,
    # Timeouts
    task_soft_time_limit=CELERY_TASK_SOFT_TIME_LIMIT,
    task_time_limit=CELERY_TASK_TIME_LIMIT,
    # Dead-letter: tasks that fail after all retries go to a dedicated queue
    task_default_queue="default",
    task_queues={
        "default": {"exchange": "default", "routing_key": "default"},
        "dead_letter": {"exchange": "dead_letter", "routing_key": "dead_letter"},
    },
)  
