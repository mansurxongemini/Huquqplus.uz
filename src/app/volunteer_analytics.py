import html
import logging
from datetime import datetime, timedelta
from sqlalchemy import func
from sqlmodel import Session, select
from sulguk import SULGUK_PARSE_MODE
from aiogram import Bot

from src.database.mysql import engine
from src.models.inquiry import Inquiry
from src.models.volunteer import Volunteer
from src.models.lawyer import OfficialLawyer
from src.models.user import User

logger = logging.getLogger(__name__)


def get_month_date_range(ref_date: datetime | None = None) -> tuple[datetime, datetime]:
    """Returns (start_of_month, end_of_month) for the given date (default current date)."""
    now = ref_date or datetime.now()
    start_date = datetime(now.year, now.month, 1, 0, 0, 0)
    if now.month == 12:
        end_date = datetime(now.year + 1, 1, 1, 0, 0, 0)
    else:
        end_date = datetime(now.year, now.month + 1, 1, 0, 0, 0)
    return start_date, end_date


def calculate_volunteer_stats(date_range: tuple[datetime | None, datetime | None] | None = None, volunteers_only: bool = False):
    """
    Calculates detailed performance metrics and KPI scores for specialists/volunteers.
    Formula:
    KPI = (Answered * 10) + (5-star * 15) + (4-star * 10) - (1-2 star * 10) + (Fast replies < 1 hour * 5)
    """
    with Session(engine) as session:
        # Fetch inquiries in date range
        stmt = select(Inquiry).where(Inquiry.responder_id != None)
        if date_range:
            start_date, end_date = date_range
            date_col = func.coalesce(Inquiry.replied_at, Inquiry.created_at)
            if start_date is not None:
                stmt = stmt.where(date_col >= start_date)
            if end_date is not None:
                stmt = stmt.where(date_col < end_date)
        inquiries = session.exec(stmt).all()

        # Fetch registered volunteers
        volunteers = session.exec(select(Volunteer)).all()
        vol_map = {v.user_id: v for v in volunteers}

        # Fetch official lawyers
        lawyers = session.exec(select(OfficialLawyer)).all()
        lawyer_map = {l.user_id: l for l in lawyers}

        # Fetch users
        users = session.exec(select(User)).all()
        user_map = {u.user_id: u for u in users}

    # Aggregate by responder_id
    stats = {}

    for inq in inquiries:
        resp_id = inq.responder_id
        if not resp_id:
            continue

        if volunteers_only and resp_id not in vol_map:
            continue

        if resp_id not in stats:
            vol = vol_map.get(resp_id)
            lawyer = lawyer_map.get(resp_id)
            user = user_map.get(resp_id)

            if vol:
                name = vol.full_name
                role = "Volontyor"
                phone = vol.phone_number
                study_work = vol.study_or_work
                birth_year = vol.birth_year
            elif lawyer:
                name = lawyer.full_name
                role = "yurist"
                phone = lawyer.phone or "-"
                study_work = lawyer.specialization or "Yurist"
                birth_year = "-"
            elif user:
                name = f"{user.first_name or ''} {user.last_name or ''}".strip() or f"Foydalanuvchi {resp_id}"
                role = "Noma'lum mutaxassis"
                phone = user.phone or "-"
                study_work = "-"
                birth_year = user.birth_year or "-"
            else:
                name = f"Mutaxassis {resp_id}"
                role = "Mutaxassis"
                phone = "-"
                study_work = "-"
                birth_year = "-"

            stats[resp_id] = {
                "user_id": resp_id,
                "name": name,
                "role": role,
                "phone": phone,
                "study_work": study_work,
                "birth_year": birth_year,
                "inquiries_count": 0,
                "ratings": [],
                "five_star_count": 0,
                "four_star_count": 0,
                "negative_count": 0,
                "response_times_minutes": [],
                "fast_responses_count": 0,
            }

        st = stats[resp_id]
        st["inquiries_count"] += 1

        # Rating metrics
        if inq.rating is not None:
            st["ratings"].append(inq.rating)
            if inq.rating == 5:
                st["five_star_count"] += 1
            elif inq.rating == 4:
                st["four_star_count"] += 1
            elif inq.rating <= 2:
                st["negative_count"] += 1

        # Response time metrics
        if inq.created_at and inq.replied_at:
            try:
                rep_time = inq.replied_at
                if isinstance(rep_time, str):
                    rep_time = datetime.fromisoformat(rep_time)
                created_time = inq.created_at
                if isinstance(created_time, str):
                    created_time = datetime.fromisoformat(created_time)

                diff_seconds = (rep_time - created_time).total_seconds()
                if diff_seconds >= 0:
                    diff_minutes = diff_seconds / 60.0
                    st["response_times_minutes"].append(diff_minutes)
                    if diff_minutes <= 60.0:
                        st["fast_responses_count"] += 1
            except Exception:
                pass

    # Calculate final scores and averages
    result_list = []
    for resp_id, s in stats.items():
        avg_rating = (sum(s["ratings"]) / len(s["ratings"])) if s["ratings"] else 0.0
        avg_resp_min = (sum(s["response_times_minutes"]) / len(s["response_times_minutes"])) if s["response_times_minutes"] else 0.0

        # KPI Formula:
        kpi_score = (
            (s["inquiries_count"] * 10)
            + (s["five_star_count"] * 15)
            + (s["four_star_count"] * 10)
            - (s["negative_count"] * 10)
            + (s["fast_responses_count"] * 5)
        )
        if kpi_score < 0:
            kpi_score = 0

        # Human-readable response time
        if avg_resp_min == 0:
            resp_str = "Mavjud emas"
        elif avg_resp_min < 60:
            resp_str = f"{int(avg_resp_min)} daqiqa"
        else:
            hours = int(avg_resp_min // 60)
            mins = int(avg_resp_min % 60)
            resp_str = f"{hours} soat {mins} daq"

        s["avg_rating"] = round(avg_rating, 2)
        s["avg_response_minutes"] = round(avg_resp_min, 1)
        s["avg_response_str"] = resp_str
        s["kpi_score"] = kpi_score
        result_list.append(s)

    # Sort descending by KPI score, then by inquiries count, then by avg_rating
    result_list.sort(key=lambda x: (x["kpi_score"], x["inquiries_count"], x["avg_rating"]), reverse=True)

    # Assign rank numbers (handling ties properly)
    current_rank = 1
    for idx, item in enumerate(result_list):
        if idx > 0 and item["kpi_score"] == result_list[idx - 1]["kpi_score"]:
            item["rank"] = result_list[idx - 1]["rank"]
        else:
            item["rank"] = current_rank
        current_rank = idx + 2

    return result_list


def get_top_volunteers_with_ties(stats_list: list[dict], top_limit: int = 5) -> list[dict]:
    """
    Returns top N volunteers. If the N-th position has ties, all tied volunteers are included!
    """
    if not stats_list:
        return []

    if len(stats_list) <= top_limit:
        return stats_list

    threshold_score = stats_list[top_limit - 1]["kpi_score"]
    return [s for s in stats_list if s["kpi_score"] >= threshold_score]


def get_week_date_range(ref_date: datetime | None = None) -> tuple[datetime, datetime]:
    """
    Returns (start_of_week, end_of_week).
    Start is Monday 00:00:00, end is next Monday 00:00:00.
    """
    now = ref_date or datetime.now()
    start_date = datetime(now.year, now.month, now.day, 0, 0, 0) - timedelta(days=now.weekday())
    end_date = start_date + timedelta(days=7)
    return start_date, end_date


def get_prev_week_date_range(ref_date: datetime | None = None) -> tuple[datetime, datetime]:
    """
    Returns (start_of_prev_week, end_of_prev_week).
    """
    now = ref_date or datetime.now()
    start_current = datetime(now.year, now.month, now.day, 0, 0, 0) - timedelta(days=now.weekday())
    start_prev = start_current - timedelta(days=7)
    end_prev = start_current
    return start_prev, end_prev


def format_volunteer_weekly_digest_text(
    vol: Volunteer,
    period_str: str,
    tw: dict | None,
    pw: dict | None,
    ov: dict | None,
    pov: dict | None,
    total_vols: int
) -> str:
    inquiries_this_week = tw["inquiries_count"] if tw else 0
    kpi_this_week = tw["kpi_score"] if tw else 0
    avg_speed_this_week = tw["avg_response_str"] if tw else "Mavjud emas"
    rating_this_week = f"⭐ {tw['avg_rating']} / 5.0" if (tw and tw["avg_rating"] > 0) else "baho berilmagan"

    kpi_prev_week = pw["kpi_score"] if pw else 0

    diff = kpi_this_week - kpi_prev_week
    if diff > 0:
        kpi_comparison = f"📈 <b>+{diff} ballga o‘sgan</b> (o‘tgan haftada {kpi_prev_week} ball, bu hafta {kpi_this_week} ball)"
    elif diff < 0:
        kpi_comparison = f"📉 <b>{abs(diff)} ballga kamaygan</b> (o‘tgan haftada {kpi_prev_week} ball, bu hafta {kpi_this_week} ball)"
    else:
        if kpi_this_week > 0:
            kpi_comparison = f"➖ <b>O‘zgarmagan</b> ({kpi_this_week} ball)"
        else:
            kpi_comparison = "➖ <b>0 ball</b> (ushbu haftada hali javob berilmadi)"

    current_rank = ov.get("rank", "-") if ov else "-"
    prev_rank = pov.get("rank", "-") if pov else "-"

    if current_rank != "-" and prev_rank != "-":
        rdiff = prev_rank - current_rank
        if rdiff > 0:
            rank_comparison = f"📈 <b>{rdiff} pog‘ona ko‘tarildi</b> ({prev_rank}-o‘rindan {current_rank}-o‘ringa)"
        elif rdiff < 0:
            rank_comparison = f"📉 <b>{abs(rdiff)} pog‘ona pastladi</b> ({prev_rank}-o‘rindan {current_rank}-o‘ringa)"
        else:
            rank_comparison = f"➖ <b>{current_rank}-o‘rinda saqlanib turibdi</b>"
    elif current_rank != "-":
        rank_comparison = f"🆕 <b>Yangi</b> ({current_rank}-o‘rin)"
    else:
        rank_comparison = "—"

    total_kpi = ov["kpi_score"] if ov else 0
    total_answered = ov["inquiries_count"] if ov else 0
    safe_name = html.escape(vol.full_name)

    text = f"""
🌟 <b>Haftalik faoliyat hisobotingiz</b><br/>
📅 <b>Davr:</b> {period_str}<br/>
━━━━━━━━━━━━━━━━━━━━━<br/>
Hurmatli <b>{safe_name}</b>!<br/>
Ushbu hafta davomida fuqarolarga beminnat huquqiy yordam ko‘rsatganingiz uchun samimiy minnatdorchilik bildiramiz.<br/><br/>

📊 <b>Ushbu haftadagi natijalaringiz:</b><br/>
• 📩 <b>Javob berilgan murojaatlar:</b> <b>{inquiries_this_week}</b> ta<br/>
• 🎯 <b>Haftalik KPI ballingiz:</b> <b>{kpi_this_week}</b> ball<br/>
• 📈 <b>O‘tgan haftaga nisbatan:</b> {kpi_comparison}<br/>
• ⚡️ <b>O‘rtacha javob tezligi:</b> {avg_speed_this_week}<br/>
• ⭐️ <b>Haftalik o‘rtacha baho:</b> {rating_this_week}<br/><br/>

🏆 <b>Umumiy reytingdagi holatingiz:</b><br/>
• 🎖 <b>O‘rningiz:</b> <b>{current_rank}-o‘rin</b> (jami {total_vols} ta volontyor ichida)<br/>
• 📊 <b>O‘rin o‘zgarishi:</b> {rank_comparison}<br/>
• 🌟 <b>Jami to‘plangan KPI ball:</b> <b>{total_kpi}</b> ball (Jami: {total_answered} ta javob)<br/>
━━━━━━━━━━━━━━━━━━━━━<br/>
💬 <i>Barcha fuqarolar izohlari va to‘liq ko‘rsatkichlaringizni ko‘rish uchun botga /myresult buyrug‘ini yuboring.</i>
"""
    return text.strip()


async def dispatch_weekly_volunteer_digest(bot: Bot, session: Session, is_manual: bool = False) -> tuple[int, int]:
    """
    Sends the weekly personal performance digest to all active volunteers.
    Returns (sent_count, failed_count).
    """
    now = datetime.now()
    active_vols = session.exec(select(Volunteer).where(Volunteer.is_active == True)).all()
    if not active_vols:
        return 0, 0

    sent_count = 0
    failed_count = 0

    start_current, end_current = get_week_date_range(now)
    start_prev, end_prev = get_prev_week_date_range(now)

    this_week_stats = calculate_volunteer_stats(date_range=(start_current, now), volunteers_only=True)
    tw_map = {s["user_id"]: s for s in this_week_stats}

    prev_week_stats = calculate_volunteer_stats(date_range=(start_prev, end_prev), volunteers_only=True)
    pw_map = {s["user_id"]: s for s in prev_week_stats}

    overall_stats = calculate_volunteer_stats(date_range=None, volunteers_only=True)
    ov_map = {s["user_id"]: s for s in overall_stats}

    prev_overall_stats = calculate_volunteer_stats(date_range=(None, start_current), volunteers_only=True)
    pov_map = {s["user_id"]: s for s in prev_overall_stats}

    total_vols = len(overall_stats)
    period_str = f"{start_current.strftime('%d.%m.%Y')} — {now.strftime('%d.%m.%Y')}"

    for vol in active_vols:
        msg_text = format_volunteer_weekly_digest_text(
            vol=vol,
            period_str=period_str,
            tw=tw_map.get(vol.user_id),
            pw=pw_map.get(vol.user_id),
            ov=ov_map.get(vol.user_id),
            pov=pov_map.get(vol.user_id),
            total_vols=total_vols,
        )
        try:
            await bot.send_message(
                chat_id=vol.user_id,
                text=msg_text,
                parse_mode=SULGUK_PARSE_MODE
            )
            sent_count += 1
        except Exception as e:
            failed_count += 1
            logger.warning("Failed to send weekly digest to volunteer %s (%s): %s", vol.user_id, vol.full_name, e)

    return sent_count, failed_count
