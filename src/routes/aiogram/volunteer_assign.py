import asyncio
import html
import json
import logging
import re
from datetime import datetime

from aiogram import Router, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, LinkPreviewOptions
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlmodel import select
from sulguk import SULGUK_PARSE_MODE

from src.app.assign_helpers import (
    VOL_ASSIGNS_PAGE_SIZE,
    is_text_review,
    paginate,
    review_draft_hash,
    vol_assigns_cb,
)
from src.app.filters import is_private_message
from src.app.html_utils import escape_multiline
from src.app.review_quality import ISSUE_LABELS, record_review_attempt
from src.app.keyboards import get_volunteer_menu
from src.app.link_utils import build_group_message_link
from src.app.rag_client import RagError, rag_client
from src.app.timeutils import tz
from src.app.translations import t
from src.config.settings import settings
from src.models.assignment import AssignmentStatus, InquiryAssignment
from src.models.inquiry import Inquiry, InquiryMediaType, InquiryStatus
from src.models.user import User
from src.models.volunteer import Volunteer
from src.routes.aiogram.volunteer_result import get_volunteer_result_view
from src.routes.deps.db_session import DBSession

logger = logging.getLogger(__name__)

volunteer_assign_router = Router(name="volunteer_assign")


class VolunteerReviewState(StatesGroup):
    waiting_for_draft = State()


VOL_RESULT_BTNS = [t("menu_vol_result", "uz"), t("menu_vol_result", "oz"), t("menu_vol_result", "ru")]
VOL_ASSIGNS_BTNS = [t("menu_vol_assigns", "uz"), t("menu_vol_assigns", "oz"), t("menu_vol_assigns", "ru")]
VOL_REVIEW_BTNS = [t("menu_vol_review", "uz"), t("menu_vol_review", "oz"), t("menu_vol_review", "ru")]
VOL_MENU_BTNS = VOL_RESULT_BTNS + VOL_ASSIGNS_BTNS + VOL_REVIEW_BTNS
VOL_BACK_BTNS = [
    t("btn_back_main", "uz"), t("btn_back_main", "oz"), t("btn_back_main", "ru"),
    t("btn_cancel", "uz"), t("btn_cancel", "oz"), t("btn_cancel", "ru"),
    "⬅️ Asosiy menyu", "⬅️ Асосий меню", "⬅️ Главное меню",
    "❌ Bekor qilish", "❌ Бекор қилиш", "❌ Отмена",
]


def _vol_lang(user_id: int, db_session: DBSession) -> str:
    user = User.get_by_user_id(user_id, db_session)
    return user.language if user and user.language else "uz"


def _active_volunteer(user_id: int, db_session: DBSession) -> Volunteer | None:
    # admin yoki yurist bo'lsa ham faol volontyor o'z panelidan foydalanadi
    vol = Volunteer.get_by_user_id(user_id, db_session)
    if vol and vol.is_active:
        return vol
    return None


def get_open_assignments(volunteer_id: int, db_session: DBSession) -> list[tuple[InquiryAssignment, Inquiry]]:
    rows = db_session.exec(
        select(InquiryAssignment).where(
            InquiryAssignment.volunteer_user_id == volunteer_id,
            InquiryAssignment.status.in_(AssignmentStatus.OPEN),
        ).order_by(InquiryAssignment.assigned_at.desc())
    ).all()
    out = []
    for a in rows:
        inq = db_session.get(Inquiry, a.inquiry_id)
        if inq and inq.status == InquiryStatus.active:
            out.append((a, inq))
    return out


def _inquiry_link_html(inquiry: Inquiry) -> str:
    link = build_group_message_link(inquiry.group_id, inquiry.group_question_id)
    if link:
        return f'<a href="{link}">Murojaat №{inquiry.id}</a>'
    return f"Murojaat №{inquiry.id}"


def render_assigns_text(items: list[tuple[InquiryAssignment, Inquiry]], total: int, lang: str) -> str:
    lines = [t("vol_assigns_title", lang, n=total)]
    for a, inq in items:
        at = a.assigned_at.strftime("%d.%m.%Y %H:%M") if a.assigned_at else "—"
        lines.append(f"{_inquiry_link_html(inq)} • {html.escape((inq.section_name or '—').strip())}<br/>🕓 {at}")
    return "<br/><br/>".join(lines)


def review_pick_cb(inquiry_id: int) -> str:
    return f"volrv:{inquiry_id}"


