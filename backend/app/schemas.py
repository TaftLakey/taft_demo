from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

Status = Literal["backlog", "selected", "in_progress", "blocked", "done"]
Priority = Literal["low", "medium", "high", "urgent"]
SprintStatus = Literal["planned", "active", "closed"]


class UserRead(BaseModel):
    id: str
    name: str
    email: str

    model_config = {"from_attributes": True}


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str = ""
    team_member_ids: list[str] = []


class ProjectRead(BaseModel):
    id: str
    name: str
    description: str
    owner_id: str
    created_at: datetime
    members: list[UserRead] = []

    model_config = {"from_attributes": True}


class TeamMemberUpdate(BaseModel):
    user_id: str
    role: str = "member"


class SprintCreate(BaseModel):
    name: str | None = None
    goal: str = ""
    start_date: date | None = None
    end_date: date | None = None
    status: SprintStatus = "active"


class SprintUpdate(BaseModel):
    name: str | None = None
    goal: str | None = None
    status: SprintStatus | None = None
    start_date: date | None = None
    end_date: date | None = None


class SprintRead(BaseModel):
    id: str
    project_id: str
    name: str
    goal: str
    status: str
    start_date: date | None
    end_date: date | None
    closed_at: datetime | None
    velocity: int | None
    notes: str
    created_at: datetime

    model_config = {"from_attributes": True}


class StoryCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str = ""
    acceptance_criteria: str = ""
    priority: Priority = "medium"
    story_points: int | None = Field(default=None, ge=1)
    assignee_id: str | None = None
    due_date: date | None = None


class StoryUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    acceptance_criteria: str | None = None
    status: Status | None = None
    priority: Priority | None = None
    story_points: int | None = Field(default=None, ge=1)
    assignee_id: str | None = None
    due_date: date | None = None
    sprint_id: str | None = None


class StorySummary(BaseModel):
    id: str
    project_id: str
    sprint_id: str | None
    parent_story_id: str | None
    title: str
    status: str
    priority: str
    story_points: int | None
    assignee_id: str | None
    due_date: date | None
    blocked_by: list[str] = []

    model_config = {"from_attributes": True}


class CommentCreate(BaseModel):
    text: str = Field(min_length=1, max_length=5000)


class CommentRead(BaseModel):
    id: str
    story_id: str
    author_id: str
    text: str
    created_at: datetime

    model_config = {"from_attributes": True}


class DependencyCreate(BaseModel):
    reason: str = ""


class DependencyRead(BaseModel):
    id: str
    blocker_story_id: str
    blocked_story_id: str
    reason: str
    created_at: datetime

    model_config = {"from_attributes": True}


class StoryDetail(StorySummary):
    description: str
    acceptance_criteria: str
    created_at: datetime
    updated_at: datetime
    subtasks: list[StorySummary] = []
    comments: list[CommentRead] = []
    blocks: list[DependencyRead] = []
    blocked_by_links: list[DependencyRead] = []

    model_config = {"from_attributes": True}


class AssignStoryToSprint(BaseModel):
    sprint_id: str | None
    status: Status = "selected"


class SprintClose(BaseModel):
    notes: str = ""


class ReportDraftRequest(BaseModel):
    additional_context: str = ""


class ReportSave(BaseModel):
    final_content: str = Field(min_length=1)


class ReportRead(BaseModel):
    id: str
    sprint_id: str
    ai_draft: str
    final_content: str | None
    generated_at: datetime
    finalized_at: datetime | None
    finalized_by_id: str | None

    model_config = {"from_attributes": True}
