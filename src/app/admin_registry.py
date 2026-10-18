"""Panel orqali qo'shilgan adminlar (DB) ro'yxati — qisqa muddatli xotira keshi bilan.

settings.is_admin() sinxron va 80+ joyda chaqiriladi, shuning uchun DB so'rovi TTL kesh orqali
(bir jarayonda 15 soniyada ko'pi bilan 1 marta). Boshqa jarayon (celery) o'zgarishni TTL ichida ko'radi.
DB ishlamasa yoki jadval yo'q bo'lsa faqat .env dagi (super) adminlar qoladi.
"""
import logging
import time

logger = logging.getLogger(__name__)

CACHE_TTL = 15.0
_cache: dict = {"ids": frozenset(), "expires": 0.0}


def invalidate_cache() -> None:
    _cache["expires"] = 0.0


def get_db_admin_ids() -> frozenset[int]:
    now = time.monotonic()
    if now < _cache["expires"]:
        return _cache["ids"]
    try:
        from sqlmodel import Session, select
        from src.database.mysql import engine
        from src.models.bot_admin import BotAdmin
        with Session(engine) as session:
            rows = session.exec(select(BotAdmin.user_id).where(BotAdmin.is_active == True)).all()  # noqa: E712
        _cache["ids"] = frozenset(int(r) for r in rows)
    except Exception as e:  # noqa: BLE001 — DB/jadval yo'q: faqat super adminlar
        logger.warning("DB adminlarni o'qib bo'lmadi (%s): %s", type(e).__name__, e)
    _cache["expires"] = now + CACHE_TTL
    return _cache["ids"]
