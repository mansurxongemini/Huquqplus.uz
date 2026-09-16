from datetime import datetime
from enum import Enum
from sqlalchemy import BigInteger, Text, VARCHAR
from src.models.base import BaseModel, table_prefix
from sqlmodel import Field, Relationship, select, and_
from src.models.user import User
from src.routes.deps.db_session import DBSession


class InquiryStatus(str, Enum):
    active = "active"
    replied = "replied"
    closed = "closed"
    cancelled = "cancelled"


class InquiryMediaType(str, Enum):
    text = "text"
    voice = "voice"
    video_note = "video_note"
    video = "video"
    document = "document"
    photo = "photo"


class Inquiry(BaseModel, table=True):
    __tablename__ = table_prefix + "inquiries"

    section_name: str
    question: str = Field(sa_type=Text)
    private_question_id: int
    group_question_id: int = Field(index=True)
    question_mediatype: InquiryMediaType = Field(default=InquiryMediaType.text)
    question_media: str | None = Field(default=None, sa_type=Text)
    group_id: int | str = Field(sa_type=VARCHAR(255))
    bot_id: int = Field(sa_type=BigInteger)
    status: InquiryStatus = Field(default=InquiryStatus.active, index=True)
    answer: str | None = Field(default=None, sa_type=Text)
    answer_mediatype: InquiryMediaType = Field(default=InquiryMediaType.text)
    answer_media: str | None = Field(default=None, sa_type=Text)
    group_answer_id: int | None = Field(default=None)
    responder_id: int | None = Field(default=None, sa_type=BigInteger)
    created_at: datetime | None = Field(default_factory=datetime.now, index=True)
    updated_at: datetime | None = Field(default_factory=datetime.now)

    replied_at: datetime | None = Field(default=None)
    rating: int | None = Field(default=None)
    feedback: str | None = Field(default=None, sa_type=Text)
    rated_at: datetime | None = Field(default=None)
    user_id: int | None = Field(default=None, sa_type=BigInteger, foreign_key=table_prefix + "users.user_id", index=True)
    user: User | None = Relationship()
    parent_id: int | None = Field(default=None, sa_type=BigInteger, nullable=True, index=True)

    @staticmethod
    def get_by_message_id(group_id: str, group_question_id: int, bot_id: int,session: DBSession):
        return session.exec(select(Inquiry).where(
            and_(Inquiry.bot_id == bot_id,
                 Inquiry.group_id == group_id,
                 Inquiry.group_question_id == group_question_id))).first()

    def close(self, cancelled: bool, session: DBSession, commit=True):
        self.status = InquiryStatus.closed if not cancelled else InquiryStatus.cancelled
        self.updated_at = datetime.now()

        session.add(self)
        if commit: session.commit()