def render_assigns_markup(page: int, total_pages: int, items: list[tuple[InquiryAssignment, Inquiry]] | None = None,
                          lang: str = "uz"):
    builder = InlineKeyboardBuilder()
    for _, inq in items or []:
        builder.row(InlineKeyboardButton(text=t("btn_review_this", lang, id=inq.id), callback_data=review_pick_cb(inq.id)))
    if total_pages > 1:
        nav = []
        if page > 1:
            nav.append(InlineKeyboardButton(text="⬅️", callback_data=vol_assigns_cb(page - 1)))
        nav.append(InlineKeyboardButton(text=f"📄 {page}/{total_pages}", callback_data=vol_assigns_cb(page)))
        if page < total_pages:
            nav.append(InlineKeyboardButton(text="➡️", callback_data=vol_assigns_cb(page + 1)))
        builder.row(*nav)
    return builder.as_markup()


def _question_snippet(inquiry: Inquiry, limit: int = 300) -> str:
    raw = inquiry.question or ""
    if inquiry.question_mediatype != InquiryMediaType.text:
        raw = re.sub(r"<[^>]+>", " ", raw).strip() or "Media murojaat"
    if len(raw) > limit:
        raw = raw[:limit].rstrip() + "…"
    return escape_multiline(raw)


REVIEW_ERR_DEDUPE_SECONDS = 300

_SECRET_RE = re.compile(
    r"(?i)(api[_-]?key|bearer|password|passwd|secret|token)\s*[:=\s]\s*\S+",
)
_URL_PASS_RE = re.compile(r"(\w+://[^/\s:]+:)[^@\s]+(@)")


def _short(text: str | None, limit: int = 200) -> str:
    text = (text or "").strip()
    if len(text) > limit:
        return text[:limit].rstrip() + "…"
    return text




def format_review_issues(issues: list[dict] | None) -> str:
    """Kamchiliklar: avval jiddiylari; har biri — qaysi joy, nima xato, nimani tuzatish kerak."""
    items = [i for i in issues or [] if isinstance(i, dict)]
    items.sort(key=lambda i: 0 if i.get("severity", "major") == "major" else 1)
    lines = []
    for n, item in enumerate(items, 1):
        label = ISSUE_LABELS.get(item.get("type"), ISSUE_LABELS["other"])
        if item.get("severity") == "minor":
            label += " (kichik)"
        quote = _short(item.get("quote"), 200)
        problem = _short(item.get("problem"), 250)
        fix = _short(item.get("fix"), 250)
        line = f"<b>{n}. {label}</b>"
        if quote:
            line += f"<br/>«{html.escape(quote)}»"
        if problem:
            line += f"<br/>{html.escape(problem)}"
        if fix:
            line += f"<br/>👉 {html.escape(fix)}"
        lines.append(line)
    return "<br/><br/>".join(lines) or "—"


def _volunteer_label(message: Message) -> str:
    u = message.from_user
    name = html.escape(f"{u.first_name or ''} {u.last_name or ''}".strip() or "—")
    if u.username:
        return f"{name} (@{html.escape(u.username)}, ID: {u.id})"
    return f"{name} (ID: {u.id})"


def sanitize_admin_error_text(text: str | None, limit: int = 300) -> str:
    """Admin xabaridagi qisqa matn: sirlar (kalit/token/parol) niqoblanadi."""
    cleaned = _SECRET_RE.sub(lambda m: f"{m.group(1)}=***", text or "")
    cleaned = _URL_PASS_RE.sub(r"\1***\2", cleaned)
    return _short(cleaned.strip(), limit) or "—"


def review_error_info(exc: BaseException) -> tuple[str, str]:
    """(tur, kod): RagError | TimeoutError | exception sinfi; kod — RagError kodi yoki 'exception'."""
    if isinstance(exc, RagError):
        return ("RagError", exc.code or "error")
    if isinstance(exc, asyncio.TimeoutError):
        return ("TimeoutError", "review_timeout")
    return (type(exc).__name__, "exception")


def review_error_key(kind: str, code: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.:-]+", "_", f"{kind}:{code}")[:80]
    return f"review_err:{safe}"


def _get_redis_client():
    try:
        from src.database.redisdb import get_redis
        return get_redis(is_async=True)
    except Exception:
        logger.warning("Review error dedupe: redis unavailable, admin alert always sent")
        return None


