"""Fuqaro savolini yetkazish: oddiy savolga avtomatik javob yoki guruhga murojaat.

Avtomatik javob faqat matnli, qisqa savolga beriladi va ikki bosqichdan o'tadi: bazadan javob
olinadi, so'ng shu javobni nazoratchi qat'iy tekshiradi. Tekshiruvdan to'liq o'tmasa yoki xizmat
ishlamasa, savol odatdagidek soha guruhiga ketadi — fuqaro hech qachon javobsiz qolmaydi.
"""
import logging
import re
from datetime import datetime

from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message
from sulguk import SULGUK_PARSE_MODE

from src.app.inquiry_card import AI_ESCALATION_HEADER, InquiryPayload, finalize_new_inquiry, post_inquiry_card
from src.app.translations import t
from src.config.settings import settings
from src.models.ai_answer import AiAnswer
from src.models.inquiry import Inquiry, InquiryMediaType
from src.models.user import User
from src.routes.deps.db_session import DBSession

logger = logging.getLogger(__name__)

def _plain(html_text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html_text or "")).strip()


def ai_answer_is_trusted(ask_resp: dict, review: dict) -> bool:
    """Avtomatik javob fuqaroga faqat to'liq ishonchli bo'lsa yuboriladi."""
    if not ask_resp or ask_resp.get("is_refusal") or not ask_resp.get("citations"):
        return False
    if not review or review.get("verdict") != "approve":
        return False
    if float(review.get("confidence") or 0) < settings.AI_AUTO_MIN_CONFIDENCE:
        return False
    scores = review.get("scores") or {}
    return bool(scores) and min(scores.values()) >= settings.AI_AUTO_MIN_SCORE


async def try_ai_answer(question: str, section: str | None, user: User) -> tuple[dict, dict] | None:
    """(ask javobi, nazoratchi xulosasi) yoki None — avtomatik javob berilmaydigan holatda."""
    from src.app.rag_client import rag_client

    if not settings.AI_CITIZEN_ANSWERS or not rag_client.is_configured():
        return None
    question = (question or "").strip()
    if not question or len(question) > settings.AI_AUTO_MAX_QUESTION_CHARS:
        return None
    if not within_daily_limits(user.user_id):
        logger.info("Avtomatik javob kunlik chegarasi tugadi (user %s)", user.user_id)
        return None
    lang = user.language or "uz"
    try:
        ask_resp = await rag_client.ask(
            question=question, user_id=str(user.user_id), conversation_id=None,
            language="ru" if lang == "ru" else "uz", internal=True,
        )
        if ask_resp.get("is_refusal") or not ask_resp.get("citations"):
            return None
        dis_state = getattr(user.disability_state, "value", user.disability_state) if user.disability_state else None
        review = await rag_client.review(
            question=question, section=section, answer=_plain(ask_resp.get("answer", ""))[:6000],
            disability_state=str(dis_state) if dis_state else None, request_id=f"auto:{user.user_id}",
        )
    except Exception as e:
        logger.info("Avtomatik javob berilmadi (user %s): %s", user.user_id, type(e).__name__)
        return None
    if not ai_answer_is_trusted(ask_resp, review):
        logger.info("Avtomatik javob nazoratdan o'tmadi (user %s): %s", user.user_id, review.get("verdict"))
        return None
    return ask_resp, review


