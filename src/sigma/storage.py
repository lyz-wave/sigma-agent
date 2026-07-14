import json
import sqlite3
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from sigma.memory import EpisodicMemory, FactualMemory, MemoryRecord, ProceduralMemory


class StorageBackend(ABC):
    """Pluggable storage interface for memory records."""

    @abstractmethod
    def store(self, record: MemoryRecord) -> None:
        ...

    @abstractmethod
    def query(
        self, memory_type: str, tags: list[str], limit: int = 100
    ) -> list[MemoryRecord]:
        ...

    @abstractmethod
    def cross_reference(self, key: str) -> list[str]:
        ...


_MEMORY_CLASSES: dict[str, type[MemoryRecord]] = {
    "factual": FactualMemory,
    "procedural": ProceduralMemory,
    "episodic": EpisodicMemory,
}


def _record_to_row(record: MemoryRecord) -> dict[str, Any]:
    extra: dict[str, Any] = {}
    if isinstance(record, FactualMemory):
        extra["source"] = record.source
    elif isinstance(record, ProceduralMemory):
        extra["domain"] = record.domain
        extra["steps"] = record.steps
    elif isinstance(record, EpisodicMemory):
        extra["context"] = record.context
        extra["outcome"] = record.outcome
    return {
        "key": record.key,
        "type": record.type,
        "content": record.content,
        "tags": json.dumps(record.tags),
        "extra_data": json.dumps(extra),
    }


def _row_to_record(row: sqlite3.Row) -> MemoryRecord:
    cls = _MEMORY_CLASSES.get(row["type"], FactualMemory)
    extra = json.loads(row["extra_data"])
    tags = json.loads(row["tags"])
    return cls(
        key=row["key"],
        content=row["content"],
        tags=tags,
        **extra,
    )


class SQLiteStorageBackend(StorageBackend):
    """SQLite-backed memory storage with pluggable interface."""

    def __init__(self, db_path: str | Path):
        self._conn = sqlite3.connect(str(db_path))
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def close(self) -> None:
        self._conn.close()

    def _init_schema(self) -> None:
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT NOT NULL UNIQUE,
                type TEXT NOT NULL,
                content TEXT NOT NULL,
                tags TEXT DEFAULT '[]',
                extra_data TEXT DEFAULT '{}'
            )
        """)
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_type ON memories(type)"
        )
        self._conn.commit()

    def store(self, record: MemoryRecord) -> None:
        row = _record_to_row(record)
        self._conn.execute(
            """INSERT OR REPLACE INTO memories (key, type, content, tags, extra_data)
               VALUES (:key, :type, :content, :tags, :extra_data)""",
            row,
        )
        self._conn.commit()

    def query(
        self, memory_type: str, tags: list[str], limit: int = 100
    ) -> list[MemoryRecord]:
        cursor = self._conn.execute(
            "SELECT * FROM memories WHERE type = ? ORDER BY id DESC LIMIT ?",
            (memory_type, limit),
        )
        results = [_row_to_record(row) for row in cursor.fetchall()]
        if tags:
            results = [
                r for r in results if any(t in r.tags for t in tags)
            ]
        return results[:limit]

    def cross_reference(self, key: str) -> list[str]:
        """Find memory keys related to the given key via tag overlap."""
        cursor = self._conn.execute(
            "SELECT tags FROM memories WHERE key = ?", (key,)
        )
        row = cursor.fetchone()
        if not row:
            return []
        tags = json.loads(row["tags"])
        if not tags:
            return []
        cursor = self._conn.execute(
            "SELECT key, tags FROM memories WHERE key != ?", (key,)
        )
        related = []
        for r in cursor.fetchall():
            other_tags = json.loads(r["tags"])
            if any(t in other_tags for t in tags):
                related.append(r["key"])
        return related
