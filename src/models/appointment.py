from datetime import datetime
from enum import Enum
from sqlalchemy import BigInteger, Text, VARCHAR
from sqlmodel import Field, Relationship, select
from src.models.base import BaseModel, table_prefix
from src.models.user import User
from src.routes.deps.db_session import DBSession


class AppointmentStatus(str, Enum):
    pending = "pending"
    accepted = "accepted"
    completed = "completed"
    cancelled = "cancelled"


class Appointment(BaseModel, table=True):
    __tablename__ = table_prefix + "appointments"

    user_id: int = Field(sa_type=BigInteger, foreign_key=table_prefix + "users.user_id", index=True)
    user: User | None = Relationship()

    appointment_type: str = Field(default="remote_appointment", sa_type=VARCHAR(50))
    problem_description: str = Field(sa_type=Text)

    lawyer_id: int | None = Field(default=None, sa_type=BigInteger, index=True)
    group_message_id: int | None = Field(default=None, index=True)

    status: AppointmentStatus = Field(default=AppointmentStatus.pending, index=True)

    scheduled_at: datetime | None = Field(default=None, index=True)
    completed_at: datetime | None = Field(default=None)

    media_type: str | None = Field(default=None, sa_type=VARCHAR(50))
    media_file_id: str | None = Field(default=None, sa_type=VARCHAR(255))
    media_name: str | None = Field(default=None, sa_type=VARCHAR(255))
    media_meta: str | None = Field(default=None, sa_type=Text)

    meeting_link: str | None = Field(default=None, sa_type=VARCHAR(500))
    cancellation_reason: str | None = Field(default=None, sa_type=Text)
    reminder_sent: bool = Field(default=False)

    rating: int | None = Field(default=None)
    feedback: str | None = Field(default=None, sa_type=Text)
    rated_at: datetime | None = Field(default=None)

    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    @classmethod
    def get_by_id(cls, appointment_id: int, session: DBSession) -> "Appointment | None":
        return session.get(cls, appointment_id)

    @classmethod
    def get_by_group_message_id(cls, group_message_id: int, session: DBSession):
        return session.exec(select(cls).where(cls.group_message_id == group_message_id)).first()

    @classmethod
    def get_user_appointments(cls, user_id: int, session: DBSession) -> list["Appointment"]:
        return list(session.exec(select(cls).where(cls.user_id == user_id).order_by(cls.created_at.desc())).all())