async def _review_error_dedupe(redis_client, err_key: str) -> tuple[bool, int]:
    """Spam himoyasi: bir xil xato kaliti uchun 5 daqiqada ko'pi bilan 1 ta admin xabari.

    Qaytaradi: (yuborilsinmi, jamlangan_soni). Redis ishlamasa — (True, 0).
    """
    lock_key = f"{err_key}:lock"
    count_key = f"{err_key}:count"
    try:
        if redis_client is None:
            return True, 0
        acquired = await redis_client.set(lock_key, "1", ex=REVIEW_ERR_DEDUPE_SECONDS, nx=True)
        if acquired:
            pending = 0
            try:
                raw = await redis_client.get(count_key)
                pending = int(raw) if raw is not None else 0
            except (TypeError, ValueError):
                pending = 0
            if pending:
                try:
                    await redis_client.delete(count_key)
                except Exception:
                    pass
            return True, pending
        try:
            await redis_client.incr(count_key)
        except Exception:
            pass
        try:
            await redis_client.expire(count_key, REVIEW_ERR_DEDUPE_SECONDS)
        except Exception:
            pass
        return False, 0
    except Exception:
        return True, 0


async def _send_admin_dm(bot: Bot, text: str) -> int:
    """Barcha adminlarga shaxsiy DM; yuborilmasa (blocked) log + keyingi adminga davom."""
    sent = 0
    for admin_id in settings.admin_ids_list:
        try:
            await bot.send_message(chat_id=admin_id, text=text, parse_mode=SULGUK_PARSE_MODE)
            sent += 1
        except Exception as e:
            logger.warning("Review admin DM failed (admin_id=%s): %s", admin_id, type(e).__name__)
    return sent


async def _handle_review_error(bot: Bot, message: Message, inquiry: Inquiry, lang: str, exc: BaseException) -> None:
    """Fail-closed xato xulqi: volontyorga texnik xato matni, adminlarga dedupe bilan DM."""
    kind, code = review_error_info(exc)
    if isinstance(exc, RagError):
        raw_detail = exc.message or ""
    else:
        raw_detail = str(exc)
    detail = sanitize_admin_error_text(raw_detail)
    await message.answer(t("review_unavailable", lang))
    err_key = review_error_key(kind, code)
    should_send, pending = await _review_error_dedupe(_get_redis_client(), err_key)
    if not should_send:
        return
    now_str = datetime.now(tz).strftime("%d.%m.%Y %H:%M")
    extra = t("review_error_admin_pending", "uz", n=pending) if pending else ""
    admin_text = t(
        "review_error_admin", "uz",
        ts=now_str, link=_inquiry_link_html(inquiry), id=inquiry.id,
        vol=_volunteer_label(message), kind=html.escape(kind), code=html.escape(code),
        detail=html.escape(detail), extra=extra,
    )
    await _send_admin_dm(bot, admin_text)


@volunteer_assign_router.message(F.text.in_(VOL_RESULT_BTNS), is_private_message)
async def vol_result_handler(message: Message, state: FSMContext, db_session: DBSession):
    vol = _active_volunteer(message.from_user.id, db_session)
    if not vol:
        return await message.answer(t("vol_panel_not_volunteer", _vol_lang(message.from_user.id, db_session)))
    await state.clear()
    text, markup = get_volunteer_result_view(vol, db_session)
    await message.answer(text, reply_markup=markup, parse_mode=SULGUK_PARSE_MODE)


@volunteer_assign_router.message(F.text.in_(VOL_ASSIGNS_BTNS), is_private_message)
async def vol_assigns_handler(message: Message, state: FSMContext, db_session: DBSession):
    vol = _active_volunteer(message.from_user.id, db_session)
    if not vol:
        return await message.answer(t("vol_panel_not_volunteer", _vol_lang(message.from_user.id, db_session)))
    await state.clear()
    lang = _vol_lang(message.from_user.id, db_session)
    await _answer_assigns(message, vol, lang, db_session, page=1)


async def _answer_assigns(message: Message, vol: Volunteer, lang: str, db_session: DBSession, page: int):
    pairs = get_open_assignments(vol.user_id, db_session)
    if not pairs:
        return await message.answer(t("vol_assigns_empty", lang))
    page_items, total_pages, page = paginate(
        pairs, page if isinstance(page, int) and page >= 1 else 1, VOL_ASSIGNS_PAGE_SIZE,
    )
    await message.answer(
        render_assigns_text(page_items, len(pairs), lang),
        reply_markup=render_assigns_markup(page, total_pages, page_items, lang),
        parse_mode=SULGUK_PARSE_MODE,
    )


