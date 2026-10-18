from datetime import datetime
from typing import Any, Annotated, Literal
from pydantic import AnyUrl, BeforeValidator
from pydantic_settings import BaseSettings, SettingsConfigDict
import secrets


def parse_cors(v: Any) -> list[str] | str:
    if isinstance(v, str) and not v.startswith("["):
        return [i.strip() for i in v.split(",")]
    elif isinstance(v, list | str):
        return v
    raise ValueError(v)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", secrets_dir="/run/secrets", env_ignore_empty=True, extra="ignore")

    STACK_NAME: str
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = secrets.token_urlsafe(32)
    # 60 minutes * 24 hours * 8 days = 8 days
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8
    DOMAIN: str = "localhost"
    ENVIRONMENT: Literal["local", "staging", "production"] = "local"
    WEBSITE_API_SECRET_KEY: str = "huquqplus_website_secret_key_2026_secure"
    API_PORT: int = 80

    @property
    def server_host(self) -> str:
        if self.ENVIRONMENT == "local":
            return f"http://{self.DOMAIN}"
        return f"https://{self.DOMAIN}"

    BACKEND_CORS_ORIGINS: Annotated[list[AnyUrl] | str, BeforeValidator(parse_cors)] = []
    PROJECT_NAME: str
    BOT_TOKEN: str
    BOT_NAME: str
    BOT_WEBHOOK_URL: str
    REDIS_HOST: str
    REDIS_PORT: str
    REDIS_PASS: str
    REDIS_DB: int = 0
    REDIS_QUEUE_DB: int = 1

    @property
    def redis_url(self) -> str:
        return f"redis://:{self.REDIS_PASS}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    DB_USER: str
    DB_PASSWORD: str
    DB_HOST: str
    DB_PORT: str
    DB_NAME: str

    @property
    def database_url(self) -> str:
        return f"mysql+pymysql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    LAWYER_APPOINTMENT_GROUP_ID: str
    HELP_GROUP_ID: str | None = None
    REPORT_RECIPIENT: str | None = None
    ADMIN_IDS: str = ""
    VOLUNTEER_GROUP_ID: str | int | None = None
    VOLUNTEER_REG_KEY: str = "volunteer"
    VOLUNTEER_LEADERBOARD_PUBLIC: bool = False
    ASSIGN_ENFORCE_FROM: datetime | None = None
    ASSIGN_REMINDER_QUIET_START: int = 22
    ASSIGN_REMINDER_QUIET_END: int = 6
    ASSIGN_REMINDER_SKIP_WEEKDAYS: str = ""  # eslatma yubormaslik kunlari: "6" — yakshanba, "5,6" — dam olish kunlari

    # RAG AI Assistant sozlamalari (ixtiyoriy)
    RAG_API_URL: str = ""
    RAG_API_KEY: str = ""
    RAG_TIMEOUT_SECONDS: float = 60.0
    RAG_REVIEW_TIMEOUT_SECONDS: float = 90.0
    AI_ASSISTANT_ENABLED: bool = True
    # Fuqarolar AI chatiga kirish (False = fuqaro menyusi/kirish yopiq; True = rollback).
    # Ichki AI (yurist qoralamasi, volontyor AI nazoratchi) bu bayroqqa bog'liq emas.
    AI_CITIZEN_ENABLED: bool = False
    AI_LAWYER_DRAFTS: bool = False  # guruhga AI qoralamasi yuborilmaydi: guruhda faqat haqiqiy javoblar
    # Fuqaroning oddiy matnli savoliga avtomatik javob (nazoratchi tasdiqlasa); aks holda guruhga
    AI_CITIZEN_ANSWERS: bool = False
    AI_AUTO_MIN_CONFIDENCE: float = 0.8
    AI_AUTO_MIN_SCORE: int = 4
    AI_AUTO_MAX_QUESTION_CHARS: int = 800
    AI_AUTO_DAILY_LIMIT_PER_USER: int = 5  # bir fuqaroga kuniga avtomatik javoblar soni
    AI_AUTO_DAILY_LIMIT: int = 300  # barcha fuqarolar uchun kunlik chegara (xarajat nazorati)
    AI_BALANCE_ALERT_USD: float = 2.0  # OpenRouter balansi shundan kam bo'lsa adminlarga ogohlantirish

    @property
    def super_admin_ids_list(self) -> list[int]:
        """Asosiy adminlar (.env ADMIN_IDS): panel orqali o'chirib bo'lmaydi, adminlarni boshqara oladi."""
        if not self.ADMIN_IDS:
            return []
        ids = []
        for i in self.ADMIN_IDS.split(","):
            i = i.strip()
            if i.lstrip("-").isdigit():
                ids.append(int(i))
        return ids

    @property
    def admin_ids_list(self) -> list[int]:
        """Barcha adminlar: .env dagi asosiy + panel orqali qo'shilganlar."""
        from src.app.admin_registry import get_db_admin_ids
        ids = list(self.super_admin_ids_list)
        for uid in sorted(get_db_admin_ids()):
            if uid not in ids:
                ids.append(uid)
        return ids

    def is_super_admin(self, user_id: int) -> bool:
        return user_id in self.super_admin_ids_list

    def is_admin(self, user_id: int) -> bool:
        if user_id in self.super_admin_ids_list:
            return True
        from src.app.admin_registry import get_db_admin_ids
        return user_id in get_db_admin_ids()

    # Inquiry section groups
    GROUP_IJTIMOIY_HIMOYA: str | int | None = None
    GROUP_TALIM: str | int | None = None
    GROUP_MEHNAT: str | int | None = None
    GROUP_UY_JOY: str | int | None = None
    GROUP_TIBBIY: str | int | None = None
    GROUP_BOSHQA: str | int | None = None

    def get_help_group_id(self) -> str:
        return self.HELP_GROUP_ID or self.LAWYER_APPOINTMENT_GROUP_ID

    def get_report_recipient(self) -> str:
        if self.REPORT_RECIPIENT:
            return self.REPORT_RECIPIENT
        if self.ENVIRONMENT == "local":
            return self.LAWYER_APPOINTMENT_GROUP_ID
        return "@d_yusupov"

    def get_inquiry_groups(self) -> dict[str, str | int]:
        if self.ENVIRONMENT == "local":
            default_group = self.LAWYER_APPOINTMENT_GROUP_ID
            return {
                '🛡  Ijtimoiy himoya': self.GROUP_IJTIMOIY_HIMOYA or default_group,
                '👨🏻‍🎓 Ta’lim': self.GROUP_TALIM or default_group,
                '👩🏻‍💼 Mehnat': self.GROUP_MEHNAT or default_group,
                '🏘  Uy-joy': self.GROUP_UY_JOY or default_group,
                '🧑🏻‍⚕ Tibbiy xizmat va reabilitatsiya': self.GROUP_TIBBIY or default_group,
                'Boshqa': self.GROUP_BOSHQA or default_group,
            }
        return {
            '🛡  Ijtimoiy himoya': self.GROUP_IJTIMOIY_HIMOYA or -1002155301250,
            '👨🏻‍🎓 Ta’lim': self.GROUP_TALIM or -1002192874095,
            '👩🏻‍💼 Mehnat': self.GROUP_MEHNAT or -1002230151847,
            '🏘  Uy-joy': self.GROUP_UY_JOY or -1002184621717,
            '🧑🏻‍⚕ Tibbiy xizmat va reabilitatsiya': self.GROUP_TIBBIY or -1002226267602,
            'Boshqa': self.GROUP_BOSHQA or -1002245081621,
        }


settings = Settings()
