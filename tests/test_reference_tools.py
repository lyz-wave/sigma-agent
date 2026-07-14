"""Tests for reference Tool implementations."""

import tempfile
from pathlib import Path

import pytest
from sigma.executor import ToolResult
from sigma.tools.filesystem import ListDirectory, ReadFile, SearchFiles, ShellCommand, WriteFile


class TestFileTools:
    """Reference Tool: file read/write/search/list operations."""

    @pytest.fixture
    def workdir(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            (base / "hello.txt").write_text("hello world")
            (base / "sub").mkdir()
            (base / "sub" / "nested.py").write_text("print('hello')")
            yield base

    def test_read_existing_file(self, workdir):
        tool = ReadFile()
        result = tool.execute({"path": str(workdir / "hello.txt")})
        assert result.success is True
        assert "hello world" in result.output

    def test_read_nonexistent_file(self):
        tool = ReadFile()
        result = tool.execute({"path": "/nonexistent/file.txt"})
        assert result.success is False

    def test_write_new_file(self, workdir):
        tool = WriteFile()
        result = tool.execute({
            "path": str(workdir / "new.txt"),
            "content": "fresh content",
        })
        assert result.success is True
        assert (workdir / "new.txt").read_text() == "fresh content"

    def test_search_by_content(self, workdir):
        tool = SearchFiles()
        result = tool.execute({"root": str(workdir), "text": "hello", "glob": "**/*"})
        assert result.success is True
        assert "hello.txt" in result.output

    def test_search_by_pattern(self, workdir):
        tool = SearchFiles()
        result = tool.execute({"root": str(workdir), "pattern": "*.py", "glob": "**/*"})
        assert result.success is True
        assert "nested.py" in result.output

    def test_search_no_match(self, workdir):
        tool = SearchFiles()
        result = tool.execute({"root": str(workdir), "text": "zzz_nonexistent_zzz"})
        assert result.success is True
        assert "No matches" in result.output

    def test_list_directory(self, workdir):
        tool = ListDirectory()
        result = tool.execute({"path": str(workdir), "depth": 2})
        assert result.success is True
        assert "hello.txt" in result.output
        assert "sub/" in result.output

    def test_list_nonexistent(self):
        tool = ListDirectory()
        result = tool.execute({"path": "/nonexistent_path_xyz"})
        assert result.success is False

    def test_shell_command(self):
        tool = ShellCommand()
        result = tool.execute({"command": "echo hello_sigma"})
        assert result.success is True
        assert "hello_sigma" in result.output

    def test_shell_failing_command(self):
        tool = ShellCommand()
        result = tool.execute({"command": "exit 1"})
        assert result.success is False


class TestSkills:
    """Verify pre-built Skills have valid structure."""

    def test_code_review_skill_structure(self):
        from sigma.skills import code_review_skill
        skill = code_review_skill()
        assert skill.id == "code-review"
        assert len(skill.pipeline) > 0
        assert "review" in skill.metadata["tags"]

    def test_all_example_skills_valid(self):
        from sigma.skills import EXAMPLE_SKILLS
        for skill in EXAMPLE_SKILLS:
            assert skill.id
            assert skill.name
            assert skill.metadata
            assert len(skill.pipeline) >= 1

    def test_register_and_route_example_skills(self):
        from sigma.registry import SkillRegistry
        from sigma.router import Router
        from sigma.skills import EXAMPLE_SKILLS

        registry = SkillRegistry()
        for skill in EXAMPLE_SKILLS:
            registry.register(skill)
        assert len(registry.discover()) == len(EXAMPLE_SKILLS)

        router = Router(registry)
        result = router.route(intent_class="code_review", tags=[])
        assert result.selected is not None
        assert result.selected.id == "code-review"

    def test_route_by_tags(self):
        from sigma.registry import SkillRegistry
        from sigma.router import Router
        from sigma.skills import EXAMPLE_SKILLS

        registry = SkillRegistry()
        for skill in EXAMPLE_SKILLS:
            registry.register(skill)

        router = Router(registry)
        result = router.route(intent_class="", tags=["project"])
        assert result.selected is not None
        assert result.selected.id == "project-inspect"
