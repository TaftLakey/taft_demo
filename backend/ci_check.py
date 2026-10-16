import os
import tempfile
from pathlib import Path

sqlite_path = Path(tempfile.gettempdir()) / "workflow-ci-check.db"
try:
    sqlite_path.unlink()
except FileNotFoundError:
    pass

os.environ["DATABASE_URL"] = f"sqlite+pysqlite:///{sqlite_path.as_posix()}"
os.environ["OPENAI_API_KEY"] = ""

from fastapi.testclient import TestClient

from app.database import engine
from app.main import app, on_startup

on_startup()
client = TestClient(app)
try:
    health = client.get("/health")
    assert health.status_code == 200, health.text
    assert health.json()["ok"] is True

    created = client.post(
        "/api/projects",
        json={"name": "CI Smoke Project", "description": "Created by CI", "team_member_ids": []},
    )
    assert created.status_code == 200, created.text
    project_id = created.json()["id"]

    projects = client.get("/api/projects")
    assert projects.status_code == 200, projects.text
    assert any(project["id"] == project_id for project in projects.json())
finally:
    client.close()
    engine.dispose()

print("backend smoke check passed")
