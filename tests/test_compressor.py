import pytest
from sigma.compressor import (
    Stage1SummaryPreview,
    Stage2PlaceholderReplacement,
    Stage3OnDemandRetrieval,
    Stage4Fallback,
    CompressorPipeline,
)


class TestCompressorStages:
    """Seam: each compressor stage independently produces correct output."""

    def test_stage1_summary_preserves_key_info(self):
        text = "Error: connection refused on port 8080. " + "verbose log " * 50
        stage = Stage1SummaryPreview()
        result = stage.process(text)
        assert len(result) < len(text)
        assert "8080" in result or "port" in result

    def test_stage1_empty_text(self):
        stage = Stage1SummaryPreview()
        assert stage.process("") == ""

    def test_stage2_placeholder_round_trip(self):
        content = "Large tool output with " + "lots of logs " * 100
        stage = Stage2PlaceholderReplacement()
        placeholder = stage.compress(content)
        assert placeholder.startswith("{{placeholder:")
        retrieved = stage.decompress(placeholder)
        assert retrieved == content

    def test_stage2_compress_twice(self):
        stage = Stage2PlaceholderReplacement()
        p1 = stage.compress("x" * 2000)
        p2 = stage.compress("y" * 2000)
        assert p1 != p2
        assert stage.decompress(p1) == "x" * 2000
        assert stage.decompress(p2) == "y" * 2000

    def test_stage3_retrieval_from_external(self):
        stage = Stage3OnDemandRetrieval()
        placeholder = stage.compress("deferred content")
        assert stage.decompress(placeholder) == "deferred content"

    def test_stage4_fallback_prunes(self):
        items = ["critical_a", "critical_b", "normal_c", "normal_d"]
        stage = Stage4Fallback(max_items=2)
        result = stage.prune(items)
        assert len(result) == 2
        assert "critical_a" in result
        assert "critical_b" in result

    def test_stage4_below_limit_no_prune(self):
        items = ["a", "b"]
        stage = Stage4Fallback(max_items=5)
        assert stage.prune(items) == items


class TestCompressorPipeline:
    """Seam: CompressorPipeline — full 4-stage pipeline with triggers."""

    def test_pipeline_compress_decompress_integrity(self):
        pipeline = CompressorPipeline()
        content = "Large JSON output: " + "x" * 5000
        compressed = pipeline.compress(content)
        assert isinstance(compressed, str)
        assert "{{placeholder:" in compressed

        decompressed = pipeline.decompress(compressed)
        assert decompressed == content

    def test_compress_small_content_skips_placeholder(self):
        pipeline = CompressorPipeline()
        content = "small output"
        result = pipeline.compress(content)
        assert result == content  # below threshold, no compression needed

    def test_token_threshold_trigger(self):
        pipeline = CompressorPipeline(token_threshold=100)
        pipeline.update_metrics(token_count=200)
        assert pipeline.should_trigger()

    def test_token_threshold_not_reached(self):
        pipeline = CompressorPipeline(token_threshold=100)
        pipeline.update_metrics(token_count=50)
        assert not pipeline.should_trigger()

    def test_turn_threshold_trigger(self):
        pipeline = CompressorPipeline(turn_threshold=3)
        for _ in range(4):
            pipeline.update_metrics(turn_count=1)
        assert pipeline.should_trigger()

    def test_introspect_trigger(self):
        pipeline = CompressorPipeline()
        pipeline.signal_introspect()
        assert pipeline.should_trigger()

    def test_introspect_resets_after_check(self):
        pipeline = CompressorPipeline()
        pipeline.signal_introspect()
        assert pipeline.should_trigger()
        assert not pipeline.should_trigger()
