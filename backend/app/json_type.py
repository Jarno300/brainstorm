from sqlalchemy import Text
from sqlalchemy.types import TypeDecorator
import json


class JSONType(TypeDecorator):
    """Cross-database JSON type. Stores as Text (SQLite) or uses native JSON (PostgreSQL)."""
    impl = Text
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import JSON
            return dialect.type_descriptor(JSON())
        return dialect.type_descriptor(Text())

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if dialect.name == "postgresql":
            return value
        return json.dumps(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if dialect.name == "postgresql" or isinstance(value, (dict, list)):
            return value
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return {}
