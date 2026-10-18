import time
import secrets
import logging
from typing import Annotated
from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from src.config.settings import settings
from src.database.mysql import engine
from src.models.volunteer import Volunteer
from src.models.lawyer import OfficialLawyer
from src.models.inquiry import Inquiry, InquiryStatus
from src.models.appointment import Appointment, AppointmentStatus

logger = logging.getLogger(__name__)

website_router = APIRouter(tags=["Website Integration"])


class VolunteerStatResponse(BaseModel):
    name: str = Field(..., description="Volontyor yoki yuristning to'liq ismi")
    resolved_count: int = Field(..., description="Yechilgan / javob berilgan murojaatlar soni")
    satisfaction_rate: float = Field(..., description="Foydalanuvchilar qoldirgan ijobiy baho foizi (yoki o'rtacha ball foizda)")
    status: str = Field(default="online", description="Faol yoki onlayn holati")


# Xotirada yengil kesh (Cache)
_cached_stats: list[dict] | None = None
_last_cache_time: float = 0.0
CACHE_TTL_SECONDS: int = 30  # 30 soniyalik kesh ma'lumotlar bazasini og'irlashtirmaydi


async def verify_website_token(
    authorization: Annotated[str | None, Header()] = None,
    token: str | None = None,
    api_key: str | None = None,
    secret: str | None = None,
) -> bool:
    """
    Rasmiy veb-sayt (WordPress) so'rovlarini tekshirish:
    1. Header orqali: Authorization: Bearer <WEBSITE_API_SECRET_KEY>
    2. URL query orqali: ?token=... yoki ?api_key=... yoki ?secret=...
    3. Agar token ko'rsatilmagan bo'lsa ham, bu faqat umumiy ommaviy volontyorlar
       statistikasi bo'lgani sababli, veb-saytda uzilish bo'lmasligi uchun ruxsat beriladi.
    """
    expected_token = getattr(settings, "WEBSITE_API_SECRET_KEY", None)
    provided_token = None

    if authorization:
        parts = authorization.strip().split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            provided_token = parts[1]
        elif len(parts) == 1:
            provided_token = parts[0]

    if not provided_token:
        provided_token = token or api_key or secret

    # Agar token yuborilgan bo'lsa, uni tekshiramiz
    if expected_token and provided_token:
        if not secrets.compare_digest(provided_token, expected_token):
            logger.warning("Veb-sayt API so'rovida noto'g'ri token uzatildi")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or unauthorized API token",
                headers={"WWW-Authenticate": "Bearer"}
            )

    return True


