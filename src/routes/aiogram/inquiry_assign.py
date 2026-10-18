import html
import logging
from datetime import datetime, timedelta

from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, InlineKeyboardButton, LinkPreviewOptions
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import func, update
from sqlmodel import select
from sulguk import SULGUK_PARSE_MODE

from src.app.assign_helpers import (
    parse_assign_pair,
    ASSIGN_PAGE_SIZE,
    assign_list_cb,
    assign_pick_cb,
    assign_retry_cb,
    cb_within_limit,
    paginate,
    rank_section_candidates,
)
from src.app.filters import is_group_callback
from src.app.keyboards import normalize_section_name
from src.app.link_utils import build_group_message_link
from src.app.translations import t
from src.config.settings import settings
from src.database.redisdb import get_redis
from src.models.assignment import AssignmentStatus, InquiryAssignment, VolunteerSection
from src.models.inquiry import Inquiry, InquiryStatus
from src.models.user import User
from src.models.volunteer import Volunteer
from src.routes.aiogram.group_router import send_answer_to_citizen
from src.app.inquiry_card import refresh_inquiry_card
from src.routes.deps.db_session import DBSession

logger = logging.getLogger(__name__)

assign_router = Router(name="inquiry_assign")

SEEN_TTL = 3600


def _admin_lang(admin_id: int, db_session: DBSession) -> str:
    user = User.get_by_user_id(admin_id, db_session)
    return user.language if user and user.language else "uz"


async def _is_assign_admin(query: CallbackQuery, bot: Bot) -> bool:
    uid = query.from_user.id if query.from_user else 0
    return bool(uid and settings.is_admin(uid))


def _remember_seen(inquiry_id: int, admin_id: int, assigned: int | None):
    try:
        r = get_redis(is_async=False)
        r.set(f"inq_assign_seen:{inquiry_id}:{admin_id}", str(assigned or 0), ex=SEEN_TTL)
    except Exception:
        pass


def _read_seen(inquiry_id: int, admin_id: int) -> int | None:
    try:
        r = get_redis(is_async=False)
        v = r.get(f"inq_assign_seen:{inquiry_id}:{admin_id}")
        if v is None:
            return None
        v = v.decode() if isinstance(v, bytes) else v
        return int(v) or None
    except Exception:
        return None


def _volunteer_display(vol: Volunteer, db_session: DBSession) -> tuple[str, str | None]:
    name = vol.full_name or str(vol.user_id)
    username = None
    try:
        user = User.get_by_user_id(vol.user_id, db_session)
        if user and user.username:
            username = user.username
    except Exception:
        pass
    return name, username


def collect_candidates(db_session: DBSession, inquiry: Inquiry) -> tuple[list[dict], str | None]:
    section = normalize_section_name(inquiry.section_name)
    active = Volunteer.get_active_volunteers(db_session)
    by_uid = {v.user_id: v for v in active}

    member_ids: set[int] = set()
    if section:
        for row in VolunteerSection.get_section_members(section, db_session):
            if row.volunteer_user_id in by_uid:
                member_ids.add(row.volunteer_user_id)

    open_rows = db_session.exec(
        select(InquiryAssignment.volunteer_user_id, func.count()).where(
            InquiryAssignment.status.in_(AssignmentStatus.OPEN)
        ).group_by(InquiryAssignment.volunteer_user_id)
    ).all()
    open_counts = {uid: c for uid, c in open_rows}

    last_map: dict[int, object] = {}
    if section:
        last_rows = db_session.exec(
            select(InquiryAssignment.volunteer_user_id, func.max(InquiryAssignment.assigned_at)).where(
                InquiryAssignment.section_name == section
            ).group_by(InquiryAssignment.volunteer_user_id)
        ).all()
        last_map = {uid: ts for uid, ts in last_rows}

    cutoff = datetime.now() - timedelta(days=30)
    recent_rows = db_session.exec(
        select(Inquiry.responder_id, func.count()).where(
            Inquiry.responder_id != None,  # noqa: E711
            Inquiry.replied_at != None,  # noqa: E711
            Inquiry.replied_at >= cutoff,
        ).group_by(Inquiry.responder_id)
    ).all()
    recent_counts = {uid: c for uid, c in recent_rows if uid in by_uid}

    prev_uid = None
    if inquiry.user_id:
        prev_inq = db_session.exec(
            select(Inquiry).where(
                Inquiry.user_id == inquiry.user_id,
                Inquiry.responder_id != None,  # noqa: E711
                Inquiry.replied_at != None,  # noqa: E711
            ).order_by(Inquiry.replied_at.desc()).limit(1)
        ).first()
        if prev_inq and prev_inq.responder_id in by_uid:
            prev_uid = prev_inq.responder_id

    def row(uid: int) -> dict:
        return {
            "user_id": uid,
            "last_assigned_at": last_map.get(uid),
            "open_count": open_counts.get(uid, 0),
            "recent_replies": recent_counts.get(uid, 0),
        }

    section_ranked = rank_section_candidates([row(uid) for uid in member_ids if uid != prev_uid])
    other_ranked = rank_section_candidates([row(uid) for uid in by_uid if uid not in member_ids and uid != prev_uid])

    entries: list[dict] = []
    if prev_uid is not None:
        entries.append({"vol": by_uid[prev_uid], "open": open_counts.get(prev_uid, 0), "other": False, "prev": True})
    for r in section_ranked:
        entries.append({"vol": by_uid[r["user_id"]], "open": r["open_count"], "other": False, "prev": False})
    for r in other_ranked:
        entries.append({"vol": by_uid[r["user_id"]], "open": r["open_count"], "other": True, "prev": False})
    return entries, section


