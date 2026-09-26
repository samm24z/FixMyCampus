"""Custom SQLAlchemy column types and pgvector adaptation."""

import json
from typing import Any, List, Optional
from sqlalchemy import TypeDecorator, Text
from pgvector.sqlalchemy import Vector as PgVector


class VectorType(TypeDecorator):
    """SQLAlchemy TypeDecorator providing pgvector.Vector support with generic fallback."""

    impl = Text
    cache_ok = True

    def __init__(self, dim: int = 384, **kwargs: Any):
        super().__init__(**kwargs)
        self.dim = dim
        self._pg_vector = PgVector(dim)

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(self._pg_vector)
        return dialect.type_descriptor(Text())

    def process_bind_param(self, value: Optional[List[float]], dialect) -> Any:
        if value is None:
            return None
        if dialect.name == "postgresql":
            return value
        return json.dumps(value)

    def process_result_value(self, value: Any, dialect) -> Optional[List[float]]:
        if value is None:
            return None
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            try:
                return json.loads(value)
            except Exception:
                return None
        return list(value)
