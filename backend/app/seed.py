from sqlalchemy.orm import Session

from .models import Project, ProjectMember, Sprint, Story, User


def seed_defaults(db: Session) -> None:
    users = [
        User(id="user-001", name="Taylor Lead", email="taylor@example.edu"),
        User(id="user-002", name="Jordan Dev", email="jordan@example.edu"),
        User(id="user-003", name="Casey QA", email="casey@example.edu"),
        User(id="user-004", name="Morgan PM", email="morgan@example.edu"),
    ]
    for user in users:
        if not db.get(User, user.id):
            db.add(user)
    db.commit()

    if db.query(Project).count() > 0:
        return

    project = Project(
        name="Capstone Workflow Build",
        description="Demo project seeded for the Engineering Workflow Manager MVP.",
        owner_id="user-001",
    )
    db.add(project)
    db.flush()

    for user in users:
        db.add(ProjectMember(project_id=project.id, user_id=user.id, role="owner" if user.id == "user-001" else "member"))

    sprint = Sprint(
        project_id=project.id,
        name="Sprint 1",
        goal="Build the planning board, backend API, and sprint report flow.",
        status="active",
    )
    db.add(sprint)
    db.flush()

    stories = [
        Story(
            project_id=project.id,
            sprint_id=sprint.id,
            title="Implement sprint board UI",
            description="Create a Kanban-style board with drag-and-drop status transitions.",
            acceptance_criteria="Board shows all five status columns and supports status updates.",
            status="in_progress",
            priority="high",
            story_points=8,
            assignee_id="user-002",
        ),
        Story(
            project_id=project.id,
            sprint_id=sprint.id,
            title="Set up FastAPI backend",
            description="Create project, story, sprint, dependency, comment, and report endpoints.",
            acceptance_criteria="Core API endpoints return JSON and persist to PostgreSQL.",
            status="selected",
            priority="high",
            story_points=5,
            assignee_id="user-001",
        ),
        Story(
            project_id=project.id,
            sprint_id=sprint.id,
            title="Generate AI sprint report",
            description="Use sprint data to draft a stakeholder-ready report.",
            acceptance_criteria="Closed sprints can generate and save an editable report.",
            status="blocked",
            priority="medium",
            story_points=5,
            assignee_id="user-004",
        ),
        Story(
            project_id=project.id,
            sprint_id=sprint.id,
            title="Design database schema",
            description="Model users, projects, sprints, stories, comments, dependencies, and reports.",
            acceptance_criteria="Schema supports sprint history and dependency tracking.",
            status="done",
            priority="high",
            story_points=3,
            assignee_id="user-003",
        ),
        Story(
            project_id=project.id,
            title="Write API tests",
            description="Add coverage for board transitions, sprint closure, and report generation.",
            acceptance_criteria="Key workflow behavior has automated tests.",
            status="backlog",
            priority="medium",
            story_points=3,
            assignee_id="user-003",
        ),
    ]
    db.add_all(stories)
    db.commit()
