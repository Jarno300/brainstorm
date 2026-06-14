from app.tasks.celery_app import celery_app
from app.tasks.classification_tasks import process_message_classification

__all__ = ["celery_app", "process_message_classification"]
