import re
import uuid
from typing import Any

# --- Thresholds ---
PLACEHOLDER_THRESHOLD = 1000  # chars — content below this skips placeholder stage
SUMMARY_PREVIEW_RATIO = 0.3   # target summary length ratio


class Stage1SummaryPreview:
    """Compress large text into a structured summary preserving key info."""

    def process(self, text: str, max_chars: int = 500) -> str:
        if not text:
            return ""
        if len(text) <= max_chars:
            return text
        # Preserve first N chars + extract key patterns
        head = text[:max_chars]
        # Extract key-value pairs, numbers, identifiers
        keys = set(re.findall(r'"[a-zA-Z_]+":', text))
        numbers = set(re.findall(r'\b\d{3,}\b', text))
        extras = []
        if keys:
            extras.append("keys: " + ", ".join(sorted(keys)[:10]))
        if numbers:
            extras.append("values: " + ", ".join(sorted(numbers)[:5]))
        summary = head
        if extras:
            summary += "\n... [summary: " + "; ".join(extras) + "] ..."
        return summary


class _CacheStore:
    """Internal cache for placeholder content."""

    def __init__(self):
        self._store: dict[str, str] = {}

    def put(self, content: str) -> str:
        key = str(uuid.uuid4())[:8]
        self._store[key] = content
        return key

    def get(self, key: str) -> str | None:
        return self._store.get(key)


class Stage2PlaceholderReplacement:
    """Replace large content blocks with cache-friendly placeholders."""

    def __init__(self):
        self._cache = _CacheStore()

    def compress(self, content: str, threshold: int = PLACEHOLDER_THRESHOLD) -> str:
        if len(content) <= threshold:
            return content
        key = self._cache.put(content)
        return f"{{{{placeholder:{key}}}}}"

    def decompress(self, placeholder: str) -> str | None:
        m = re.match(r"^\{\{placeholder:([a-f0-9]+)\}\}$", placeholder)
        if not m:
            return None
        return self._cache.get(m.group(1))


class Stage3OnDemandRetrieval:
    """Retrieve full content from placeholders on demand."""

    def __init__(self):
        self._cache = _CacheStore()

    def compress(self, content: str) -> str:
        key = self._cache.put(content)
        return f"{{{{ph:{key}}}}}"

    def decompress(self, token: str) -> str | None:
        m = re.match(r"^\{\{ph:([a-f0-9]+)\}\}$", token)
        if not m:
            return None
        return self._cache.get(m.group(1))


class Stage4Fallback:
    """Prune to N most recent critical items when over hard limit."""

    def __init__(self, max_items: int = 50):
        self._max_items = max_items

    def prune(self, items: list[Any]) -> list[Any]:
        if len(items) <= self._max_items:
            return items
        # Keep items with "critical" in name, then most recent
        critical = [i for i in items if isinstance(i, str) and "critical" in i.lower()]
        rest = [i for i in items if i not in critical]
        keep = critical + rest[-(self._max_items - len(critical)):]
        return keep[:self._max_items]


class CompressorPipeline:
    """Full 4-stage hierarchical context compression pipeline."""

    def __init__(
        self,
        token_threshold: int = 2000,
        turn_threshold: int = 10,
    ):
        self.stage1 = Stage1SummaryPreview()
        self.stage2 = Stage2PlaceholderReplacement()
        self.stage3 = Stage3OnDemandRetrieval()
        self.stage4 = Stage4Fallback(max_items=50)

        self._token_threshold = token_threshold
        self._turn_threshold = turn_threshold
        self._total_tokens = 0
        self._total_turns = 0
        self._introspect_flag = False

    # --- Triggers ---

    def update_metrics(self, token_count: int = 0, turn_count: int = 0) -> None:
        self._total_tokens += token_count
        self._total_turns += turn_count

    def signal_introspect(self) -> None:
        self._introspect_flag = True

    def should_trigger(self) -> bool:
        if self._introspect_flag:
            self._introspect_flag = False
            return True
        if self._total_tokens > self._token_threshold:
            return True
        if self._total_turns > self._turn_threshold:
            return True
        return False

    # --- Pipeline ---

    def compress(self, content: str) -> str:
        """Stage 1 → 2: generate summary, then replace large content with placeholder.

        - If content is large: stores full content in external cache,
          returns a placeholder token.
        - If content is small: returns content unchanged.
        """
        # Stage 1: generate summary (stored internally, not used for decompress path)
        self._last_summary = self.stage1.process(content)
        # Stage 2: replace large content with placeholder
        return self.stage2.compress(content)

    def summary(self) -> str:
        """Return the last generated summary (Stage 1 output)."""
        return getattr(self, "_last_summary", "")

    def decompress(self, token: str) -> str | None:
        """Stage 3: resolve placeholder back to full content."""
        result = self.stage2.decompress(token)
        if result is not None:
            return result
        return self.stage3.decompress(token)

    def prune(self, items: list[Any]) -> list[Any]:
        """Stage 4: prune items when over hard limit."""
        return self.stage4.prune(items)
