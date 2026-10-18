"""Avtomatik javob tugmalari: baho va «Huquqshunosdan javob olish»."""
import logging
from datetime import datetime

from aiogram import F, Bot, Router
from aiogram.types import CallbackQuery
from sulguk import SULGUK_PARSE_MODE

from src.app.filters import is_private_message
from src.app.question_delivery import ai_answer_markup, escalate_ai_answer
from src.app.rag_client import rag_client
from src.app.translations import t
from src.database.redisdb import get_redis
from src.models.ai_answer import AiAnswer
from src.models.user import User
from src.routes.deps.db_session import DBSession

logger = logging.getLogger(__name__)

ai_answer_router = Router(name="ai_answer")


@ai_answer_router.callback_query(F.data.startswith("aiesc:"), is_private_message)
async def ask_lawyer_callback(query: CallbackQuery, db_session: DBSession, bot: Bot):
    user = User.get_by_user_id(query.from_user.id, db_session)
    lang = (user.language if user else None) or "uz"
    try:
        record = db_session.get(AiAnswer, int(query.data.split(":")[1]))
    except (ValueError, IndexError):
        record = None
    if not record or not user or record.user_id != query.from_user.id:
        return await query.answer()
    if user.is_blocked:
        return await query.answer(t("user_blocked", lang), show_alert=True)
    if record.escalated_inquiry_id:
        return await query.answer(t("ai_escalate_already", lang), show_alert=True)
    # ikki marta bosilsa ikki murojaat yaratilmasin
    try:
        if not get_redis(is_async=False).set(f"aiesc_lock:{record.id}", "1", ex=60, nx=True):
            return await query.answer()
    except Exception:
        pass
    await query.answer()

    inquiry = await escalate_ai_answer(bot, db_session, record, user)
    logger.info("AI javobi %s huquqshunosga o'tkazildi: murojaat %s", record.id, inquiry.id)
    try:
        await query.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await query.message.answer(t("inquiry_received", lang), parse_mode=SULGUK_PARSE_MODE)


@ai_answer_router.callback_query(F.data.startswith("aifb:"), is_private_message)
async def ai_answer_feedback_callback(query: CallbackQuery, db_session: DBSession):
    """Avtomatik javobga baho: bazada saqlanadi va bilim bazasi sifatini oshirish uchun RAG ga yuboriladi."""
    user = User.get_by_user_id(query.from_user.id, db_session)
    lang = (user.language if user else None) or "uz"
    try:
        _, rec_id, vote = query.data.split(":")
        record = db_session.get(AiAnswer, int(rec_id))
    except (ValueError, IndexError):
        record, vote = None, ""
    if not record or record.user_id != query.from_user.id or vote not in ("up", "down"):
        return await query.answer()
    if record.rating is None:
        record.rating = 1 if vote == "up" else -1
        record.rated_at = datetime.now()
        db_session.add(record)
        db_session.commit()
        if record.rag_answer_id:
            await rag_client.feedback(record.rag_answer_id, vote)
    await query.answer(t("ai_feedback_thanks" if vote == "up" else "ai_feedback_down_hint", lang),
                       show_alert=vote == "down")
    try:
        markup = None if record.escalated_inquiry_id else ai_answer_markup(record.id, lang, with_rating=False)
        await query.message.edit_reply_markup(reply_markup=markup)
    except Exception:
        pass