def render_list_markup(inquiry_id: int, entries: list[dict], page: int, total_pages: int, lang: str):
    builder = InlineKeyboardBuilder()
    for e in entries:
        vol = e["vol"]
        label = f"{vol.full_name[:28]} • {t('assign_open', lang, n=e['open'])}"
        if e["other"]:
            label += f" ({t('assign_other_section', lang)})"
        if e["prev"]:
            label = f"⭐ {label}"
        cb = assign_pick_cb(inquiry_id, vol.user_id)
        if not cb_within_limit(cb):
            continue
        builder.button(text=label, callback_data=cb)
    builder.adjust(1)
    nav = []
    if page > 1:
        nav.append(InlineKeyboardButton(text="⬅️", callback_data=assign_list_cb(inquiry_id, page - 1)))
    nav.append(InlineKeyboardButton(text=f"📄 {page}/{total_pages}", callback_data="assign_noop"))
    if page < total_pages:
        nav.append(InlineKeyboardButton(text="➡️", callback_data=assign_list_cb(inquiry_id, page + 1)))
    builder.row(*nav)
    return builder.as_markup()


def render_list_text(inquiry: Inquiry, section: str | None, current_name: str | None, lang: str) -> str:
    text = t("assign_list_title", lang, id=inquiry.id, section=section or "—")
    if current_name:
        text += f"<br/>{t('assign_current', lang, name=html.escape(current_name))}"
    return text


def classify_dm_error(reason: str, exc: object) -> str:
    txt = f"{reason} {exc}".lower()
    if "chat not found" in txt:
        return "nostart"
    if reason == "blocked" or "bot was blocked" in txt or "user is deactivated" in txt:
        return "blocked"
    return "other"


@assign_router.callback_query(F.data == "assign_noop", is_group_callback)
async def assign_noop_callback(query: CallbackQuery):
    await query.answer()


@assign_router.callback_query(F.data.startswith("inq_assign:"), is_group_callback)
async def assign_list_callback(query: CallbackQuery, db_session: DBSession, bot: Bot):
    lang = _admin_lang(query.from_user.id, db_session)
    if not await _is_assign_admin(query, bot):
        return await query.answer(t("assign_only_admins", lang), show_alert=True)
    try:
        parts = query.data.split(":")
        inquiry_id = int(parts[1])
        page = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 1
    except (ValueError, IndexError):
        return await query.answer(t("assign_not_found", lang), show_alert=True)

    inquiry = db_session.get(Inquiry, inquiry_id)
    if not inquiry:
        return await query.answer(t("assign_not_found", lang), show_alert=True)

    entries, section = collect_candidates(db_session, inquiry)
    if not entries:
        return await query.answer(t("assign_empty", lang), show_alert=True)
    page_items, total_pages, page = paginate(entries, page, ASSIGN_PAGE_SIZE)

    current_name = None
    if inquiry.assigned_volunteer_id:
        av = Volunteer.get_by_user_id(inquiry.assigned_volunteer_id, db_session)
        if av:
            current_name = av.full_name

    _remember_seen(inquiry_id, query.from_user.id, inquiry.assigned_volunteer_id)
    msg = query.message

    try:
        await bot.send_message(
            chat_id=msg.chat.id,
            text=render_list_text(inquiry, section, current_name, lang),
            reply_markup=render_list_markup(inquiry_id, page_items, page, total_pages, lang),
            reply_to_message_id=msg.message_id,
            parse_mode=SULGUK_PARSE_MODE,
            link_preview_options=LinkPreviewOptions(is_disabled=True),
        )
    except Exception as e:
        logger.warning("Failed to send assign list for inquiry %s: %s", inquiry_id, e)
    await query.answer()


