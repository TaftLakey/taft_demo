from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from .config import settings
from .database import get_db
from .models import ProjectMember, User


def get_current_user(
    db: Session = Depends(get_db),
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
) -> User:
    user_id = x_user_id or settings.default_user_id
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=401, detail="Unknown user")
    return user


def ensure_project_member(db: Session, project_id: str, user: User) -> None:
    member = (
        db.query(ProjectMember)
        .filter(ProjectMember.project_id == project_id, ProjectMember.user_id == user.id)
        .first()
    )
    if not member:
        raise HTTPException(status_code=403, detail="User is not a member of this project")
