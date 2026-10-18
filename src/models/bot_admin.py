from datetime import datetime
from sqlalchemy import BigInteger, Boolean
from sqlmodel import Field, select
from src.models.base import BaseModel, table_prefix
from src.routes.deps.db_session import DBSession


class BotAdmin(BaseModel, table=True):
    """Admin panel orqali qo'shilgan adminlar. Asosiy (super) adminlar .env dagi ADMIN_IDS da turadi."""
    __tablename__ = table_prefix + "bot_admins"

    user_id: int = Field(sa_type=BigInteger, unique=True, index=True)
    added_by: int | None = Field(default=None, sa_type=BigInteger)
    added_at: datetime = Field(default_factory=datetime.now)
    is_active: bool = Field(default=True, sa_type=Boolean, index=True)
    removed_by: int | None = Field(default=None, sa_type=BigInteger)
    removed_at: datetime | None = Field(default=None)

    @classmethod
    def get_by_user_id(cls, user_id: int, session: DBSession) -> "BotAdmin | None":
        return session.exec(select(cls).where(cls.user_id == user_id)).first()

    @classmethod
    def get_active(cls, session: DBSession) -> list["BotAdmin"]:
        return list(session.exec(select(cls).where(cls.is_active == True).order_by(cls.id.asc())).all())  # noqa: E712