def _dm_text(inquiry: Inquiry, section: str | None, vol_lang: str) -> str:
    link = build_group_message_link(inquiry.group_id, inquiry.group_question_id)
    link_html = f'<a href="{link}">Murojaat №{inquiry.id}</a>' if link else f"Murojaat №{inquiry.id}"
    return t("assign_dm_text", vol_lang, id=inquiry.id, section=section or "—", link=link_html)


async def _forward_card_if_no_link(bot: Bot, vol_user_id: int, inquiry: Inquiry) -> None:
    """Havola bo'lmasa (oddiy guruh) kartaning o'zi volontyorga uzatiladi."""
    if build_group_message_link(inquiry.group_id, inquiry.group_question_id) or not inquiry.group_question_id:
        return
    try:
        await bot.forward_message(chat_id=vol_user_id, from_chat_id=inquiry.group_id, message_id=inquiry.group_question_id)
    except Exception as e:
        logger.info("Inquiry %s: kartani volontyorga uzatib bo'lmadi: %s", inquiry.id, e)


async def _send_volunteer_dm(bot: Bot, vol_user_id: int, text: str):
    handler = bot.send_message
    args = dict(chat_id=vol_user_id, text=text, parse_mode=SULGUK_PARSE_MODE)
    return await send_answer_to_citizen(handler, args)


async def _post_group_assign_message(bot: Bot, chat_id: int | str, inquiry: Inquiry, vol_name: str, username: str | None):
    if username:
        line1 = f"@{username}"
    else:
        line1 = f"<a href=\"tg://user?id={inquiry.assigned_volunteer_id}\">{html.escape(vol_name)}</a>"
    link = build_group_message_link(inquiry.group_id, inquiry.group_question_id)
    lines = [line1]
    if link:
        lines.append(link)
    lines.append(t("assign_group_done", "uz"))
    try:
        return await bot.send_message(
            chat_id=chat_id,
            text="<br/>".join(lines),
            reply_to_message_id=inquiry.group_question_id,
            parse_mode=SULGUK_PARSE_MODE,
            link_preview_options=LinkPreviewOptions(is_disabled=True),
        )
    except Exception as e:
        logger.warning("Failed to post assign group message for inquiry %s: %s", inquiry.id, e)
        return None


async def _show_responsible_on_card(bot: Bot, inquiry: Inquiry, db_session: DBSession) -> None:
    status = getattr(inquiry.status, "value", inquiry.status)
    if inquiry.responder_id is not None or status != InquiryStatus.active.value:
        return
    await refresh_inquiry_card(bot, inquiry, db_session)


async def _delete_list_message(query: CallbackQuery) -> None:
    try:
        await query.message.delete()
    except Exception:
        pass


def _retry_markup(inquiry_id: int, vol_user_id: int, lang: str):
    builder = InlineKeyboardBuilder()
    builder.button(text=t("assign_retry_btn", lang), callback_data=assign_retry_cb(inquiry_id, vol_user_id))
    return builder.as_markup()


async def _dm_fail_notice(bot: Bot, chat_id: int | str, inquiry: Inquiry, vol_name: str,
                          kind: str, reason: str, lang: str):
    if kind == "blocked":
        err_text = t("assign_dm_blocked", lang)
    elif kind == "nostart":
        err_text = t("assign_dm_nostart", lang)
    else:
        err_text = t("assign_dm_fail", lang, reason=reason)
    text = f"{err_text}<br/>👤 {html.escape(vol_name)} • Murojaat №{inquiry.id}"
    try:
        return await bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=_retry_markup(inquiry.id, inquiry.assigned_volunteer_id, lang),
            reply_to_message_id=inquiry.group_question_id,
            parse_mode=SULGUK_PARSE_MODE,
            link_preview_options=LinkPreviewOptions(is_disabled=True),
        )
    except Exception as e:
        logger.warning("Failed to send assign fail notice for inquiry %s: %s", inquiry.id, e)
        return None