@volunteer_assign_router.callback_query(F.data.startswith("volas:"), is_private_message)
async def vol_assigns_page_callback(query: CallbackQuery, db_session: DBSession):
    vol = _active_volunteer(query.from_user.id, db_session)
    if not vol:
        return await query.answer()
    try:
        page = int(query.data.split(":")[1])
    except (ValueError, IndexError):
        page = 1
    lang = _vol_lang(query.from_user.id, db_session)
    pairs = get_open_assignments(vol.user_id, db_session)
    if not pairs:
        await query.answer()
        return await query.message.answer(t("vol_assigns_empty", lang))
    page_items, total_pages, page = paginate(pairs, max(page, 1), VOL_ASSIGNS_PAGE_SIZE)
    try:
        await query.message.edit_text(
            render_assigns_text(page_items, len(pairs), lang),
            reply_markup=render_assigns_markup(page, total_pages, page_items, lang),
            parse_mode=SULGUK_PARSE_MODE,
        )
    except Exception:
        pass
    await query.answer()


@volunteer_assign_router.message(F.text.in_(VOL_REVIEW_BTNS), is_private_message)
async def vol_review_start_handler(message: Message, state: FSMContext, db_session: DBSession):
    vol = _active_volunteer(message.from_user.id, db_session)
    if not vol:
        return await message.answer(t("vol_panel_not_volunteer", _vol_lang(message.from_user.id, db_session)))
    lang = _vol_lang(message.from_user.id, db_session)
    await _start_review(message, state, vol, lang, db_session)


async def _start_review(message: Message, state: FSMContext, vol: Volunteer, lang: str, db_session: DBSession):
    pairs = get_open_assignments(vol.user_id, db_session)
    await state.clear()
    if not pairs:
        return await message.answer(t("review_no_assign", lang))
    if len(pairs) == 1:
        assignment, inquiry = pairs[0]
        return await _ask_draft(message, state, assignment, inquiry, lang)
    builder = InlineKeyboardBuilder()
    for _, inq in pairs[:30]:
        section = (inq.section_name or "").strip()
        builder.row(InlineKeyboardButton(text=f"№{inq.id} • {section[:28]}", callback_data=review_pick_cb(inq.id)))
    await message.answer(t("review_choose", lang, n=len(pairs)), reply_markup=builder.as_markup(), parse_mode=SULGUK_PARSE_MODE)


async def _ask_draft(message: Message, state: FSMContext, assignment: InquiryAssignment, inquiry: Inquiry, lang: str):
    await state.set_state(VolunteerReviewState.waiting_for_draft)
    await state.update_data(review_inquiry_id=inquiry.id, review_assignment_id=assignment.id)
    await message.answer(
        t("review_ask", lang, link=_inquiry_link_html(inquiry), q=_question_snippet(inquiry)),
        parse_mode=SULGUK_PARSE_MODE,
        link_preview_options=LinkPreviewOptions(is_disabled=True),
    )


@volunteer_assign_router.callback_query(F.data.startswith("volrv:"), is_private_message)
async def vol_review_pick_callback(query: CallbackQuery, state: FSMContext, db_session: DBSession):
    lang = _vol_lang(query.from_user.id, db_session)
    vol = _active_volunteer(query.from_user.id, db_session)
    if not vol:
        return await query.answer(t("vol_panel_not_volunteer", lang), show_alert=True)
    try:
        inquiry_id = int(query.data.split(":")[1])
    except (ValueError, IndexError):
        return await query.answer()
    chosen = next(((a, inq) for a, inq in get_open_assignments(vol.user_id, db_session) if inq.id == inquiry_id), None)
    if not chosen:
        return await query.answer(t("review_no_assign", lang), show_alert=True)
    await query.answer()
    try:
        await query.message.delete()
    except Exception:
        pass
    await _ask_draft(query.message, state, chosen[0], chosen[1], lang)


