from datetime import datetime
from sqlmodel import Session, select
from src.database.mysql import engine
from src.models.inquiry import Inquiry, InquiryStatus
from src.models.volunteer import Volunteer
from src.models.lawyer import OfficialLawyer
from src.models.user import User


def get_month_date_range(ref_date: datetime | None = None) -> tuple[datetime, datetime]:
    """Returns (start_of_month, end_of_month) for the given date (default current date)."""
    now = ref_date or datetime.now()
    start_date = datetime(now.year, now.month, 1, 0, 0, 0)
    if now.month == 12:
        end_date = datetime(now.year + 1, 1, 1, 0, 0, 0)
    else:
        end_date = datetime(now.year, now.month + 1, 1, 0, 0, 0)
    return start_date, end_date


def calculate_volunteer_stats(date_range: tuple[datetime, datetime] | None = None, volunteers_only: bool = False):
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
            stmt = stmt.where(Inquiry.created_at >= start_date, Inquiry.created_at < end_date)
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
