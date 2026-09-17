"""Project models for the Jarvis project registry."""

from datetime import UTC, datetime

from pydantic import BaseModel, Field


class Project(BaseModel):
    """Full project representation."""

    id: str
    name: str
    local_path: str
    github_repo: str | None = None
    default_branch: str = "main"
    stack: list[str] = Field(default_factory=list)
    preferred_agent: str | None = None
    deployment: dict[str, str] = Field(default_factory=dict)
    instructions: str = ""
    version: int = 1
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ProjectSummary(BaseModel):
    """Lightweight project representation for list views."""

    id: str
    name: str
    local_path: str
    stack: list[str]
    preferred_agent: str | None
    created_at: datetime


class CreateProjectRequest(BaseModel):
    """Input model for creating a project."""

    name: str = Field(min_length=1, max_length=200)
    local_path: str = Field(min_length=1)
    github_repo: str | None = None
    default_branch: str = "main"
    stack: list[str] = Field(default_factory=list)
    preferred_agent: str | None = None
    deployment: dict[str, str] = Field(default_factory=dict)
    instructions: str = ""


class UpdateProjectRequest(BaseModel):
    """Input model for updating a project. All fields optional."""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    local_path: str | None = Field(default=None, min_length=1)
    github_repo: str | None = None
    default_branch: str | None = None
    stack: list[str] | None = None
    preferred_agent: str | None = None
    deployment: dict[str, str] | None = None
    instructions: str | None = None


class ProjectNotFoundError(Exception):
    """Raised when a project is not found."""

    def __init__(self, project_id: str) -> None:
        self.project_id = project_id
        super().__init__(f"Project not found: {project_id}")
