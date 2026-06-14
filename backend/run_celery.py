#!/usr/bin/env python
"""Run the Celery worker for Brainstorm."""
from app.tasks.celery_app import celery_app

if __name__ == "__main__":
    celery_app.start(argv=["worker", "--loglevel=info", "--pool=solo"])
