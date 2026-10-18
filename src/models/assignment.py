from datetime import datetime
from sqlalchemy import BigInteger, VARCHAR, Text, UniqueConstraint as sa_UniqueConstraint
from sqlmodel import Field, select
from src.models.base import BaseModel, table_prefix
from src.routes.deps.db_session import DBSession


class AssignmentStatus:
    assigned = "assigned"
    notified = "notified"
    notify_failed = "notify_failed"
    replied = "replied"
    reassigned = "reassigned"
    closed = "closed"  # murojaat javobsiz yopilgan (masalan, eskirgan)

    OPEN = (assigned, notified, notify_failed)


class VolunteerSection(BaseModel, table=True):
    __tablename__ = table_prefix + "volunteer_sections"
    __table_args__ = (sa_UniqueConstraint("volunteer_user_id", "section_name", name="uq_volunteer_sections_pair"),)

    volunteer_user_id: int = Field(sa_type=BigInteger, index=True)
    section_name: str = Field(sa_type=VARCHAR(255))
    added_by: int | None = Field(default=None, sa_type=BigInteger)
    added_at: datetime = Field(default_factory=datetime.now)

    @classmethod
    def get_user_sections(cls, volunteer_user_id: int, session: DBSession) -> list["VolunteerSection"]:
        return list(session.exec(select(cls).where(cls.volunteer_user_id == volunteer_user_id)).all())

    @classmethod
    def get_section_members(cls, section_name: str, session: DBSession) -> list["VolunteerSection"]:
        return list(session.exec(select(cls).where(cls.section_name == section_name)).all())


class InquiryAssignment(BaseModel, table=True):
    __tablename__ = table_prefix + "inquiry_assignments"

    inquiry_id: int = Field(foreign_key=table_prefix + "inquiries.id", index=True)
    volunteer_user_id: int = Field(sa_type=BigInteger, index=True)
    section_name: str = Field(sa_type=VARCHAR(255))
    assigned_by: int = Field(sa_type=BigInteger)
    assigned_at: datetime = Field(default_factory=datetime.now)
    status: str = Field(default=AssignmentStatus.assigned, sa_type=VARCHAR(20), index=True)
    notify_error: str | None = Field(default=None, sa_type=Text)
    notify_attempts: int = Field(default=0)
    last_notify_at: datetime | None = Field(default=None)
    first_reminded_at: datetime | None = Field(default=None)
    last_reminded_at: datetime | None = Field(default=None)
    remind_count: int = Field(default=0)
    review_status: str = Field(default="none", sa_type=VARCHAR(20))
    review_draft_hash: str | None = Field(default=None, sa_type=VARCHAR(64))
    review_passed_at: datetime | None = Field(default=None)
    review_json: str | None = Field(default=None, sa_type=Text)
    created_at: datetime = Field(default_factory=datetime.now)

    @classmethod
    def get_open_for_volunteer(cls, volunteer_user_id: int, session: DBSession) -> list["InquiryAssignment"]:
        return list(session.exec(
            select(cls).where(
                cls.volunteer_user_id == volunteer_user_id,
                cls.status.in_(AssignmentStatus.OPEN),
            )
        ).all())


class ReviewAttempt(BaseModel, table=True):
    """Javobni tekshirishning har bir urinishi (volontyor sifat profili uchun tarix)."""
    __tablename__ = table_prefix + "review_attempts"

    assignment_id: int | None = Field(default=None, index=True)
    inquiry_id: int = Field(index=True)
    volunteer_user_id: int = Field(sa_type=BigInteger, index=True)
    verdict: str = Field(sa_type=VARCHAR(20))
    confidence: float | None = Field(default=None)
    scores_json: str | None = Field(default=None, sa_type=Text)
    issue_types: str | None = Field(default=None, sa_type=VARCHAR(500))  # "wrong_norm:major,incomplete:minor"
    created_at: datetime = Field(default_factory=datetime.now, index=True)
