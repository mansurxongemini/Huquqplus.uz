from datetime import datetime
from enum import Enum
from sqlalchemy import BigInteger, VARCHAR
from sqlmodel import Field, select
from src.models.base import BaseModel, table_prefix
from src.routes.deps.db_session import DBSession


class BroadcastStatus(str, Enum):
    pending = "pending"
    running = "running"
    paused = "paused"
    completed = "completed"
    cancelled = "cancelled"


class Broadcast(BaseModel, table=True):
    __tablename__ = table_prefix + "broadcasts"

    admin_id: int = Field(sa_type=BigInteger, index=True)
    from_chat_id: int = Field(sa_type=BigInteger)
    message_id: int

    target_filter: str = Field(default="all", sa_type=VARCHAR(100))
    button_text: str | None = Field(default=None, sa_type=VARCHAR(255))
    button_url: str | None = Field(default=None, sa_type=VARCHAR(500))

    total_target: int = Field(default=0)
    sent_count: int = Field(default=0)
    blocked_count: int = Field(default=0)
    failed_count: int = Field(default=0)

    status: BroadcastStatus = Field(default=BroadcastStatus.pending)
    started_at: datetime | None = Field(default=None)
    completed_at: datetime | None = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.now)

    @classmethod
    def get_by_id(cls, broadcast_id: int, session: DBSession) -> "Broadcast | None":
        return session.get(cls, broadcast_id)

    @classmethod
    def get_latest(cls, session: DBSession, limit: int = 5) -> list["Broadcast"]:
        return list(session.exec(select(cls).order_by(cls.created_at.desc()).limit(limit)).all())

    @classmethod
    def get_running_broadcast(cls, session: DBSession) -> "Broadcast | None":
        return session.exec(select(cls).where(cls.status == BroadcastStatus.running)).first()
