from sqlalchemy import Column, DateTime, ForeignKey, Integer
from sqlalchemy.sql import func

from app.db.database import Base


class AdminSession(Base):
    """Persist authenticated admins across API process restarts."""

    __tablename__ = "admin_sessions"

    admin_id = Column(
        Integer,
        ForeignKey("admins.admin_id", ondelete="CASCADE"),
        primary_key=True,
    )
    created_at = Column(DateTime, nullable=False, server_default=func.now())