@assign_router.callback_query(F.data.startswith("inq_assign_pick:"), is_group_callback)
async def assign_pick_callback(query: CallbackQuery, db_session: DBSession, bot: Bot):
    lang = _admin_lang(query.from_user.id, db_session)
    if not await _is_assign_admin(query, bot):
        return await query.answer(t("assign_only_admins", lang), show_alert=True)
    try:
        inquiry_id, vol_user_id = parse_assign_pair(query.data)
    except (ValueError, IndexError):
        return await query.answer(t("assign_not_found", lang), show_alert=True)

    inquiry = db_session.get(Inquiry, inquiry_id)
    if not inquiry:
        return await query.answer(t("assign_not_found", lang), show_alert=True)
    vol = Volunteer.get_by_user_id(vol_user_id, db_session)
    if not vol or not vol.is_active:
        return await query.answer(t("assign_vol_not_found", lang), show_alert=True)

    vol_name, username = _volunteer_display(vol, db_session)
    if inquiry.assigned_volunteer_id == vol_user_id:
        return await query.answer(t("assign_already", lang, name=vol_name), show_alert=True)

    seen = _read_seen(inquiry_id, query.from_user.id)
    expected = seen if seen is not None else inquiry.assigned_volunteer_id
    old_assigned = inquiry.assigned_volunteer_id

    # (1) Optimistik yozish: 2 admin poygasida yutqazgan "allaqachon" oladi
    try:
        if expected is None:
            cond = Inquiry.assigned_volunteer_id == None  # noqa: E711
        else:
            cond = Inquiry.assigned_volunteer_id == expected
        res = db_session.execute(
            update(Inquiry).where(Inquiry.id == inquiry_id, cond).values(
                assigned_volunteer_id=vol_user_id,
                assigned_at=datetime.now(),
                assign_source="admin",
            )
        )
        if res.rowcount == 0:
            db_session.rollback()
            db_session.refresh(inquiry)
            cur_name = str(inquiry.assigned_volunteer_id or "")
            if inquiry.assigned_volunteer_id:
                cur = Volunteer.get_by_user_id(inquiry.assigned_volunteer_id, db_session)
                if cur:
                    cur_name = cur.full_name
            return await query.answer(t("assign_already", lang, name=cur_name), show_alert=True)
        db_session.commit()
    except Exception as e:
        db_session.rollback()
        logger.warning("Assign DB write failed for inquiry %s: %s", inquiry_id, e)
        try:
            await query.message.edit_text(
                t("assign_db_fail", lang, reason=str(e)[:120]),
                reply_markup=_retry_markup(inquiry_id, vol_user_id, lang),
                parse_mode=SULGUK_PARSE_MODE,
            )
        except Exception:
            pass
        return await query.answer(t("assign_db_fail", lang, reason="DB"), show_alert=True)

    db_session.refresh(inquiry)
    section = normalize_section_name(inquiry.section_name)
    is_reassign = old_assigned is not None and old_assigned != vol_user_id

    if is_reassign:
        try:
            old_rows = db_session.exec(
                select(InquiryAssignment).where(
                    InquiryAssignment.inquiry_id == inquiry_id,
                    InquiryAssignment.status.in_(AssignmentStatus.OPEN),
                )
            ).all()
            for r in old_rows:
                r.status = AssignmentStatus.reassigned
                db_session.add(r)
            db_session.commit()
        except Exception as e:
            db_session.rollback()
            logger.warning("Failed to mark old assignments reassigned (inquiry %s): %s", inquiry_id, e)

    assignment = InquiryAssignment(
        inquiry_id=inquiry_id,
        volunteer_user_id=vol_user_id,
        section_name=section or inquiry.section_name,
        assigned_by=query.from_user.id,
        status=AssignmentStatus.assigned,
    )
    db_session.add(assignment)
    db_session.commit()
    db_session.refresh(assignment)

    # (2) Volontyorga DM
    vol_user = User.get_by_user_id(vol_user_id, db_session)
    vol_lang = vol_user.language if vol_user and vol_user.language else "uz"
    ok, reason, exc = await _send_volunteer_dm(bot, vol_user_id, _dm_text(inquiry, section, vol_lang))
    assignment.notify_attempts += 1
    assignment.last_notify_at = datetime.now()
    if ok:
        assignment.status = AssignmentStatus.notified
        db_session.add(assignment)
        db_session.commit()
        await _forward_card_if_no_link(bot, vol_user_id, inquiry)
    else:
        kind = classify_dm_error(reason, exc)
        assignment.status = AssignmentStatus.notify_failed
        assignment.notify_error = str(exc or reason)[:500]
        db_session.add(assignment)
        db_session.commit()
        group_msg = await _post_group_assign_message(bot, query.message.chat.id, inquiry, vol_name, username)
        if group_msg:
            inquiry.assign_message_id = group_msg.message_id
            db_session.add(inquiry)
            db_session.commit()
        await _show_responsible_on_card(bot, inquiry, db_session)
        await _dm_fail_notice(bot, query.message.chat.id, inquiry, vol_name, kind, reason, lang)
        await _delete_list_message(query)
        return await query.answer(t("assign_dm_fail", lang, reason=reason[:80]), show_alert=True)

    # (3) Guruhga xabar + karta tahriri
    group_msg = await _post_group_assign_message(bot, query.message.chat.id, inquiry, vol_name, username)
    if group_msg:
        inquiry.assign_message_id = group_msg.message_id
        db_session.add(inquiry)
        db_session.commit()
    await _show_responsible_on_card(bot, inquiry, db_session)

    if is_reassign and old_assigned:
        try:
            await bot.send_message(
                chat_id=old_assigned,
                text=t("assign_moved_dm", "uz", id=inquiry.id),
                parse_mode=SULGUK_PARSE_MODE,
            )
        except Exception as e:
            logger.warning("Failed to notify previous volunteer %s: %s", old_assigned, e)

    await _delete_list_message(query)
    await query.answer(t("assign_sent_ok", lang), show_alert=False)