@volunteer_assign_router.message(
    VolunteerReviewState.waiting_for_draft,
    F.text.in_(VOL_MENU_BTNS + VOL_BACK_BTNS),
    is_private_message,
)
async def vol_review_menu_or_back(message: Message, state: FSMContext, db_session: DBSession):
    vol = _active_volunteer(message.from_user.id, db_session)
    if not vol:
        await state.clear()
        return
    lang = _vol_lang(message.from_user.id, db_session)
    await state.clear()
    if message.text in VOL_RESULT_BTNS:
        text, markup = get_volunteer_result_view(vol, db_session)
        return await message.answer(text, reply_markup=markup, parse_mode=SULGUK_PARSE_MODE)
    if message.text in VOL_ASSIGNS_BTNS:
        return await _answer_assigns(message, vol, lang, db_session, page=1)
    if message.text in VOL_REVIEW_BTNS:
        return await _start_review(message, state, vol, lang, db_session)
    await message.answer(t("btn_back_main", lang), reply_markup=get_volunteer_menu(lang))


@volunteer_assign_router.message(VolunteerReviewState.waiting_for_draft, F.text, is_private_message)
async def vol_review_draft_handler(message: Message, state: FSMContext, db_session: DBSession, bot: Bot):
    vol = _active_volunteer(message.from_user.id, db_session)
    if not vol:
        await state.clear()
        return
    lang = _vol_lang(message.from_user.id, db_session)
    if not is_text_review(message.text):
        return await message.answer(t("review_only_text", lang))
    data = await state.get_data()
    inquiry = db_session.get(Inquiry, data.get("review_inquiry_id") or 0)
    assignment = db_session.get(InquiryAssignment, data.get("review_assignment_id") or 0)
    if (
        not inquiry or inquiry.status != InquiryStatus.active
        or not assignment or assignment.status not in AssignmentStatus.OPEN
        or assignment.volunteer_user_id != vol.user_id
        or assignment.inquiry_id != inquiry.id
    ):
        await state.clear()
        return await message.answer(t("review_no_assign", lang))

    dis_state = None
    try:
        ds = inquiry.user.disability_state if inquiry.user else None
        dis_state = getattr(ds, "value", ds) or None
    except Exception:
        dis_state = None
    if dis_state is not None:
        dis_state = str(dis_state)
    try:
        result = await rag_client.review(
            question=inquiry.question,
            section=inquiry.section_name,
            answer=message.text.strip(),
            disability_state=dis_state,
            request_id=f"inquiry:{inquiry.id}",
        )
    except Exception as e:
        logger.warning("Volunteer review RAG failed (inquiry %s): %s", inquiry.id, type(e).__name__)
        await _handle_review_error(bot, message, inquiry, lang, e)
        return

    try:
        record_review_attempt(db_session, assignment, inquiry, vol.user_id, result)
    except Exception as e:
        db_session.rollback()
        logger.warning("Tekshiruv tarixiga yozib bo'lmadi (inquiry %s): %s", inquiry.id, e)
    draft_hash = review_draft_hash(message.text)
    verdict = result.get("verdict")
    if verdict == "approve":
        assignment.review_status = "passed"
        assignment.review_draft_hash = draft_hash
        assignment.review_passed_at = datetime.now()
        assignment.review_json = json.dumps({**result, "approved_text": message.text.strip()}, ensure_ascii=False)
        db_session.add(assignment)
        db_session.commit()
        hint = ""
        if result.get("delivery_hint"):
            hint = t("review_hint", lang, hint=html.escape(result["delivery_hint"]))
        await state.clear()
        send_kb = InlineKeyboardBuilder()
        send_kb.button(text=t("btn_send_approved", lang), callback_data=f"volsend:{assignment.id}")
        return await message.answer(
            t("review_approved", lang, link=_inquiry_link_html(inquiry), hint=hint),
            reply_markup=send_kb.as_markup(),
            parse_mode=SULGUK_PARSE_MODE,
            link_preview_options=LinkPreviewOptions(is_disabled=True),
        )
    if verdict == "needs_admin":
        assignment.review_status = "needs_admin"
        assignment.review_draft_hash = draft_hash
        assignment.review_passed_at = None
        assignment.review_json = json.dumps(result, ensure_ascii=False)
        db_session.add(assignment)
        db_session.commit()
        await state.clear()
        await message.answer(t("review_needs_admin", lang))
        admin_hint = ""
        if result.get("delivery_hint"):
            admin_hint = t("review_hint", "uz", hint=html.escape(result["delivery_hint"]))
        admin_text = t(
            "review_admin_escalation", "uz",
            link=_inquiry_link_html(inquiry), id=inquiry.id,
            vol=_volunteer_label(message),
            summary=html.escape(str(result.get("summary") or "—")),
            hint=admin_hint,
        )
        await _send_admin_dm(bot, admin_text)
        return
    assignment.review_status = "failed"
    assignment.review_draft_hash = draft_hash
    assignment.review_passed_at = None
    assignment.review_json = json.dumps(result, ensure_ascii=False)
    db_session.add(assignment)
    db_session.commit()
    issues = format_review_issues(result.get("issues"))
    await message.answer(t("review_rejected", lang, issues=issues), parse_mode=SULGUK_PARSE_MODE)


