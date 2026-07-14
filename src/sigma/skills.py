"""Pre-built Skills using the reference Tool implementations.

These Skills can be registered into the framework and used out of the box.
"""

from sigma.skill import ExecutionStep, Skill, ToolRef


def code_review_skill() -> Skill:
    """Review code for quality issues."""
    return Skill(
        id="code-review",
        name="Code Review",
        description="Review code for quality issues — search for patterns and report findings",
        metadata={
            "tags": ["code", "review", "quality", "python"],
            "intent_class": "code_review",
            "applicability_boundary": "Python/TypeScript projects",
        },
        examples=[
            "review this PR for bugs",
            "check this code for style issues",
            "find potential problems in the codebase",
        ],
        tools=[ToolRef(name="search"), ToolRef(name="read")],
        pipeline=[
            ExecutionStep(tool="search", params={
                "glob": "**/*.py",
                "text": "TODO",
            }),
            ExecutionStep(tool="read", params={
                "path": "{{steps[0].path}}",
                "limit": 5000,
            }),
        ],
    )


def project_inspect_skill() -> Skill:
    """Inspect project structure and provide overview."""
    return Skill(
        id="project-inspect",
        name="Project Inspect",
        description="Explore project structure, count files, and generate a summary",
        metadata={
            "tags": ["project", "structure", "overview", "inspect"],
            "intent_class": "project_inspect",
            "applicability_boundary": "Any project directory",
        },
        examples=[
            "what does this project look like",
            "explore the project structure",
            "give me an overview of this codebase",
        ],
        tools=[ToolRef(name="list_dir"), ToolRef(name="search")],
        pipeline=[
            ExecutionStep(tool="list_dir", params={"depth": 2, "hidden": False}),
        ],
    )


def file_edit_skill() -> Skill:
    """Read, edit, or create files in a project."""
    return Skill(
        id="file-edit",
        name="File Edit",
        description="Read, create, or modify files in the project",
        metadata={
            "tags": ["file", "edit", "read", "write", "create"],
            "intent_class": "file_edit",
            "applicability_boundary": "Local filesystem",
        },
        examples=[
            "create a new file called README.md",
            "update the config file",
            "show me the contents of main.py",
        ],
        tools=[ToolRef(name="read"), ToolRef(name="write"), ToolRef(name="list_dir")],
        pipeline=[
            ExecutionStep(tool="read", params={"path": "{{path}}"}),
        ],
    )


def shell_exec_skill() -> Skill:
    """Execute shell commands and scripts."""
    return Skill(
        id="shell-exec",
        name="Shell Execute",
        description="Run shell commands, scripts, and capture results",
        metadata={
            "tags": ["shell", "command", "script", "run", "terminal"],
            "intent_class": "shell_exec",
            "applicability_boundary": "Shell commands — use with caution",
        },
        examples=[
            "run npm install",
            "check disk usage",
            "list running processes",
        ],
        tools=[ToolRef(name="shell")],
        pipeline=[
            ExecutionStep(tool="shell", params={"command": "{{command}}"}),
        ],
    )


# Registry of all example Skills for bulk registration
EXAMPLE_SKILLS: list[Skill] = [
    code_review_skill(),
    project_inspect_skill(),
    file_edit_skill(),
    shell_exec_skill(),
]
