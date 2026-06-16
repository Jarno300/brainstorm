import os
import logging.config
import time as _time_module

# ─── Log Level ──────────────────────────────────────────────
LOG_LEVEL = os.getenv("APP_LOG_LEVEL", "INFO").upper()
LOG_FORMAT = os.getenv("APP_LOG_FORMAT", "text").lower()  # "text" or "json"
APP_ENV = os.getenv("APP_ENV", "development")

# ─── Log Format ─────────────────────────────────────────────
SIMPLE_FORMAT = "[%(asctime)s] %(levelname)-7s %(name)s: %(message)s"
VERBOSE_FORMAT = (
    "[%(asctime)s] %(levelname)-7s %(name)s %(filename)s:%(lineno)d | "
    "%(request_id)s | %(message)s"
)


def _choose_formatters():
    """Select formatter classes based on LOG_FORMAT env var."""
    if LOG_FORMAT == "json":
        return {
            "verbose": {
                "()": "pythonjsonlogger.json.JsonFormatter",
                "format": "%(asctime)s %(levelname)s %(name)s %(filename)s %(lineno)d %(request_id)s %(message)s",
                "timestamp": True,
            },
        }
    # Text formatters
    return {
        "simple": {
            "format": SIMPLE_FORMAT,
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
        "verbose": {
            "format": VERBOSE_FORMAT if APP_ENV != "development" else SIMPLE_FORMAT,
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
    }


LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "request_id": {
            "()": "app.logging_config.RequestIDFilter",
        },
    },
    "formatters": _choose_formatters(),
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "level": LOG_LEVEL,
            "formatter": "verbose",
            "filters": ["request_id"] if APP_ENV != "development" or LOG_FORMAT == "json" else [],
            "stream": "ext://sys.stdout",
        },
    },
    "loggers": {
        "app": {
            "level": LOG_LEVEL,
            "handlers": ["console"],
            "propagate": False,
        },
        "uvicorn": {
            "level": "INFO",
            "handlers": ["console"],
            "propagate": False,
        },
        "sqlalchemy": {
            "level": os.getenv("SQLALCHEMY_LOG_LEVEL", "WARNING").upper(),
            "handlers": ["console"],
            "propagate": False,
        },
        "app.services": {
            "level": LOG_LEVEL,
            "handlers": ["console"],
            "propagate": False,
        },
        "app.tasks": {
            "level": LOG_LEVEL,
            "handlers": ["console"],
            "propagate": False,
        },
    },
    "root": {
        "level": LOG_LEVEL,
        "handlers": ["console"],
    },
}

# Thread-local storage for request ID
import threading
_request_context = threading.local()


def set_request_id(request_id: str):
    _request_context.request_id = request_id


def get_request_id() -> str:
    return getattr(_request_context, "request_id", "-")


class RequestIDFilter(logging.Filter):
    """Add the current request ID to every log record."""
    def filter(self, record):
        record.request_id = get_request_id()
        return True


def configure_logging():
    logging.config.dictConfig(LOGGING_CONFIG)
