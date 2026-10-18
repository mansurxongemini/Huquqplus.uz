from datetime import datetime
from sqlalchemy import BigInteger, Boolean, Text, VARCHAR
from sqlmodel import Field
from src.models.base import BaseModel, table_prefix


class AiAnswer(BaseModel, table=True):
    """Fuqaroning oddiy savoliga berilgan avtomatik javob (nazoratchi tasdiqlagan).
    Fuqaro qoniqmasa, shu yozuvdan guruhga murojaat yaratiladi (escalated_inquiry_id)."""
    __tablename__ = table_prefix + "ai_answers"

    user_id: int = Field(sa_type=BigInteger, index=True)
    section_name: str | None = Field(default=None, sa_type=VARCHAR(255))
    group_id: str | None = Field(default=None, sa_type=VARCHAR(255))
    question: str = Field(sa_type=Text)
    private_question_id: int | None = Field(default=None)
    answer_html: str = Field(sa_type=Text)
    review_confidence: float | None = Field(default=None)
    rag_answer_id: str | None = Field(default=None, sa_type=VARCHAR(64))
    rating: int | None = Field(default=None)  # 1 — foydali, -1 — foydali emas
    rated_at: datetime | None = Field(default=None)
    escalated_inquiry_id: int | None = Field(default=None, index=True)
    escalated_at: datetime | None = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.now, index=True)


class AiSectionSetting(BaseModel, table=True):
    """Soha bo'yicha avtomatik javobni yoqish/o'chirish (yozuv yo'q bo'lsa — yoqilgan)."""
    __tablename__ = table_prefix + "ai_section_settings"

    section_name: str = Field(sa_type=VARCHAR(255), unique=True, index=True)
    enabled: bool = Field(default=True, sa_type=Boolean)
    updated_by: int | None = Field(default=None, sa_type=BigInteger)
    updated_at: datetime = Field(default_factory=datetime.now)
