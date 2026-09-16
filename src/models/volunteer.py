from datetime import datetime
from sqlalchemy import BigInteger, VARCHAR
from sqlmodel import Field, select
from src.models.base import BaseModel, table_prefix
from src.routes.deps.db_session import DBSession


class Volunteer(BaseModel, table=True):
    __tablename__ = table_prefix + "volunteers"

    user_id: int = Field(sa_type=BigInteger, unique=True, index=True)
    first_name: str = Field(sa_type=VARCHAR(100))
    last_name: str = Field(sa_type=VARCHAR(100))
    study_or_work: str = Field(sa_type=VARCHAR(255))
    birth_year: int = Field(default=2000)
    phone_number: str = Field(sa_type=VARCHAR(50))
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.now)

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    @classmethod
    def get_by_user_id(cls, user_id: int, session: DBSession) -> "Volunteer | None":
        return session.exec(select(cls).where(cls.user_id == user_id)).first()

    @classmethod
    def get_active_volunteers(cls, session: DBSession) -> list["Volunteer"]:
        return list(session.exec(select(cls).where(cls.is_active == True)).all())