@volunteer_assign_router.message(VolunteerReviewState.waiting_for_draft, is_private_message)
async def vol_review_media_handler(message: Message, state: FSMContext, db_session: DBSession):
    vol = _active_volunteer(message.from_user.id, db_session)
    if not vol:
        await state.clear()
        return
    lang = _vol_lang(message.from_user.id, db_session)
    await message.answer(t("review_only_text", lang))


@volunteer_assign_router.callback_query(F.data.startswith("volsend:"), is_private_message)
async def vol_send_approved_callback(query: CallbackQuery, db_session: DBSession, bot: Bot):
    """Tasdiqlangan javobni bitta tugma bilan yuborish: fuqaroga, guruhga (kartaga reply) va karta holati."""
    from src.app.assign_helpers import review_hashes_match
    from src.app.inquiry_card import refresh_inquiry_card
    from src.database.redisdb import get_redis
    from src.routes.aiogram.group_router import answered_block, finalize_inquiry_answer, send_answer_to_citizen

    lang = _vol_lang(query.from_user.id, db_session)
    vol = _active_volunteer(query.from_user.id, db_session)
    if not vol:
        return await query.answer(t("vol_panel_not_volunteer", lang), show_alert=True)
    try:
        assignment = db_session.get(InquiryAssignment, int(query.data.split(":")[1]))
    except (ValueError, IndexError):
        assignment = None
    inquiry = db_session.get(Inquiry, assignment.inquiry_id) if assignment else None
    approved_text = ""
    if assignment and assignment.review_json:
        try:
            approved_text = json.loads(assignment.review_json).get("approved_text") or ""
        except ValueError:
            approved_text = ""
    if (
        not assignment or not inquiry
        or assignment.volunteer_user_id != vol.user_id
        or assignment.status not in AssignmentStatus.OPEN
        or assignment.review_status != "passed"
        or inquiry.status != InquiryStatus.active
        or inquiry.assigned_volunteer_id != vol.user_id
        or not approved_text
        or not review_hashes_match(approved_text, assignment.review_draft_hash)
    ):
        return await query.answer(t("review_send_unavailable", lang), show_alert=True)

    # ikki marta bosilsa ikki marta ketmasin
    lock_key = f"volsend_lock:{assignment.id}"
    try:
        if not get_redis(is_async=False).set(lock_key, "1", ex=120, nx=True):
            return await query.answer()
    except Exception:
        pass
    await query.answer()

    success, reason, _ = await send_answer_to_citizen(
        bot.send_message,
        dict(chat_id=inquiry.user_id, text=approved_text, reply_to_message_id=inquiry.private_question_id),
    )
    if not success:
        try:
            get_redis(is_async=False).delete(lock_key)
        except Exception:
            pass
        return await query.message.answer(t("review_send_failed", lang, reason=reason))

    group_msg = None
    try:
        group_msg = await bot.send_message(
            chat_id=inquiry.group_id,
            text=f"💬 <b>Fuqaroga yuborilgan javob</b> — {html.escape(vol.full_name)}:<br/>"
                 f"<blockquote>{escape_multiline(approved_text)}</blockquote>",
            reply_to_message_id=inquiry.group_question_id,
            parse_mode=SULGUK_PARSE_MODE,
        )
    except Exception as e:
        logger.warning("Inquiry %s: javobni guruhga qayd etib bo'lmadi: %s", inquiry.id, e)

    inquiry.answer = approved_text
    inquiry.answer_mediatype = InquiryMediaType.text
    link = build_group_message_link(inquiry.group_id, group_msg.message_id) if group_msg else None
    await refresh_inquiry_card(
        bot, inquiry, db_session,
        extra_html=answered_block(vol.user_id, vol.full_name, datetime.now(tz), link),
        keep_assign_button=False,
    )
    await finalize_inquiry_answer(bot, db_session, inquiry, vol.user_id, group_msg.message_id if group_msg else None)
    try:
        await query.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await query.message.answer(t("review_sent_ok", lang), parse_mode=SULGUK_PARSE_MODE)
