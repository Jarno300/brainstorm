"""
Alembic migration environment.

Reads DATABASE_URL from the application config so that all
environments (local, Docker, CI) use the same source of truth.
"""

from logging.config import fileConfig
import os
import sys

from sqlalchemy import engine_from_config, pool

from alembic import context

# ── Path setup: ensure backend/app/ is importable ──────────
# When running from backend/ with "prepend_sys_path = ." in alembic.ini,
# the backend/ directory is already on sys.path.
# We also add it explicitly for edge cases.
_backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

# ── Load .env before importing config ──────────────────────
from dotenv import load_dotenv
from pathlib import Path

for candidate in (Path(_backend_dir) / ".env", Path(_backend_dir).parent / ".env"):
    if candidate.exists():
        load_dotenv(candidate)
        break
else:
    load_dotenv()

# ── Database URL from app config ───────────────────────────
from app.config import DATABASE_URL

# Alembic Config object
config = context.config

# Override sqlalchemy.url with our DATABASE_URL
config.set_main_option("sqlalchemy.url", DATABASE_URL)

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ── Metadata ───────────────────────────────────────────────
from app.database import Base
# Import ALL models so Base.metadata is fully populated
import app.models  # noqa: F401 — triggers model registration

target_metadata = Base.metadata

# ── Run migrations ─────────────────────────────────────────

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode — generates SQL without connecting."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode — connects to the database."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            # Compare server defaults so we don't miss drift
            compare_server_default=True,
            # Compare types in case of changes
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
