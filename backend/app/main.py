from collections import Counter
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import or_, text
from sqlalchemy.orm import Session, selectinload

from .ai import generate_sprint_report
from .auth import ensure_project_member, get_current_user
from .config import settings
from .database import Base, SessionLocal, engine, get_db
from .models import Comment, Dependency, Project, ProjectMember, Sprint, SprintReport, Story, User
from .schemas import (
    AssignStoryToSprint,
    CommentCreate,
    CommentRead,
    DependencyRead,
    DependencyCreate,
    ProjectCreate,
    ProjectRead,
    ReportDraftRequest,
    ReportRead,
    ReportSave,
    SprintClose,
    SprintCreate,
    SprintRead,
    SprintUpdate,
    StoryCreate,
    StoryDetail,
    StorySummary,
    StoryUpdate,
    TeamMemberUpdate,
    UserRead,
)
from .seed import seed_defaults

STATUSES = ["backlog", "selected", "in_progress", "blocked", "done"]

app = FastAPI(title=settings.app_name)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin, "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed_defaults(db)


def story_summary(story: Story) -> StorySummary:
    data = StorySummary.model_validate(story)
    data.blocked_by = [link.blocker_story_id for link in story.blocked_by_links]
    return data


def project_read(project: Project) -> ProjectRead:
    members = [member.user for member in project.members]
    return ProjectRead(
        id=project.id,
        name=project.name,
        description=project.description,
        owner_id=project.owner_id,
        created_at=project.created_at,
        members=[UserRead.model_validate(member) for member in members],
    )


def get_story_for_user(db: Session, story_id: str, user: User) -> Story:
    story = (
        db.query(Story)
        .options(
            selectinload(Story.subtasks).selectinload(Story.blocked_by_links),
            selectinload(Story.comments),
            selectinload(Story.blocks),
            selectinload(Story.blocked_by_links),
        )
        .filter(Story.id == story_id)
        .first()
    )
    if not story:
        raise HTTPException(status_code=404, detail="Story not found")
    ensure_project_member(db, story.project_id, user)
    return story


def ensure_story_editable(story: Story) -> None:
    if story.sprint and story.sprint.status == "closed":
        raise HTTPException(status_code=400, detail="Sprint is closed")


def ensure_assignee_is_member(db: Session, project_id: str, assignee_id: str | None) -> None:
    if not assignee_id:
        return
    member = db.query(ProjectMember).filter_by(project_id=project_id, user_id=assignee_id).first()
    if not member:
        raise HTTPException(status_code=400, detail="Assignee must be a project member")


@app.get("/health")
@app.get("/api/health")
def health(db: Session = Depends(get_db)) -> dict[str, object]:
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"database unreachable: {exc}") from exc
    return {"ok": True, "service": settings.app_name}


@app.get("/api/users", response_model=list[UserRead])
def list_users(db: Session = Depends(get_db)) -> list[User]:
    return db.query(User).order_by(User.name).all()


