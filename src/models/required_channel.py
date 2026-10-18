from datetime import datetime
from sqlalchemy import VARCHAR, Boolean
from sqlmodel import Field, select
from src.models.base import BaseModel, table_prefix
from src.routes.deps.db_session import DBSession


class RequiredChannel(BaseModel, table=True):
    __tablename__ = table_prefix + "required_channels"

    channel_id: str = Field(sa_type=VARCHAR(100), unique=True, index=True)
    channel_name: str = Field(sa_type=VARCHAR(255))
    invite_link: str = Field(sa_type=VARCHAR(500))
    language: str = Field(default="all", sa_type=VARCHAR(10), index=True)
    is_active: bool = Field(default=True, sa_type=Boolean, index=True)
    created_at: datetime = Field(default_factory=datetime.now)

    @classmethod
    def get_by_id(cls, channel_db_id: int, session: DBSession) -> "RequiredChannel | None":
        return session.get(cls, channel_db_id)

    @classmethod
    def get_by_channel_id(cls, channel_id: str, session: DBSession) -> "RequiredChannel | None":
        return session.exec(select(cls).where(cls.channel_id == str(channel_id))).first()

    @classmethod
    def get_all(cls, session: DBSession) -> list["RequiredChannel"]:
        return list(session.exec(select(cls).order_by(cls.id.asc())).all())

    @classmethod
    def get_active_channels(cls, session: DBSession) -> list["RequiredChannel"]:
        return list(session.exec(select(cls).where(cls.is_active == True).order_by(cls.id.asc())).all())

    @classmethod
    def get_active_channels_for_lang(cls, lang: str, session: DBSession) -> list["RequiredChannel"]:
        """
        Returns active channels appropriate for user's language:
        - For 'uz' or 'oz' (Cyrillic): channels with language in ('uz', 'all')
        - For 'ru': channels with language in ('ru', 'all')
        """
        allowed_langs = ["all"]
        if lang in ["uz", "oz"]:
            allowed_langs.append("uz")
        elif lang == "ru":
            allowed_langs.append("ru")
        else:
            allowed_langs.append("uz")

        return list(
            session.exec(
                select(cls)
                .where(cls.is_active == True, cls.language.in_(allowed_langs))
                .order_by(cls.id.asc())
            ).all()
        )