def fetch_volunteers_stats_from_db() -> list[dict]:
    """
    Ma'lumotlar bazasidan faol volontyorlar va rasmiy yuristlarning
    yechilgan murojaatlari va ijobiy baholash ko'rsatkichlarini hisoblaydi.
    """
    try:
        with Session(engine) as session:
            # 1. Faol volontyorlar
            volunteers = session.exec(select(Volunteer).where(Volunteer.is_active == True)).all()

            # 2. Faol yuristlar
            lawyers = session.exec(select(OfficialLawyer).where(OfficialLawyer.is_active == True)).all()

            # 3. Javob berilgan/yechilgan barcha murojaatlar
            inquiries = session.exec(select(Inquiry).where(Inquiry.responder_id.isnot(None))).all()

            # 4. Yakunlangan yurist qabullari
            appointments = session.exec(select(Appointment).where(Appointment.lawyer_id.isnot(None))).all()
    except Exception as e:
        logger.error("Bazadan statistika olishda xatolik: %s", e)
        # Agar bazada muammo bo'lsa, xatolik chiqarmay bo'sh ro'yxat yoki kesh qaytarish
        return _cached_stats or []

    # Murojaatlar bo'yicha agregatsiya
    inquiry_stats: dict[int, dict] = {}
    for inq in inquiries:
        r_id = inq.responder_id
        if not r_id:
            continue
        if r_id not in inquiry_stats:
            inquiry_stats[r_id] = {"resolved": 0, "ratings": []}

        # Yechilgan yoki javob berilgan deb hisoblash
        if inq.status in [InquiryStatus.replied, InquiryStatus.closed] or inq.answer:
            inquiry_stats[r_id]["resolved"] += 1

        if inq.rating is not None and inq.rating > 0:
            inquiry_stats[r_id]["ratings"].append(inq.rating)

    # Qabullar (Appointments) bo'yicha agregatsiya
    appointment_stats: dict[int, dict] = {}
    for app in appointments:
        l_id = app.lawyer_id
        if not l_id:
            continue
        if l_id not in appointment_stats:
            appointment_stats[l_id] = {"completed": 0, "ratings": []}

        if app.status == AppointmentStatus.completed:
            appointment_stats[l_id]["completed"] += 1

        if app.rating is not None and app.rating > 0:
            appointment_stats[l_id]["ratings"].append(app.rating)

    result = []
    seen_user_ids = set()

    # 1. Rasmiy yuristlar natijalari
    for lawyer in lawyers:
        u_id = lawyer.user_id
        seen_user_ids.add(u_id)

        inq_data = inquiry_stats.get(u_id, {"resolved": 0, "ratings": []})
        app_data = appointment_stats.get(u_id, {"completed": 0, "ratings": []})

        resolved = inq_data["resolved"] + app_data["completed"]
        all_ratings = inq_data["ratings"] + app_data["ratings"]

        if all_ratings:
            avg_score = sum(all_ratings) / len(all_ratings)
            satisfaction = round((avg_score / 5.0) * 100, 1)
        else:
            satisfaction = 100.0  # Bahosi hali bo'lmasa standart 100%

        lawyer_name = (lawyer.full_name or "").strip() or f"Huquqshunos {u_id}"
        result.append({
            "name": lawyer_name,
            "resolved_count": resolved,
            "satisfaction_rate": satisfaction,
            "status": "online" if lawyer.is_active else "offline"
        })

    # 2. Faol volontyorlar natijalari
    for vol in volunteers:
        u_id = vol.user_id
        if u_id in seen_user_ids:
            continue
        seen_user_ids.add(u_id)

        inq_data = inquiry_stats.get(u_id, {"resolved": 0, "ratings": []})
        resolved = inq_data["resolved"]
        all_ratings = inq_data["ratings"]

        if all_ratings:
            avg_score = sum(all_ratings) / len(all_ratings)
            satisfaction = round((avg_score / 5.0) * 100, 1)
        else:
            satisfaction = 100.0  # Bahosi hali bo'lmasa standart 100%

        vol_name = (vol.full_name or "").strip() or f"Volontyor {u_id}"
        result.append({
            "name": vol_name,
            "resolved_count": resolved,
            "satisfaction_rate": satisfaction,
            "status": "online" if vol.is_active else "offline"
        })

    # Saralash: eng ko'p javob berganlar va qoniqish foizi yuqorilar oldinda
    result.sort(key=lambda x: (x["resolved_count"], x["satisfaction_rate"]), reverse=True)
    return result


def get_cached_volunteers_stats(force_refresh: bool = False) -> list[dict]:
    """
    Statistikani keshdan olish yoki zarur bo'lsa yangilab qaytarish.
    """
    global _cached_stats, _last_cache_time
    now = time.time()

    if not force_refresh and _cached_stats is not None and (now - _last_cache_time) < CACHE_TTL_SECONDS:
        return _cached_stats

    stats = fetch_volunteers_stats_from_db()
    _cached_stats = stats
    _last_cache_time = now
    return stats


@website_router.get(
    "/volunteers-stats",
    response_model=list[VolunteerStatResponse],
    summary="Volontyorlar va huquqshunoslar statistikasi (Veb-sayt integratsiyasi uchun)",
    dependencies=[Depends(verify_website_token)]
)
async def get_volunteers_stats_endpoint():
    """
    Rasmiy veb-sayt (WordPress) uchun volontyor va huquqshunoslarning real natijalari:
    - Yechilgan / javob berilgan murojaatlar soni
    - Ijobiy baholash foizi
    - Holati (online)
    """
    return get_cached_volunteers_stats()
