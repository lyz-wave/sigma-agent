import tempfile
from pathlib import Path

import pytest
from sigma.memory import FactualMemory, ProceduralMemory, EpisodicMemory
from sigma.storage import StorageBackend, SQLiteStorageBackend


class TestStorageBackend:
    """Seam: StorageBackend — store and query memory records."""

    @pytest.fixture
    def db_path(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            path = Path(f.name)
            yield path
        try:
            path.unlink(missing_ok=True)
        except PermissionError:
            pass  # Windows file lock; cleaned up later

    @pytest.fixture
    def store(self, db_path):
        backend = SQLiteStorageBackend(db_path)
        yield backend
        backend.close()

    def test_interface_is_abstract(self):
        with pytest.raises(TypeError):
            StorageBackend()  # type: ignore

    def test_store_and_retrieve_factual(self, store):
        mem = FactualMemory(
            key="api_key_format",
            content="API key is a 32-char hex string",
            source="docs",
            tags=["api", "config"],
        )
        store.store(mem)
        results = store.query(memory_type="factual", tags=[])
        assert len(results) == 1
        assert results[0].key == "api_key_format"
        assert results[0].type == "factual"

    def test_store_multiple_types(self, store):
        store.store(FactualMemory(key="f1", content="fact1", source="s"))
        store.store(ProceduralMemory(key="p1", content="proc1", domain="d", steps=["a"]))
        store.store(EpisodicMemory(key="e1", content="ep1", context={}, outcome="ok"))

        factuals = store.query(memory_type="factual", tags=[])
        procedurals = store.query(memory_type="procedural", tags=[])
        episodics = store.query(memory_type="episodic", tags=[])
        assert len(factuals) == 1
        assert len(procedurals) == 1
        assert len(episodics) == 1

    def test_query_by_tags(self, store):
        store.store(FactualMemory(key="k1", content="c1", source="s1", tags=["tag_a", "tag_b"]))
        store.store(FactualMemory(key="k2", content="c2", source="s2", tags=["tag_b"]))
        store.store(FactualMemory(key="k3", content="c3", source="s3", tags=["tag_c"]))

        results = store.query(memory_type="factual", tags=["tag_a"])
        assert len(results) == 1
        assert results[0].key == "k1"

        results = store.query(memory_type="factual", tags=["tag_b"])
        assert len(results) == 2

    def test_query_limit(self, store):
        for i in range(10):
            store.store(FactualMemory(key=f"k{i}", content=f"c{i}", source="s"))
        results = store.query(memory_type="factual", tags=[], limit=3)
        assert len(results) == 3

    def test_query_empty(self, store):
        results = store.query(memory_type="factual", tags=[])
        assert results == []

    def test_cross_reference(self, store):
        mem1 = FactualMemory(key="original", content="original data", source="s", tags=["root"])
        mem2 = FactualMemory(key="related", content="related data", source="s", tags=["child"])
        store.store(mem1)
        store.store(mem2)
        refs = store.cross_reference("original")
        assert isinstance(refs, list)

    def test_sqlite_persistence(self, db_path):
        """Cross-session: store, close, reopen, query."""
        store1 = SQLiteStorageBackend(db_path)
        store1.store(FactualMemory(key="persist", content="data", source="s", tags=["test"]))
        del store1

        store2 = SQLiteStorageBackend(db_path)
        results = store2.query(memory_type="factual", tags=["test"])
        assert len(results) == 1
        assert results[0].key == "persist"