def ai_answer_markup(ai_answer_id: int, lang: str, with_rating: bool = True) -> InlineKeyboardMarkup:
    rows = []
    if with_rating:
        rows.append([
            InlineKeyboardButton(text=t("btn_ai_useful", lang), callback_data=f"aifb:{ai_answer_id}:up"),
            InlineKeyboardButton(text=t("btn_ai_not_useful", lang), callback_data=f"aifb:{ai_answer_id}:down"),
        ])
    rows.append([InlineKeyboardButton(text=t("btn_ask_lawyer", lang), callback_data=f"aiesc:{ai_answer_id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def section_auto_enabled(db_session: DBSession, section_name: str | None) -> bool:
    """Admin paneldan soha bo'yicha o'chirilgan bo'lsa — avtomatik javob berilmaydi."""
    from sqlmodel import select
    from src.app.keyboards import normalize_section_name
    from src.models.ai_answer import AiSectionSetting
    section = normalize_section_name(section_name) or section_name
    if not section:
        return True
    try:
        row = db_session.exec(select(AiSectionSetting).where(AiSectionSetting.section_name == section)).first()
    except Exception:
        return True
    return row is None or bool(row.enabled)


def within_daily_limits(user_id: int) -> bool:
    """Xarajat nazorati: fuqaro va umumiy kunlik chegaralar (Redis ishlamasa — cheklanmaydi)."""
    try:
        from src.database.redisdb import get_redis
        r = get_redis(is_async=False)
        day = datetime.now().strftime("%Y%m%d")
        user_key, total_key = f"ai_auto:{day}:{user_id}", f"ai_auto:{day}:total"
        user_n, total_n = r.incr(user_key), r.incr(total_key)
        r.expire(user_key, 2 * 86400)
        r.expire(total_key, 2 * 86400)
    except Exception:
        return True
    return user_n <= settings.AI_AUTO_DAILY_LIMIT_PER_USER and total_n <= settings.AI_AUTO_DAILY_LIMIT


async def post_inquiry_to_group(
    bot: Bot,
    db_session: DBSession,
    user: User,
    section_name: str,
    group_id: int | str,
    payload: InquiryPayload,
    private_question_id: int,
    header: str = "",
    benefit_id: int | None = None,
    from_ai_answer_id: int | None = None,
    parent_id: int | None = None,
    reply_to_message_id: int | None = None,
) -> Inquiry:
    """Murojaatni guruhga yuboradi, bazaga yozadi va Biriktirish tugmasini qo'yadi (barcha yo'llar uchun bitta)."""
    card, cont_message, question = await post_inquiry_card(
        bot, group_id, user, payload, benefit_header=header, reply_to_message_id=reply_to_message_id,
    )
    inquiry = Inquiry(
        section_name=section_name,
        question=question,
        question_mediatype=payload.media_type,
        question_media=payload.media_json,
        private_question_id=private_question_id,
        group_question_id=card.message_id,
        group_id=str(group_id),
        bot_id=bot.id,
        user_id=user.user_id,
        benefit_id=benefit_id,
        from_ai_answer_id=from_ai_answer_id,
        parent_id=parent_id,
    )
    db_session.add(inquiry)
    db_session.commit()
    db_session.refresh(inquiry)
    await finalize_new_inquiry(bot, inquiry, card, cont_message, user.language or "uz")
    return inquiry


async def deliver_citizen_question(
    bot: Bot,
    message: Message,
    db_session: DBSession,
    user: User,
    section_name: str,
    group_id: int | str,
    payload: InquiryPayload,
    private_question_id: int,
) -> AiAnswer | Inquiry:
    """Oddiy matnli savolga avtomatik javob beradi; bo'lmasa murojaatni guruhga yuboradi."""
    from src.app.keyboards import get_role_menu
    from src.routes.aiogram.ai_assistant import send_ai_part

    lang = user.language or "uz"
    if (
        payload.media_type == InquiryMediaType.text
        and settings.AI_CITIZEN_ANSWERS
        and section_auto_enabled(db_session, section_name)
    ):
        try:
            # asosiy menyu shu xabar bilan qaytadi (soha tugmalari o'rniga)
            await message.answer(t("ai_answer_wait", lang), reply_markup=get_role_menu(user.user_id, lang, db_session))
        except Exception:
            pass
        result = await try_ai_answer(payload.text or "", section_name, user)
        if result:
            ask_resp, review = result
            record = AiAnswer(
                user_id=user.user_id, section_name=section_name, group_id=str(group_id),
                question=payload.text or "", private_question_id=private_question_id,
                answer_html=ask_resp.get("answer", ""), review_confidence=review.get("confidence"),
                rag_answer_id=str(ask_resp.get("answer_id") or "")[:64] or None,
            )
            db_session.add(record)
            db_session.commit()
            db_session.refresh(record)
            parts = [p for p in (ask_resp.get("parts") or [ask_resp.get("answer", "")]) if p]
            footer = "\n\n" + t("ai_answer_footer", lang)
            if len(parts[-1]) + len(footer) <= 4096:
                parts[-1] += footer
            else:
                parts.append(t("ai_answer_footer", lang))
            for idx, part in enumerate(parts):
                last = idx == len(parts) - 1
                await send_ai_part(
                    bot=bot, chat_id=message.chat.id, text=part,
                    reply_markup=ai_answer_markup(record.id, lang) if last else None,
                    reply_to_message_id=private_question_id if idx == 0 else None,
                )
            return record

    inquiry = await post_inquiry_to_group(
        bot, db_session, user, section_name, group_id, payload, private_question_id,
    )
    await message.answer(
        t("inquiry_received", lang),
        reply_markup=get_role_menu(user.user_id, lang, db_session),
        parse_mode=SULGUK_PARSE_MODE,
    )
    return inquiry


async def escalate_ai_answer(bot: Bot, db_session: DBSession, record: AiAnswer, user: User) -> Inquiry:
    """Fuqaro avtomatik javobdan qoniqmadi: savol tegishli guruhga murojaat sifatida yuboriladi."""
    payload = InquiryPayload(InquiryMediaType.text, text=record.question)
    inquiry = await post_inquiry_to_group(
        bot, db_session, user, record.section_name or "Boshqa", record.group_id, payload,
        record.private_question_id or 0, header=AI_ESCALATION_HEADER, from_ai_answer_id=record.id,
    )
    record.escalated_inquiry_id = inquiry.id
    record.escalated_at = datetime.now()
    db_session.add(record)
    db_session.commit()
    return inquiry
