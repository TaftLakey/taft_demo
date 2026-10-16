import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:10]}"


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)

    comments: Mapped[list["Comment"]] = relationship(back_populates="author")


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("proj"))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    owner: Mapped[User] = relationship()
    members: Mapped[list["ProjectMember"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    stories: Mapped[list["Story"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    sprints: Mapped[list["Sprint"]] = relationship(back_populates="project", cascade="all, delete-orphan")


class ProjectMember(Base):
    __tablename__ = "project_members"
    __table_args__ = (UniqueConstraint("project_id", "user_id", name="uq_project_member"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("member"))
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(64), default="member")

    project: Mapped[Project] = relationship(back_populates="members")
    user: Mapped[User] = relationship()


class Sprint(Base):
    __tablename__ = "sprints"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("sprint"))
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    goal: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32), default="planned")
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    velocity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    project: Mapped[Project] = relationship(back_populates="sprints")
    stories: Mapped[list["Story"]] = relationship(back_populates="sprint")
    report: Mapped["SprintReport | None"] = relationship(back_populates="sprint", cascade="all, delete-orphan")


class Story(Base):
    __tablename__ = "stories"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("story"))
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False)
    sprint_id: Mapped[str | None] = mapped_column(ForeignKey("sprints.id"), nullable=True)
    parent_story_id: Mapped[str | None] = mapped_column(ForeignKey("stories.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    acceptance_criteria: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32), default="backlog")
    priority: Mapped[str] = mapped_column(String(32), default="medium")
    story_points: Mapped[int | None] = mapped_column(Integer, nullable=True)
    assignee_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    project: Mapped[Project] = relationship(back_populates="stories")
    sprint: Mapped[Sprint | None] = relationship(back_populates="stories")
    parent: Mapped["Story | None"] = relationship(remote_side=[id], back_populates="subtasks")
    subtasks: Mapped[list["Story"]] = relationship(back_populates="parent")
    assignee: Mapped[User | None] = relationship()
    comments: Mapped[list["Comment"]] = relationship(back_populates="story", cascade="all, delete-orphan")
    blocks: Mapped[list["Dependency"]] = relationship(
        foreign_keys="Dependency.blocker_story_id",
        back_populates="blocker",
        cascade="all, delete-orphan",
    )
    blocked_by_links: Mapped[list["Dependency"]] = relationship(
        foreign_keys="Dependency.blocked_story_id",
        back_populates="blocked",
        cascade="all, delete-orphan",
    )


class Dependency(Base):
    __tablename__ = "dependencies"
    __table_args__ = (UniqueConstraint("blocker_story_id", "blocked_story_id", name="uq_dependency_pair"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("block"))
    blocker_story_id: Mapped[str] = mapped_column(ForeignKey("stories.id"), nullable=False)
    blocked_story_id: Mapped[str] = mapped_column(ForeignKey("stories.id"), nullable=False)
    reason: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    blocker: Mapped[Story] = relationship(foreign_keys=[blocker_story_id], back_populates="blocks")
    blocked: Mapped[Story] = relationship(foreign_keys=[blocked_story_id], back_populates="blocked_by_links")


class Comment(Base):
    __tablename__ = "comments"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("comment"))
    story_id: Mapped[str] = mapped_column(ForeignKey("stories.id"), nullable=False)
    author_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    story: Mapped[Story] = relationship(back_populates="comments")
    author: Mapped[User] = relationship(back_populates="comments")


class SprintReport(Base):
    __tablename__ = "sprint_reports"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("report"))
    sprint_id: Mapped[str] = mapped_column(ForeignKey("sprints.id"), nullable=False, unique=True)
    ai_draft: Mapped[str] = mapped_column(Text, nullable=False)
    final_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finalized_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    sprint: Mapped[Sprint] = relationship(back_populates="report")
    finalized_by: Mapped[User | None] = relationship()