@app.get("/api/projects", response_model=list[ProjectRead])
def list_projects(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[ProjectRead]:
    projects = (
        db.query(Project)
        .join(ProjectMember)
        .options(selectinload(Project.members).selectinload(ProjectMember.user))
        .filter(ProjectMember.user_id == user.id)
        .order_by(Project.created_at.desc())
        .all()
    )
    return [project_read(project) for project in projects]


@app.post("/api/projects", response_model=ProjectRead)
def create_project(payload: ProjectCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> ProjectRead:
    project = Project(name=payload.name, description=payload.description, owner_id=user.id)
    db.add(project)
    db.flush()
    member_ids = {user.id, *payload.team_member_ids}
    for member_id in member_ids:
        if not db.get(User, member_id):
            raise HTTPException(status_code=400, detail=f"Unknown team member: {member_id}")
        db.add(ProjectMember(project_id=project.id, user_id=member_id, role="owner" if member_id == user.id else "member"))
    db.commit()
    db.refresh(project)
    project = db.query(Project).options(selectinload(Project.members).selectinload(ProjectMember.user)).get(project.id)
    return project_read(project)


@app.get("/api/projects/{project_id}", response_model=ProjectRead)
def get_project(project_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> ProjectRead:
    project = db.query(Project).options(selectinload(Project.members).selectinload(ProjectMember.user)).get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    ensure_project_member(db, project_id, user)
    return project_read(project)


@app.post("/api/projects/{project_id}/team", response_model=ProjectRead)
def add_team_member(
    project_id: str,
    payload: TeamMemberUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ProjectRead:
    project = db.query(Project).options(selectinload(Project.members).selectinload(ProjectMember.user)).get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    ensure_project_member(db, project_id, user)
    if not db.get(User, payload.user_id):
        raise HTTPException(status_code=400, detail="Unknown user")
    exists = db.query(ProjectMember).filter_by(project_id=project_id, user_id=payload.user_id).first()
    if not exists:
        db.add(ProjectMember(project_id=project_id, user_id=payload.user_id, role=payload.role))
        db.commit()
    db.refresh(project)
    return project_read(project)


@app.get("/api/projects/{project_id}/summary")
def project_summary(project_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    if not db.get(Project, project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    ensure_project_member(db, project_id, user)
    stories = db.query(Story).filter(Story.project_id == project_id).all()
    counts = Counter(story.status for story in stories)
    active = db.query(Sprint).filter_by(project_id=project_id, status="active").first()
    return {
        "counts": {status: counts.get(status, 0) for status in STATUSES},
        "total_stories": len(stories),
        "active_sprint": SprintRead.model_validate(active) if active else None,
    }


@app.get("/api/projects/{project_id}/velocity")
def project_velocity(project_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    if not db.get(Project, project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    ensure_project_member(db, project_id, user)
    sprints = (
        db.query(Sprint)
        .filter(Sprint.project_id == project_id, Sprint.status == "closed")
        .order_by(Sprint.closed_at.desc())
        .limit(6)
        .all()
    )
    return {
        "sprints": [
            {
                "id": sprint.id,
                "name": sprint.name,
                "velocity": sprint.velocity or 0,
                "closed_at": sprint.closed_at,
            }
            for sprint in reversed(sprints)
        ]
    }


@app.post("/api/projects/{project_id}/stories", response_model=StorySummary)
def create_story(project_id: str, payload: StoryCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> StorySummary:
    if not db.get(Project, project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    ensure_project_member(db, project_id, user)
    ensure_assignee_is_member(db, project_id, payload.assignee_id)
    story = Story(project_id=project_id, **payload.model_dump())
    db.add(story)
    db.commit()
    db.refresh(story)
    return story_summary(story)


@app.get("/api/projects/{project_id}/stories", response_model=list[StorySummary])
def list_stories(project_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[StorySummary]:
    if not db.get(Project, project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    ensure_project_member(db, project_id, user)
    stories = (
        db.query(Story)
        .options(selectinload(Story.blocked_by_links))
        .filter(Story.project_id == project_id)
        .order_by(Story.created_at.desc())
        .all()
    )
    return [story_summary(story) for story in stories]


@app.get("/api/stories/{story_id}", response_model=StoryDetail)
def get_story(story_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> StoryDetail:
    story = get_story_for_user(db, story_id, user)
    detail = StoryDetail.model_validate(story)
    detail.blocked_by = [link.blocker_story_id for link in story.blocked_by_links]
    detail.subtasks = [story_summary(subtask) for subtask in story.subtasks]
    return detail


@app.put("/api/stories/{story_id}", response_model=StorySummary)
def update_story(story_id: str, payload: StoryUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> StorySummary:
    story = get_story_for_user(db, story_id, user)
    ensure_story_editable(story)
    data = payload.model_dump(exclude_unset=True)

    if "assignee_id" in data:
        ensure_assignee_is_member(db, story.project_id, data["assignee_id"])

    if "sprint_id" in data and data["sprint_id"]:
        sprint = db.get(Sprint, data["sprint_id"])
        if not sprint:
            raise HTTPException(status_code=404, detail="Sprint not found")
        if sprint.project_id != story.project_id:
            raise HTTPException(status_code=400, detail="Sprint and story are in different projects")
        if sprint.status == "closed":
            raise HTTPException(status_code=400, detail="Sprint is closed")

    new_status = data.get("status")
    if story.status == "blocked" and new_status and new_status != "blocked" and story.blocked_by_links:
        raise HTTPException(status_code=400, detail="Story is blocked and cannot move until blockers are removed")

    for key, value in data.items():
        setattr(story, key, value)
    db.commit()
    db.refresh(story)
    return story_summary(story)


@app.post("/api/stories/{story_id}/subtasks", response_model=StorySummary)
def create_subtask(story_id: str, payload: StoryCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> StorySummary:
    parent = get_story_for_user(db, story_id, user)
    ensure_story_editable(parent)
    ensure_assignee_is_member(db, parent.project_id, payload.assignee_id)
    subtask = Story(
        project_id=parent.project_id,
        sprint_id=parent.sprint_id,
        parent_story_id=parent.id,
        **payload.model_dump(),
    )
    db.add(subtask)
    db.commit()
    db.refresh(subtask)
    return story_summary(subtask)


@app.post("/api/stories/{story_id}/blocks/{target_story_id}", response_model=DependencyRead)
def create_dependency(
    story_id: str,
    target_story_id: str,
    payload: DependencyCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Dependency:
    blocker = get_story_for_user(db, story_id, user)
    blocked = get_story_for_user(db, target_story_id, user)
    if blocker.id == blocked.id:
        raise HTTPException(status_code=400, detail="A story cannot block itself")
    if blocker.project_id != blocked.project_id:
        raise HTTPException(status_code=400, detail="Stories are in different projects")
    dependency = Dependency(blocker_story_id=blocker.id, blocked_story_id=blocked.id, reason=payload.reason)
    blocked.status = "blocked"
    db.add(dependency)
    db.commit()
    db.refresh(dependency)
    return dependency


@app.delete("/api/stories/{story_id}/blocks/{target_story_id}")
def delete_dependency(story_id: str, target_story_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    blocker = get_story_for_user(db, story_id, user)
    blocked = get_story_for_user(db, target_story_id, user)
    dependency = db.query(Dependency).filter_by(blocker_story_id=blocker.id, blocked_story_id=blocked.id).first()
    if not dependency:
        raise HTTPException(status_code=404, detail="Blocking relationship not found")
    db.delete(dependency)
    db.commit()
    return {"success": True, "message": "Blocking relationship removed"}


@app.post("/api/stories/{story_id}/comments", response_model=CommentRead)
def create_comment(story_id: str, payload: CommentCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> Comment:
    story = get_story_for_user(db, story_id, user)
    comment = Comment(story_id=story.id, author_id=user.id, text=payload.text)
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return comment


@app.post("/api/projects/{project_id}/sprints", response_model=SprintRead)
def create_sprint(project_id: str, payload: SprintCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> Sprint:
    if not db.get(Project, project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    ensure_project_member(db, project_id, user)
    if payload.status == "active" and db.query(Sprint).filter_by(project_id=project_id, status="active").first():
        raise HTTPException(status_code=400, detail="Project already has an active sprint")
    count = db.query(Sprint).filter_by(project_id=project_id).count()
    sprint = Sprint(
        project_id=project_id,
        name=payload.name or f"Sprint {count + 1}",
        goal=payload.goal,
        status=payload.status,
        start_date=payload.start_date,
        end_date=payload.end_date,
    )
    db.add(sprint)
    db.commit()
    db.refresh(sprint)
    return sprint


@app.get("/api/projects/{project_id}/sprints", response_model=list[SprintRead])
def list_sprints(project_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[Sprint]:
    if not db.get(Project, project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    ensure_project_member(db, project_id, user)
    return db.query(Sprint).filter_by(project_id=project_id).order_by(Sprint.created_at.desc()).all()


@app.get("/api/sprints/{sprint_id}", response_model=SprintRead)
def get_sprint(sprint_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> Sprint:
    sprint = db.get(Sprint, sprint_id)
    if not sprint:
        raise HTTPException(status_code=404, detail="Sprint not found")
    ensure_project_member(db, sprint.project_id, user)
    return sprint


@app.put("/api/sprints/{sprint_id}", response_model=SprintRead)
def update_sprint(sprint_id: str, payload: SprintUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> Sprint:
    sprint = db.get(Sprint, sprint_id)
    if not sprint:
        raise HTTPException(status_code=404, detail="Sprint not found")
    ensure_project_member(db, sprint.project_id, user)
    if sprint.status == "closed":
        raise HTTPException(status_code=400, detail="Sprint is closed")
    data = payload.model_dump(exclude_unset=True)
    if data.get("status") == "active":
        active = db.query(Sprint).filter(Sprint.project_id == sprint.project_id, Sprint.status == "active", Sprint.id != sprint.id).first()
        if active:
            raise HTTPException(status_code=400, detail="Project already has an active sprint")
    for key, value in data.items():
        setattr(sprint, key, value)
    db.commit()
    db.refresh(sprint)
    return sprint


@app.get("/api/sprints/{sprint_id}/board")
def get_board(sprint_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    sprint = db.get(Sprint, sprint_id)
    if not sprint:
        raise HTTPException(status_code=404, detail="Sprint not found")
    ensure_project_member(db, sprint.project_id, user)
    stories = (
        db.query(Story)
        .options(selectinload(Story.blocked_by_links))
        .filter(or_(Story.sprint_id == sprint.id, Story.project_id == sprint.project_id, Story.sprint_id.is_(None)))
        .all()
    )
    columns = {status: [] for status in STATUSES}
    for story in stories:
        if story.sprint_id == sprint.id or story.status == "backlog":
            columns[story.status].append(story_summary(story).model_dump(mode="json"))
    return {"sprint_id": sprint.id, "columns": columns}


@app.put("/api/sprints/{sprint_id}/stories/{story_id}", response_model=StorySummary)
def assign_story_to_sprint(
    sprint_id: str,
    story_id: str,
    payload: AssignStoryToSprint,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> StorySummary:
    sprint = db.get(Sprint, sprint_id)
    if not sprint:
        raise HTTPException(status_code=404, detail="Sprint not found")
    if sprint.status == "closed":
        raise HTTPException(status_code=400, detail="Sprint is closed")
    story = get_story_for_user(db, story_id, user)
    if story.project_id != sprint.project_id:
        raise HTTPException(status_code=400, detail="Sprint and story are in different projects")
    story.sprint_id = payload.sprint_id
    story.status = payload.status
    db.commit()
    db.refresh(story)
    return story_summary(story)


@app.post("/api/sprints/{sprint_id}/close")
def close_sprint(sprint_id: str, payload: SprintClose, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    sprint = db.get(Sprint, sprint_id)
    if not sprint:
        raise HTTPException(status_code=404, detail="Sprint not found")
    ensure_project_member(db, sprint.project_id, user)
    if sprint.status == "closed":
        raise HTTPException(status_code=400, detail="Sprint is already closed")
    stories = db.query(Story).filter(Story.sprint_id == sprint.id, Story.parent_story_id.is_(None)).all()
    done = [story for story in stories if story.status == "done"]
    points = [story.story_points for story in done if story.story_points]
    sprint.velocity = sum(points) if points else len(done)
    sprint.status = "closed"
    sprint.notes = payload.notes
    sprint.closed_at = datetime.now(timezone.utc)
    db.commit()
    return {
        "id": sprint.id,
        "status": sprint.status,
        "closed_at": sprint.closed_at,
        "velocity": sprint.velocity,
        "completed_stories": len(done),
        "incomplete_stories": len(stories) - len(done),
    }


@app.post("/api/sprints/{sprint_id}/report/draft", response_model=ReportRead)
def draft_report(
    sprint_id: str,
    payload: ReportDraftRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SprintReport:
    sprint = db.get(Sprint, sprint_id)
    if not sprint:
        raise HTTPException(status_code=404, detail="Sprint not found")
    ensure_project_member(db, sprint.project_id, user)
    if sprint.status != "closed":
        raise HTTPException(status_code=400, detail="Sprint must be closed before generating a report")
    stories = (
        db.query(Story)
        .options(selectinload(Story.blocked_by_links))
        .filter(Story.sprint_id == sprint.id)
        .order_by(Story.created_at)
        .all()
    )
    draft = generate_sprint_report(sprint, stories, payload.additional_context)
    report = db.query(SprintReport).filter_by(sprint_id=sprint.id).first()
    if report:
        report.ai_draft = draft
        report.final_content = None
        report.finalized_at = None
        report.finalized_by_id = None
    else:
        report = SprintReport(sprint_id=sprint.id, ai_draft=draft)
        db.add(report)
    db.commit()
    db.refresh(report)
    return report


@app.put("/api/sprints/{sprint_id}/report", response_model=ReportRead)
def save_report(sprint_id: str, payload: ReportSave, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> SprintReport:
    sprint = db.get(Sprint, sprint_id)
    if not sprint:
        raise HTTPException(status_code=404, detail="Sprint not found")
    ensure_project_member(db, sprint.project_id, user)
    report = db.query(SprintReport).filter_by(sprint_id=sprint.id).first()
    if not report:
        raise HTTPException(status_code=400, detail="No report draft exists for this sprint")
    report.final_content = payload.final_content
    report.finalized_at = datetime.now(timezone.utc)
    report.finalized_by_id = user.id
    db.commit()
    db.refresh(report)
    return report


@app.get("/api/sprints/{sprint_id}/report", response_model=ReportRead)
def get_report(sprint_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> SprintReport:
    sprint = db.get(Sprint, sprint_id)
    if not sprint:
        raise HTTPException(status_code=404, detail="Sprint not found")
    ensure_project_member(db, sprint.project_id, user)
    report = db.query(SprintReport).filter_by(sprint_id=sprint.id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return report