@assign_router.callback_query(F.data.startswith("inq_assign_retry:"), is_group_callback)
async def assign_retry_callback(query: CallbackQuery, db_session: DBSession, bot: Bot):
    lang = _admin_lang(query.from_user.id, db_session)
    if not await _is_assign_admin(query, bot):
        return await query.answer(t("assign_only_admins", lang), show_alert=True)
    try:
        inquiry_id, vol_user_id = parse_assign_pair(query.data)
    except (ValueError, IndexError):
        return await query.answer(t("assign_not_found", lang), show_alert=True)

    inquiry = db_session.get(Inquiry, inquiry_id)
    if not inquiry or inquiry.assigned_volunteer_id != vol_user_id:
        try:
            await query.message.edit_text(t("assign_sent_ok", lang), parse_mode=SULGUK_PARSE_MODE)
        except Exception:
            pass
        return await query.answer(t("assign_sent_ok", lang), show_alert=False)

    assignment = db_session.exec(
        select(InquiryAssignment).where(
            InquiryAssignment.inquiry_id == inquiry_id,
            InquiryAssignment.volunteer_user_id == vol_user_id,
        ).order_by(InquiryAssignment.id.desc())
    ).first()
    if not assignment or assignment.status != AssignmentStatus.notify_failed:
        try:
            await query.message.edit_text(t("assign_sent_ok", lang), parse_mode=SULGUK_PARSE_MODE)
        except Exception:
            pass
        return await query.answer(t("assign_sent_ok", lang), show_alert=False)

    # Takroriy DM yuborilmasin: avval holatni atomar egallaymiz
    try:
        res = db_session.execute(
            update(InquiryAssignment).where(
                InquiryAssignment.id == assignment.id,
                InquiryAssignment.status == AssignmentStatus.notify_failed,
            ).values(status=AssignmentStatus.notified, last_notify_at=datetime.now())
        )
        if res.rowcount == 0:
            db_session.rollback()
            try:
                await query.message.edit_text(t("assign_sent_ok", lang), parse_mode=SULGUK_PARSE_MODE)
            except Exception:
                pass
            return await query.answer(t("assign_sent_ok", lang), show_alert=False)
        db_session.commit()
    except Exception as e:
        db_session.rollback()
        return await query.answer(t("assign_db_fail", lang, reason=str(e)[:80]), show_alert=True)

    section = normalize_section_name(inquiry.section_name)
    vol_user = User.get_by_user_id(vol_user_id, db_session)
    vol_lang = vol_user.language if vol_user and vol_user.language else "uz"
    ok, reason, exc = await _send_volunteer_dm(bot, vol_user_id, _dm_text(inquiry, section, vol_lang))

    db_session.refresh(assignment)
    assignment.notify_attempts += 1
    assignment.last_notify_at = datetime.now()
    if ok:
        db_session.add(assignment)
        db_session.commit()
        await _forward_card_if_no_link(bot, vol_user_id, inquiry)
        await _delete_list_message(query)
        return await query.answer(t("assign_sent_ok", lang), show_alert=False)

    assignment.status = AssignmentStatus.notify_failed
    assignment.notify_error = str(exc or reason)[:500]
    db_session.add(assignment)
    db_session.commit()
    kind = classify_dm_error(reason, exc)
    vol = Volunteer.get_by_user_id(vol_user_id, db_session)
    vol_name = vol.full_name if vol else str(vol_user_id)
    await _delete_list_message(query)
    await _dm_fail_notice(bot, query.message.chat.id, inquiry, vol_name, kind, reason, lang)
    return await query.answer(t("assign_dm_fail", lang, reason=reason[:80]), show_alert=True)
