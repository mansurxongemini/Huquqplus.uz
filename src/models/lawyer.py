from datetime import datetime
from sqlalchemy import BigInteger, VARCHAR
from sqlmodel import Field, select
from src.models.base import BaseModel, table_prefix
from src.routes.deps.db_session import DBSession


class OfficialLawyer(BaseModel, table=True):
    __tablename__ = table_prefix + "official_lawyers"

    user_id: int = Field(sa_type=BigInteger, unique=True, index=True)
    full_name: str = Field(sa_type=VARCHAR(255))
    phone: str | None = Field(default=None, sa_type=VARCHAR(50))
    specialization: str | None = Field(default=None, sa_type=VARCHAR(255))
    is_active: bool = Field(default=True)
    working_days: str = Field(default="1,2,3,4,5", sa_type=VARCHAR(50))
    start_hour: int = Field(default=9)
    end_hour: int = Field(default=18)
    slot_duration: int = Field(default=60)
    created_at: datetime = Field(default_factory=datetime.now)

    @classmethod
    def get_by_user_id(cls, user_id: int, session: DBSession):
        return session.exec(select(cls).where(cls.user_id == user_id)).first()

    @classmethod
    def get_active_lawyers(cls, session: DBSession) -> list["OfficialLawyer"]:
        return list(session.exec(select(cls).where(cls.is_active == True)).all())
