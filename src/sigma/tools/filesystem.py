"""Shell and filesystem tools for code-related tasks."""

import fnmatch
import os
import re
import subprocess
from pathlib import Path

from sigma.executor import Tool, ToolResult


class ShellCommand(Tool):
    """Execute a shell command and capture output."""

    def execute(self, params: dict) -> ToolResult:
        command = params.get("command", "")
        cwd = params.get("cwd") or os.getcwd()
        timeout = params.get("timeout", 30)

        if not command:
            return ToolResult(success=False, error="No command specified")

        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                cwd=cwd,
                timeout=timeout,
            )
            output = result.stdout or ""
            if result.stderr:
                output += f"\n[stderr]\n{result.stderr[:2000]}"
            if result.returncode != 0:
                return ToolResult(
                    success=False,
                    output=output[:3000],
                    error=f"Exit code {result.returncode}: {result.stderr[:500]}",
                )
            return ToolResult(success=True, output=output[:3000])
        except subprocess.TimeoutExpired:
            return ToolResult(success=False, error=f"Command timed out after {timeout}s")
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class ReadFile(Tool):
    """Read a file's contents."""

    def execute(self, params: dict) -> ToolResult:
        path = Path(params.get("path", ""))
        encoding = params.get("encoding", "utf-8")
        limit = params.get("limit", 0)  # 0 = no limit

        if not path.exists():
            return ToolResult(success=False, error=f"File not found: {path}")
        if not path.is_file():
            return ToolResult(success=False, error=f"Not a file: {path}")

        try:
            content = path.read_text(encoding=encoding)
            if limit > 0 and len(content) > limit:
                content = content[:limit] + f"\n... [truncated at {limit} chars]"
            return ToolResult(success=True, output=content)
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class WriteFile(Tool):
    """Write content to a file."""

    def execute(self, params: dict) -> ToolResult:
        path = Path(params.get("path", ""))
        content = params.get("content", "")
        mode = params.get("mode", "w")  # w = overwrite, a = append

        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, mode, encoding="utf-8") as f:
                f.write(content)
            return ToolResult(success=True, output=f"Written {len(content)} bytes to {path}")
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class SearchFiles(Tool):
    """Search files by name pattern or text content."""

    def execute(self, params: dict) -> ToolResult:
        root = Path(params.get("root") or os.getcwd())
        pattern = params.get("pattern", "")
        search_text = params.get("text", "")
        glob_pattern = params.get("glob", "**/*")

        if not pattern and not search_text:
            return ToolResult(success=False, error="Specify 'pattern' (filename) or 'text' (content)")

        results = []

        try:
            for filepath in root.glob(glob_pattern):
                if not filepath.is_file():
                    continue
                rel = filepath.relative_to(root)

                # Filter by filename pattern
                if pattern and not fnmatch.fnmatch(filepath.name, pattern):
                    continue

                # Filter by text content
                if search_text:
                    try:
                        content = filepath.read_text(encoding="utf-8", errors="ignore")
                        for i, line in enumerate(content.splitlines(), 1):
                            if search_text in line:
                                results.append(f"{rel}:{i}: {line.strip()[:120]}")
                    except Exception:
                        continue
                else:
                    results.append(str(rel))

                if len(results) > 50:
                    results.append(f"... {len(results)}+ results, refine your search")
                    break

            if not results:
                return ToolResult(success=True, output="No matches found")
            return ToolResult(success=True, output="\n".join(results[:60]))
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class ListDirectory(Tool):
    """List files and directories."""

    def execute(self, params: dict) -> ToolResult:
        path = Path(params.get("path") or os.getcwd())
        depth = params.get("depth", 1)
        show_hidden = params.get("hidden", False)

        if not path.exists():
            return ToolResult(success=False, error=f"Path not found: {path}")
        if not path.is_dir():
            return ToolResult(success=False, error=f"Not a directory: {path}")

        try:
            lines = [f"{path}/"] if depth > 0 else []
            self._walk(path, path, depth, show_hidden, lines, "")
            return ToolResult(success=True, output="\n".join(lines[:100]))
        except Exception as e:
            return ToolResult(success=False, error=str(e))

    def _walk(self, root, current, depth, show_hidden, lines, prefix):
        if depth <= 0:
            return
        try:
            entries = sorted(current.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        except PermissionError:
            return

        for i, entry in enumerate(entries):
            if not show_hidden and entry.name.startswith("."):
                continue
            is_last = i == len(entries) - 1
            connector = "└── " if is_last else "├── "
            rel = entry.relative_to(root) if root != entry else entry.name
            if entry.is_dir():
                lines.append(f"{prefix}{connector}{rel}/")
                self._walk(root, entry, depth - 1, show_hidden, lines, prefix + ("    " if is_last else "│   "))
            else:
                lines.append(f"{prefix}{connector}{rel}")
