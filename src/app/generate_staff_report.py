import os
import re
from datetime import datetime, timedelta, timezone
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from sqlmodel import Session, select
from src.database.mysql import engine
from src.models.ai_answer import AiAnswer
from src.models.inquiry import Inquiry, InquiryStatus
from src.models.appointment import Appointment, AppointmentStatus
from src.models.lawyer import OfficialLawyer
from src.models.volunteer import Volunteer
from src.models.user import User, Region
from src.app.enums import regions_uz, disability_types_uz, disability_states_uz, gender_types_uz


def parse_date(date_str: str, is_end: bool = False) -> datetime:
    """Turli formatdagi sanalarni tahlil qiladi (DD.MM.YYYY, YYYY-MM-DD va h.k.)"""
    clean_str = date_str.strip()
    dt = None
    formats = [
        "%d.%m.%Y",
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%Y.%m.%d",
        "%Y/%m/%d",
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(clean_str, fmt)
            break
        except ValueError:
            continue

    if dt is None:
        raise ValueError(f"Noto'g'ri sana formati: '{date_str}'. Iltimos, DD.MM.YYYY (masalan: 01.08.2026) yoki YYYY-MM-DD ko'rinishida kiriting.")

    if is_end:
        return dt.replace(hour=23, minute=59, second=59, microsecond=999999, tzinfo=timezone.utc)
    else:
        return dt.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=timezone.utc)


def get_preset_range(preset: str) -> tuple[datetime, datetime]:
    """Oldindan belgilangan davrlarni hisoblaydi"""
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = now.replace(hour=23, minute=59, second=59, microsecond=999999)

    if preset == "today":
        return today_start, today_end
    elif preset == "yesterday":
        yest = today_start - timedelta(days=1)
        return yest, yest.replace(hour=23, minute=59, second=59, microsecond=999999)
    elif preset == "week":
        start = today_start - timedelta(days=today_start.weekday())
        return start, today_end
    elif preset == "month":
        start = today_start.replace(day=1)
        return start, today_end
    elif preset == "last_month":
        first_this_month = today_start.replace(day=1)
        last_month_end = first_this_month - timedelta(seconds=1)
        last_month_start = last_month_end.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return last_month_start, last_month_end
    elif preset == "year":
        start = today_start.replace(month=1, day=1)
        return start, today_end
    else:
        raise ValueError(f"Noma'lum preset: {preset}")


def parse_date_range_string(raw_input: str) -> tuple[datetime | None, datetime | None, str, str]:
    """
    Kiritilgan matndan sana oralig'ini ajratib oladi.
    Qo'llab-quvvatlanadi:
      - 01.08.2026#01.10.2026
      - 01.08.2026-01.10.2026
      - 01.08.2026 01.10.2026
      - 2026-08-01#2026-10-01
      - today, month, last_month, all
    Returns: (start_dt, end_dt, period_name, file_suffix)
    """
    text = raw_input.strip()
    if text.startswith("/report"):
        text = text[len("/report"):].strip()

    if not text:
        raise ValueError("Sana oralig'i ko'rsatilmadi.")

    # Preset keywords
    low = text.lower()
    if low in ["today", "bugun"]:
        s, e = get_preset_range("today")
        return s, e, f"Bugun ({s.strftime('%d.%m.%Y')})", f"{s.strftime('%Y%m%d')}_bugun"
    elif low in ["month", "oy", "joriy oy", "shu oy"]:
        s, e = get_preset_range("month")
        return s, e, f"Joriy oy ({s.strftime('%m.%Y')})", f"{s.strftime('%Y%m')}_joriy_oy"
    elif low in ["last_month", "otgan oy", "o'tgan oy"]:
        s, e = get_preset_range("last_month")
        return s, e, f"O'tgan oy ({s.strftime('%m.%Y')})", f"{s.strftime('%Y%m')}_otgan_oy"
    elif low in ["all", "barchasi", "barcha", "hamma"]:
        return None, None, "Barcha davr uchun", "barcha_davr"

    # Delimiters
    if "#" in text:
        parts = [p.strip() for p in text.split("#") if p.strip()]
    elif " — " in text:
        parts = [p.strip() for p in text.split(" — ") if p.strip()]
    elif " – " in text:
        parts = [p.strip() for p in text.split(" – ") if p.strip()]
    elif ".." in text:
        parts = [p.strip() for p in text.split("..") if p.strip()]
    elif "," in text:
        parts = [p.strip() for p in text.split(",") if p.strip()]
    elif " - " in text:
        parts = [p.strip() for p in text.split(" - ") if p.strip()]
    elif " " in text:
        parts = [p.strip() for p in text.split() if p.strip()]
    else:
        match = re.split(r'(?<=\d)-(?=\d)', text)
        if len(match) == 2:
            parts = [m.strip() for m in match]
        else:
            parts = [text]

    if len(parts) != 2:
        raise ValueError("Sana oralig'i 2 ta sanadan iborat bo'lishi kerak. Masalan: 01.08.2026#01.10.2026")

    start_dt = parse_date(parts[0], is_end=False)
    end_dt = parse_date(parts[1], is_end=True)

    if start_dt > end_dt:
        raise ValueError("Boshlanish sanasi tugash sanasidan katta bo'lishi mumkin emas!")

    period_name = f"{start_dt.strftime('%d.%m.%Y')} – {end_dt.strftime('%d.%m.%Y')}"
    file_suffix = f"{start_dt.strftime('%Y%m%d')}_{end_dt.strftime('%Y%m%d')}"
    return start_dt, end_dt, period_name, file_suffix


def resolve_user_region(user: User | None) -> str:
    if not user or not user.region:
        return "Ko'rsatilmagan"
    if isinstance(user.region, Region):
        return user.region.value
    reg_str = str(user.region)
    if reg_str in regions_uz:
        return regions_uz[reg_str]
    for r in Region:
        if r.name == reg_str or r.value == reg_str:
            return r.value
    return reg_str


def resolve_disability_type(user: User | None) -> str:
    if not user or not user.disability_type:
        return "Ko'rsatilmagan"
    val = user.disability_type.value if hasattr(user.disability_type, "value") else str(user.disability_type)
    return disability_types_uz.get(val, val)


def resolve_disability_state(user: User | None) -> str:
    if not user or not user.disability_state:
        return "Ko'rsatilmagan"
    val = user.disability_state.value if hasattr(user.disability_state, "value") else str(user.disability_state)
    return disability_states_uz.get(val, val)


def resolve_gender(user: User | None) -> str:
    if not user or not user.gender:
        return "Ko'rsatilmagan"
    val = user.gender.value if hasattr(user.gender, "value") else str(user.gender)
    return gender_types_uz.get(val, val)


def format_duration_minutes(mins: float) -> str:
    if mins <= 0:
        return "—"
    if mins < 1:
        return "1 daqiqadan kam"
    if mins < 60:
        return f"{int(mins)} daqiqa"
    hours = int(mins // 60)
    rem_mins = int(mins % 60)
    if hours < 24:
        return f"{hours} soat {rem_mins} daq"
    days = int(hours // 24)
    rem_hours = int(hours % 24)
    return f"{days} kun {rem_hours} soat"


def generate_staff_kpi_report(date_range: tuple[datetime, datetime] | None = None) -> str:
    """Maintains backward compatibility with previous calls"""
    file_path, _ = generate_comprehensive_report(date_range)
    return file_path


def generate_comprehensive_report(date_range: tuple[datetime, datetime] | None = None) -> tuple[str, dict]:
    """
    Statistika:
    Sheet 1: «Umumiy loyiha statistikasi»
    Sheet 2: «Hududlar va Demografiya»
    Sheet 3: «Murojaat yo'nalishlari bo'yicha tahlil»
    Sheet 4: «Mutaxassislar KPI»
    Sheet 5: «Murojaatlar Ro'yxati»
    Sheet 6: «Yurist Qabullari»

    Returns: (file_path, summary_dict)
    """
    with Session(engine) as session:
        if date_range:
            start_date, end_date = date_range
            if hasattr(start_date, "tzinfo") and start_date.tzinfo is None:
                start_date = start_date.replace(tzinfo=timezone.utc)
            if hasattr(end_date, "tzinfo") and end_date.tzinfo is None:
                end_date = end_date.replace(tzinfo=timezone.utc)
            inquiry_stmt = select(Inquiry).where(Inquiry.created_at >= start_date, Inquiry.created_at <= end_date)
            appointment_stmt = select(Appointment).where(Appointment.created_at >= start_date, Appointment.created_at <= end_date)
        else:
            inquiry_stmt = select(Inquiry)
            appointment_stmt = select(Appointment)
        inquiries = session.exec(inquiry_stmt).all()
        appointments = session.exec(appointment_stmt).all()
        ai_stmt = select(AiAnswer)
        if date_range:
            ai_stmt = ai_stmt.where(AiAnswer.created_at >= start_date, AiAnswer.created_at <= end_date)
        ai_answers = session.exec(ai_stmt).all()

        official_lawyers = session.exec(select(OfficialLawyer)).all()
        lawyer_map = {l.user_id: l for l in official_lawyers}

        volunteers = session.exec(select(Volunteer)).all()
        vol_map = {v.user_id: v for v in volunteers}

        users = session.exec(select(User)).all()
        user_map = {u.user_id: u for u in users}

    wb = Workbook()

    # Style definitions
    header_fill = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")
    sub_header_fill = PatternFill(start_color="2F5597", end_color="2F5597", fill_type="solid")
    card_header_fill = PatternFill(start_color="D9E1F2", end_color="D9E1F2", fill_type="solid")
    total_fill = PatternFill(start_color="E8EEF8", end_color="E8EEF8", fill_type="solid")

    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    title_font = Font(name="Calibri", size=15, bold=True, color="1F4E78")
    sub_title_font = Font(name="Calibri", size=10, italic=True, color="595959")
    bold_font = Font(name="Calibri", size=11, bold=True)
    card_value_font = Font(name="Calibri", size=16, bold=True, color="1F4E78")
    card_label_font = Font(name="Calibri", size=10, bold=True, color="404040")
    regular_font = Font(name="Calibri", size=11)

    thin_border = Border(
        left=Side(style='thin', color='D9D9D9'),
        right=Side(style='thin', color='D9D9D9'),
        top=Side(style='thin', color='D9D9D9'),
        bottom=Side(style='thin', color='D9D9D9')
    )

    align_center = Alignment(horizontal="center", vertical="center")
    align_left = Alignment(horizontal="left", vertical="center")
    align_right = Alignment(horizontal="right", vertical="center")

    period_str = "Barcha davr uchun" if not date_range else f"{date_range[0].strftime('%d.%m.%Y')} — {date_range[1].strftime('%d.%m.%Y')}"
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M')

    # =========================================================================
    # DATA AGGREGATIONS & METRICS
    # =========================================================================
    total_inquiries = len(inquiries)
    answered_inquiries = [i for i in inquiries if i.status in [InquiryStatus.replied, InquiryStatus.closed]]
    total_answered = len(answered_inquiries)
    resolution_rate = (total_answered / total_inquiries * 100) if total_inquiries > 0 else 0.0

    rated_inquiries = [i for i in inquiries if i.rating is not None]
    total_rated = len(rated_inquiries)
    avg_rating = (sum(i.rating for i in rated_inquiries) / total_rated) if total_rated > 0 else 0.0
    five_star_count = sum(1 for i in rated_inquiries if i.rating == 5)
    four_star_count = sum(1 for i in rated_inquiries if i.rating == 4)
    positive_ratings = five_star_count + four_star_count
    negative_ratings = sum(1 for i in rated_inquiries if i.rating <= 2)
    satisfaction_rate = (positive_ratings / total_rated * 100) if total_rated > 0 else 0.0

    # Response times
    response_times = []
    for inq in inquiries:
        if inq.created_at and inq.replied_at:
            try:
                c_dt = inq.created_at if isinstance(inq.created_at, datetime) else datetime.fromisoformat(str(inq.created_at))
                r_dt = inq.replied_at if isinstance(inq.replied_at, datetime) else datetime.fromisoformat(str(inq.replied_at))
                diff_m = (r_dt - c_dt).total_seconds() / 60.0
                if diff_m >= 0:
                    response_times.append(diff_m)
            except Exception:
                pass
    avg_response_min = (sum(response_times) / len(response_times)) if response_times else 0.0
    avg_response_str = format_duration_minutes(avg_response_min)

    # Regional analysis
    region_stats = {}
    for r in Region:
        region_stats[r.value] = {"total": 0, "answered": 0, "ratings": []}
    region_stats["Ko'rsatilmagan"] = {"total": 0, "answered": 0, "ratings": []}

    for inq in inquiries:
        u_obj = user_map.get(inq.user_id) if inq.user_id else None
        r_name = resolve_user_region(u_obj)
        if r_name not in region_stats:
            region_stats[r_name] = {"total": 0, "answered": 0, "ratings": []}
        region_stats[r_name]["total"] += 1
        if inq.status in [InquiryStatus.replied, InquiryStatus.closed]:
            region_stats[r_name]["answered"] += 1
        if inq.rating:
            region_stats[r_name]["ratings"].append(inq.rating)

    # Disability Type analysis
    disability_type_counts = {}
    for inq in inquiries:
        u_obj = user_map.get(inq.user_id) if inq.user_id else None
        dt_label = resolve_disability_type(u_obj)
        disability_type_counts[dt_label] = disability_type_counts.get(dt_label, 0) + 1

    # Disability State analysis
    disability_state_counts = {}
    for inq in inquiries:
        u_obj = user_map.get(inq.user_id) if inq.user_id else None
        ds_label = resolve_disability_state(u_obj)
        disability_state_counts[ds_label] = disability_state_counts.get(ds_label, 0) + 1

    # Gender analysis
    gender_counts = {"Erkak": 0, "Ayol": 0, "Ko'rsatilmagan": 0}
    for inq in inquiries:
        u_obj = user_map.get(inq.user_id) if inq.user_id else None
        g_label = resolve_gender(u_obj)
        gender_counts[g_label] = gender_counts.get(g_label, 0) + 1

    # Legal sections analysis
    section_stats = {}
    for inq in inquiries:
        sec = inq.section_name or "Boshqa"
        if sec not in section_stats:
            section_stats[sec] = {
                "total": 0, "answered": 0, "ratings": [], "resp_times": []
            }
        st = section_stats[sec]
        st["total"] += 1
        if inq.status in [InquiryStatus.replied, InquiryStatus.closed]:
            st["answered"] += 1
        if inq.rating:
            st["ratings"].append(inq.rating)

        if inq.created_at and inq.replied_at:
            try:
                c_dt = inq.created_at if isinstance(inq.created_at, datetime) else datetime.fromisoformat(str(inq.created_at))
                r_dt = inq.replied_at if isinstance(inq.replied_at, datetime) else datetime.fromisoformat(str(inq.replied_at))
                diff_m = (r_dt - c_dt).total_seconds() / 60.0
                if diff_m >= 0:
                    st["resp_times"].append(diff_m)
            except Exception:
                pass

    # Appointment metrics
    total_appointments = len(appointments)
    completed_appointments = sum(1 for a in appointments if a.status == AppointmentStatus.completed)
    remote_appointments = sum(1 for a in appointments if a.appointment_type == "remote_appointment")
    in_person_appointments = sum(1 for a in appointments if a.appointment_type == "in_person_appointment")
    rated_appointments = [a for a in appointments if a.rating is not None]
    avg_app_rating = (sum(a.rating for a in rated_appointments) / len(rated_appointments)) if rated_appointments else 0.0

    # Specialists statistics
    specialist_stats = {}
    for l in official_lawyers:
        specialist_stats[l.user_id] = {
            "name": l.full_name,
            "phone": l.phone or "—",
            "role": "Rasmiy Yurist",
            "study_work": l.specialization or "Advokat / Huquqshunos",
            "inquiries_count": 0,
            "inquiries_ratings": [],
            "five_star": 0,
            "four_star": 0,
            "negative_ratings": 0,
            "response_times": [],
            "fast_responses": 0,
            "appointments_count": 0,
        }

    for v in volunteers:
        if v.user_id not in specialist_stats:
            specialist_stats[v.user_id] = {
                "name": v.full_name,
                "phone": v.phone_number or "—",
                "role": "Volontyor",
                "study_work": v.study_or_work or "—",
                "inquiries_count": 0,
                "inquiries_ratings": [],
                "five_star": 0,
                "four_star": 0,
                "negative_ratings": 0,
                "response_times": [],
                "fast_responses": 0,
                "appointments_count": 0,
            }

    for inq in inquiries:
        resp_id = inq.responder_id
        if not resp_id:
            continue
        if resp_id not in specialist_stats:
            u_obj = user_map.get(resp_id)
            name = f"{u_obj.first_name or ''} {u_obj.last_name or ''}".strip() if u_obj else f"Mutaxassis {resp_id}"
            specialist_stats[resp_id] = {
                "name": name or f"ID: {resp_id}",
                "phone": u_obj.phone if u_obj else "—",
                "role": "Volontyor",
                "study_work": "—",
                "inquiries_count": 0,
                "inquiries_ratings": [],
                "five_star": 0,
                "four_star": 0,
                "negative_ratings": 0,
                "response_times": [],
                "fast_responses": 0,
                "appointments_count": 0,
            }
        st = specialist_stats[resp_id]
        st["inquiries_count"] += 1
        if inq.rating is not None:
            st["inquiries_ratings"].append(inq.rating)
            if inq.rating == 5:
                st["five_star"] += 1
            elif inq.rating == 4:
                st["four_star"] += 1
            elif inq.rating <= 2:
                st["negative_ratings"] += 1

        if inq.created_at and inq.replied_at:
            try:
                c_dt = inq.created_at if isinstance(inq.created_at, datetime) else datetime.fromisoformat(str(inq.created_at))
                r_dt = inq.replied_at if isinstance(inq.replied_at, datetime) else datetime.fromisoformat(str(inq.replied_at))
                diff_m = (r_dt - c_dt).total_seconds() / 60.0
                if diff_m >= 0:
                    st["response_times"].append(diff_m)
                    if diff_m <= 60.0:
                        st["fast_responses"] += 1
            except Exception:
                pass

    for app in appointments:
        l_id = app.lawyer_id
        if l_id and l_id in specialist_stats and app.status == AppointmentStatus.completed:
            specialist_stats[l_id]["appointments_count"] += 1

    processed_specs = []
    for uid, data in specialist_stats.items():
        kpi = (
            (data["inquiries_count"] * 10)
            + (data["five_star"] * 15)
            + (data["four_star"] * 10)
            - (data["negative_ratings"] * 10)
            + (data["fast_responses"] * 5)
            + (data["appointments_count"] * 20)
        )
        avg_resp = (sum(data["response_times"]) / len(data["response_times"])) if data["response_times"] else 0.0
        data["uid"] = uid
        data["kpi_score"] = max(kpi, 0)
        data["avg_response_str"] = format_duration_minutes(avg_resp)
        data["avg_rating"] = round(sum(data["inquiries_ratings"]) / len(data["inquiries_ratings"]), 2) if data["inquiries_ratings"] else 0.0
        processed_specs.append(data)

    processed_specs.sort(key=lambda x: (x["kpi_score"], x["inquiries_count"]), reverse=True)

    sorted_regions = sorted(region_stats.items(), key=lambda x: x[1]["total"], reverse=True)
    sorted_sections = sorted(section_stats.items(), key=lambda x: x[1]["total"], reverse=True)
    vol_specs = [s for s in processed_specs if s["uid"] in vol_map]
    top_vol = vol_specs[0] if vol_specs else (processed_specs[0] if processed_specs else None)

    summary_dict = {
        "period_str": period_str,
        "total_inquiries": total_inquiries,
        "total_answered": total_answered,
        "resolution_rate": resolution_rate,
        "avg_rating": avg_rating,
        "total_rated": total_rated,
        "satisfaction_rate": satisfaction_rate,
        "avg_response_str": avg_response_str,
        "total_appointments": total_appointments,
        "completed_appointments": completed_appointments,
        "remote_appointments": remote_appointments,
        "in_person_appointments": in_person_appointments,
        "avg_app_rating": avg_app_rating,
        "top_regions": sorted_regions[:3],
        "top_sections": sorted_sections[:3],
        "top_specialist": top_vol,
        "ai_answers_total": len(ai_answers),
        "ai_answers_escalated": sum(1 for a in ai_answers if a.escalated_inquiry_id),
        "ai_answers_up": sum(1 for a in ai_answers if a.rating == 1),
        "ai_answers_down": sum(1 for a in ai_answers if a.rating == -1),
    }

    # =========================================================================
    # SHEET 1: LOYIHA PASPORTI VA XULOSA     (EXECUTIVE DASHBOARD)
    # =========================================================================
    ws1 = wb.active
    ws1.title = "Umumiy loyiha statistikasi"
    ws1.views.sheetView[0].showGridLines = True

    ws1.cell(row=1, column=1, value="HuquqPlus — Nogironligi Bor Shaxslar Uchun Yuridik Yordam Tizimi").font = title_font
    ws1.cell(row=2, column=1, value=f"Keng qamrovli tahliliy hisobot | Hisobot davri: {period_str} | Yaratildi: {now_str}").font = sub_title_font

    kpi_cards = [
        ("Jami Murojaatlar", f"{total_inquiries} ta", "Fuqarolar savollari"),
        ("Hal Etilgan", f"{total_answered} ta", f"Qamrov: {resolution_rate:.1f}%"),
        ("Fuqarolar Qoniqishi", f"⭐ {avg_rating:.2f} / 5.0", f"Ijobiy baholar: {satisfaction_rate:.1f}%"),
        ("O'rtacha Javob Tezligi", avg_response_str, "Savoldan birinchi javobgacha"),
        ("Yurist Qabullari", f"{completed_appointments} / {total_appointments}", f"O'tkazilgan: {completed_appointments} ta")
    ]

    for idx, (title, val, sub) in enumerate(kpi_cards, 1):
        col = idx * 2 - 1
        ws1.merge_cells(start_row=4, start_column=col, end_row=4, end_column=col + 1)
        ws1.merge_cells(start_row=5, start_column=col, end_row=5, end_column=col + 1)
        ws1.merge_cells(start_row=6, start_column=col, end_row=6, end_column=col + 1)

        c_title = ws1.cell(row=4, column=col, value=title)
        c_title.font = card_label_font
        c_title.fill = card_header_fill
        c_title.alignment = align_center

        c_val = ws1.cell(row=5, column=col, value=val)
        c_val.font = card_value_font
        c_val.fill = total_fill
        c_val.alignment = align_center

        c_sub = ws1.cell(row=6, column=col, value=sub)
        c_sub.font = sub_title_font
        c_sub.fill = total_fill
        c_sub.alignment = align_center

        for r in range(4, 7):
            for c in range(col, col + 2):
                ws1.cell(row=r, column=c).border = thin_border

    # Section 1: Detailed General Inquiries Metrics Table
    ws1.cell(row=9, column=1, value="1. Murojaatlar va Xizmat Sifati Ko'rsatkichlari").font = Font(name="Calibri", size=12, bold=True, color="1F4E78")
    t1_headers = ["Ko'rsatkich nomi", "Miqdor", "Ulush / Izoh"]
    for col_idx, h in enumerate(t1_headers, 1):
        cell = ws1.cell(row=10, column=col_idx, value=h)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = align_center

    t1_rows = [
        ("Jami kelib tushgan murojaatlar", total_inquiries, "100.0%"),
        ("Mutaxassislar tomonidan javob berilgan", total_answered, f"{resolution_rate:.1f}%"),
        ("Ayni paytda javob kutayotgan murojaatlar", total_inquiries - total_answered, f"{(100 - resolution_rate):.1f}%"),
        ("Fuqarolar tomonidan baholangan javoblar", total_rated, f"{(total_rated / total_answered * 100 if total_answered else 0):.1f}% baholash faolligi"),
        ("A'lo baholar (5 ⭐)", five_star_count, f"{(five_star_count / total_rated * 100 if total_rated else 0):.1f}%"),
        ("Yaxshi baholar (4 ⭐)", four_star_count, f"{(four_star_count / total_rated * 100 if total_rated else 0):.1f}%"),
        ("Qoniqarsiz baholar (1-2 ⭐)", negative_ratings, f"{(negative_ratings / total_rated * 100 if total_rated else 0):.1f}%"),
        ("O'rtacha javob berish vaqti", avg_response_str, "Soat va daqiqalarda")
    ]

    for r_i, (k, v, note) in enumerate(t1_rows, 11):
        c1 = ws1.cell(row=r_i, column=1, value=k)
        c2 = ws1.cell(row=r_i, column=2, value=v)
        c3 = ws1.cell(row=r_i, column=3, value=note)
        c1.font = regular_font
        c2.font = bold_font
        c3.font = regular_font
        c1.border = thin_border
        c2.border = thin_border
        c3.border = thin_border
        c1.alignment = align_left
        c2.alignment = align_right
        c3.alignment = align_center

    # Section 2: Appointments Summary Table
    ws1.cell(row=9, column=5, value="2. Yurist Qabullari Xulosasi").font = Font(name="Calibri", size=12, bold=True, color="1F4E78")
    t2_headers = ["Qabul parametri", "Qiymat", "Izoh"]
    for col_idx, h in enumerate(t2_headers, 5):
        cell = ws1.cell(row=10, column=col_idx, value=h)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = align_center

    app_summary_rows = [
        ("Jami kelib tushgan qabul arizalari", total_appointments, "100.0%"),
        ("Muvaffaqiyatli o'tkazilgan suhbatlar", completed_appointments, f"{(completed_appointments / total_appointments * 100 if total_appointments else 0):.1f}%"),
        ("Masofaviy (Online) suhbatlar", remote_appointments, f"{(remote_appointments / total_appointments * 100 if total_appointments else 0):.1f}%"),
        ("Yuzma-yuz (Bosh ofisda) qabullar", in_person_appointments, f"{(in_person_appointments / total_appointments * 100 if total_appointments else 0):.1f}%"),
        ("Fuqarolar tomonidan baholangan qabullar", len(rated_appointments), f"{len(rated_appointments)} ta baho"),
        ("Suhbatlarning o'rtacha fuqaro bahosi", f"⭐ {avg_app_rating:.2f} / 5.0" if avg_app_rating else "—", "5 ballik shkalada")
    ]

    for r_i, (k, v, note) in enumerate(app_summary_rows, 11):
        c1 = ws1.cell(row=r_i, column=5, value=k)
        c2 = ws1.cell(row=r_i, column=6, value=v)
        c3 = ws1.cell(row=r_i, column=7, value=note)
        c1.font = regular_font
        c2.font = bold_font
        c3.font = regular_font
        c1.border = thin_border
        c2.border = thin_border
        c3.border = thin_border
        c1.alignment = align_left
        c2.alignment = align_right
        c3.alignment = align_center

    for col in ws1.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        col_letter = col[0].column_letter
        ws1.column_dimensions[col_letter].width = min(max(max_len + 3, 14), 40)

    # =========================================================================
    # SHEET 2: HUDUDLAR VA DEMOGRAFIYA (REGIONS & DEMOGRAPHICS)
    # =========================================================================
    ws2 = wb.create_sheet(title="Hududlar va Demografiya")
    ws2.views.sheetView[0].showGridLines = True

    ws2.cell(row=1, column=1, value="HuquqPlus — Hududlar Kesimida Murojaatlar va Nogironlik Demografiyasi").font = title_font
    ws2.cell(row=2, column=1, value=f"Davr: {period_str} | Yaratildi: {now_str}").font = sub_title_font

    ws2.cell(row=4, column=1, value="📍 Viloyatlar va Hududlar Kesimi (14 ta hudud)").font = Font(name="Calibri", size=12, bold=True, color="1F4E78")
    reg_headers = ["№", "Viloyat / Hudud nomi", "Jami murojaatlar", "Ulush (%)", "Javob berilgan", "Hal etilish (%)", "O'rtacha baho (⭐)"]
    for col_idx, h in enumerate(reg_headers, 1):
        cell = ws2.cell(row=5, column=col_idx, value=h)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = align_center

    cur_r_row = 6
    for idx, (reg_name, r_data) in enumerate(sorted_regions, 1):
        tot = r_data["total"]
        ans = r_data["answered"]
        pct = (tot / total_inquiries * 100) if total_inquiries > 0 else 0.0
        res_pct = (ans / tot * 100) if tot > 0 else 0.0
        r_avg = round(sum(r_data["ratings"]) / len(r_data["ratings"]), 2) if r_data["ratings"] else "—"

        row_vals = [idx, reg_name, tot, f"{pct:.1f}%", ans, f"{res_pct:.1f}%", r_avg]
        for col_idx, val in enumerate(row_vals, 1):
            c = ws2.cell(row=cur_r_row, column=col_idx, value=val)
            c.font = regular_font
            c.border = thin_border
            c.alignment = align_center if col_idx in [1, 4, 6, 7] else (align_right if col_idx in [3, 5] else align_left)
        cur_r_row += 1

    tot_row = cur_r_row
    ws2.cell(row=tot_row, column=1, value="").border = thin_border
    ws2.cell(row=tot_row, column=2, value="JAMI:").font = bold_font
    ws2.cell(row=tot_row, column=3, value=total_inquiries).font = bold_font
    ws2.cell(row=tot_row, column=4, value="100.0%").font = bold_font
    ws2.cell(row=tot_row, column=5, value=total_answered).font = bold_font
    ws2.cell(row=tot_row, column=6, value=f"{resolution_rate:.1f}%").font = bold_font
    ws2.cell(row=tot_row, column=7, value=round(avg_rating, 2) if avg_rating else "—").font = bold_font
    for c_i in range(1, 8):
        c = ws2.cell(row=tot_row, column=c_i)
        c.fill = total_fill
        c.border = thin_border
        if c_i in [3, 5]:
            c.alignment = align_right
        elif c_i in [4, 6, 7]:
            c.alignment = align_center
        else:
            c.alignment = align_left

    # Table 2: Disability Groups (Columns 9-11)
    ws2.cell(row=4, column=9, value="♿️ Nogironlik Guruhlari Kesimi").font = Font(name="Calibri", size=12, bold=True, color="1F4E78")
    dt_headers = ["Nogironlik guruhi", "Murojaatlar", "Ulush (%)"]
    for col_idx, h in enumerate(dt_headers, 9):
        cell = ws2.cell(row=5, column=col_idx, value=h)
        cell.font = header_font
        cell.fill = sub_header_fill
        cell.alignment = align_center

    cur_dt_row = 6
    sorted_dt = sorted(disability_type_counts.items(), key=lambda x: x[1], reverse=True)
    for dt_lbl, cnt in sorted_dt:
        pct = (cnt / total_inquiries * 100) if total_inquiries > 0 else 0.0
        c1 = ws2.cell(row=cur_dt_row, column=9, value=dt_lbl)
        c2 = ws2.cell(row=cur_dt_row, column=10, value=cnt)
        c3 = ws2.cell(row=cur_dt_row, column=11, value=f"{pct:.1f}%")
        for c in [c1, c2, c3]:
            c.font = regular_font
            c.border = thin_border
        c1.alignment = align_left
        c2.alignment = align_right
        c3.alignment = align_center
        cur_dt_row += 1

    # Table 3: Disability States / Forms (Columns 9-11 continued)
    cur_dt_row += 2
    ws2.cell(row=cur_dt_row, column=9, value="🦽 Nogironlik Shakli / Holati Kesimi").font = Font(name="Calibri", size=12, bold=True, color="1F4E78")
    cur_dt_row += 1
    for col_idx, h in enumerate(["Nogironlik shakli", "Murojaatlar", "Ulush (%)"], 9):
        cell = ws2.cell(row=cur_dt_row, column=col_idx, value=h)
        cell.font = header_font
        cell.fill = sub_header_fill
        cell.alignment = align_center
    cur_dt_row += 1

    sorted_ds = sorted(disability_state_counts.items(), key=lambda x: x[1], reverse=True)
    for ds_lbl, cnt in sorted_ds:
        pct = (cnt / total_inquiries * 100) if total_inquiries > 0 else 0.0
        c1 = ws2.cell(row=cur_dt_row, column=9, value=ds_lbl)
        c2 = ws2.cell(row=cur_dt_row, column=10, value=cnt)
        c3 = ws2.cell(row=cur_dt_row, column=11, value=f"{pct:.1f}%")
        for c in [c1, c2, c3]:
            c.font = regular_font
            c.border = thin_border
        c1.alignment = align_left
        c2.alignment = align_right
        c3.alignment = align_center
        cur_dt_row += 1

    # Table 4: Gender breakdown
    cur_dt_row += 2
    ws2.cell(row=cur_dt_row, column=9, value="👥 Gender (Jinsi) Kesimi").font = Font(name="Calibri", size=12, bold=True, color="1F4E78")
    cur_dt_row += 1
    for col_idx, h in enumerate(["Jinsi", "Murojaatlar", "Ulush (%)"], 9):
        cell = ws2.cell(row=cur_dt_row, column=col_idx, value=h)
        cell.font = header_font
        cell.fill = sub_header_fill
        cell.alignment = align_center
    cur_dt_row += 1

    for g_lbl, cnt in gender_counts.items():
        pct = (cnt / total_inquiries * 100) if total_inquiries > 0 else 0.0
        c1 = ws2.cell(row=cur_dt_row, column=9, value=g_lbl)
        c2 = ws2.cell(row=cur_dt_row, column=10, value=cnt)
        c3 = ws2.cell(row=cur_dt_row, column=11, value=f"{pct:.1f}%")
        for c in [c1, c2, c3]:
            c.font = regular_font
            c.border = thin_border
        c1.alignment = align_left
        c2.alignment = align_right
        c3.alignment = align_center
        cur_dt_row += 1

    for col in ws2.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        col_letter = col[0].column_letter
        ws2.column_dimensions[col_letter].width = min(max(max_len + 3, 14), 45)

    # =========================================================================
    # SHEET 3: HUQUQIY SOHALAR TAHLILI (LEGAL TOPICS BREAKDOWN)
    # =========================================================================
    ws3 = wb.create_sheet(title="Huquqiy Sohalar Tahlili")
    ws3.views.sheetView[0].showGridLines = True

    ws3.cell(row=1, column=1, value="HuquqPlus — Huquqiy Mavzular va Yo'nalishlar Bo'yicha Tahlil").font = title_font
    ws3.cell(row=2, column=1, value=f"Davr: {period_str} | Yaratildi: {now_str}").font = sub_title_font

    sec_headers = [
        "№", "Huquqiy soha / Yo'nalish", "Jami murojaat", "Ulush (%)", "Javob berilgan",
        "Yechilish (%)", "O'rtacha baho (⭐)", "O'rtacha javob vaqti"
    ]
    for col_idx, h in enumerate(sec_headers, 1):
        cell = ws3.cell(row=4, column=col_idx, value=h)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = align_center

    cur_sec_row = 5
    for idx, (sec_name, s_data) in enumerate(sorted_sections, 1):
        tot = s_data["total"]
        ans = s_data["answered"]
        pct = (tot / total_inquiries * 100) if total_inquiries > 0 else 0.0
        res_pct = (ans / tot * 100) if tot > 0 else 0.0
        s_avg = round(sum(s_data["ratings"]) / len(s_data["ratings"]), 2) if s_data["ratings"] else "—"
        s_resp_avg = (sum(s_data["resp_times"]) / len(s_data["resp_times"])) if s_data["resp_times"] else 0.0

        row_vals = [
            idx,
            sec_name,
            tot,
            f"{pct:.1f}%",
            ans,
            f"{res_pct:.1f}%",
            s_avg,
            format_duration_minutes(s_resp_avg)
        ]
        for col_idx, val in enumerate(row_vals, 1):
            c = ws3.cell(row=cur_sec_row, column=col_idx, value=val)
            c.font = regular_font
            c.border = thin_border
            c.alignment = align_center if col_idx in [1, 4, 6, 7, 8] else (align_right if col_idx in [3, 5] else align_left)
        cur_sec_row += 1

    # Total row for sections
    ws3.cell(row=cur_sec_row, column=1, value="").border = thin_border
    ws3.cell(row=cur_sec_row, column=2, value="JAMI:").font = bold_font
    ws3.cell(row=cur_sec_row, column=3, value=total_inquiries).font = bold_font
    ws3.cell(row=cur_sec_row, column=4, value="100.0%").font = bold_font
    ws3.cell(row=cur_sec_row, column=5, value=total_answered).font = bold_font
    ws3.cell(row=cur_sec_row, column=6, value=f"{resolution_rate:.1f}%").font = bold_font
    ws3.cell(row=cur_sec_row, column=7, value=round(avg_rating, 2) if avg_rating else "—").font = bold_font
    ws3.cell(row=cur_sec_row, column=8, value=avg_response_str).font = bold_font

    for c_i in range(1, 9):
        c = ws3.cell(row=cur_sec_row, column=c_i)
        c.fill = total_fill
        c.border = thin_border
        if c_i in [3, 5]:
            c.alignment = align_right
        elif c_i in [4, 6, 7, 8]:
            c.alignment = align_center
        else:
            c.alignment = align_left

    for col in ws3.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        col_letter = col[0].column_letter
        ws3.column_dimensions[col_letter].width = min(max(max_len + 3, 14), 45)

    # =========================================================================
    # SHEET 4: MUTAXASSISLAR VA VOLONTYORLAR KPI (SPECIALISTS RANKING)
    # =========================================================================
    ws4 = wb.create_sheet(title="Mutaxassislar KPI")
    ws4.views.sheetView[0].showGridLines = True

    ws4.cell(row=1, column=1, value="HuquqPlus — Mutaxassislar (Yurist va Volontyorlar) KPI Tahlili").font = title_font
    ws4.cell(row=2, column=1, value=f"Davr: {period_str} | Yaratildi: {now_str}").font = sub_title_font

    headers4 = [
        "O'rin", "Mutaxassis F.I.Sh.", "Telegram ID", "Telefon", "Maqomi / Roli", "O'qish / Ish joyi",
        "Jami KPI Ball", "Javoblar soni", "O'rtacha baho (⭐)", "O'rtacha javob tezligi",
        "5⭐ baholar", "4⭐ baholar", "1-2⭐ baholar", "Qabullar soni"
    ]
    for col_idx, h in enumerate(headers4, 1):
        cell = ws4.cell(row=4, column=col_idx, value=h)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = align_center

    cur_spec_row = 5
    for idx, data in enumerate(processed_specs, 1):
        inq_avg = data["avg_rating"] if data["avg_rating"] > 0 else "—"
        row_vals = [
            idx,
            data["name"],
            data["uid"],
            data["phone"],
            data["role"],
            data["study_work"],
            data["kpi_score"],
            data["inquiries_count"],
            inq_avg,
            data["avg_response_str"],
            data["five_star"],
            data["four_star"],
            data["negative_ratings"],
            data["appointments_count"]
        ]
        for col_idx, val in enumerate(row_vals, 1):
            c = ws4.cell(row=cur_spec_row, column=col_idx, value=val)
            c.font = regular_font
            c.border = thin_border
            c.alignment = align_center if col_idx in [1, 3, 4, 5, 9, 10] else (align_right if col_idx in [7, 8, 11, 12, 13, 14] else align_left)
        cur_spec_row += 1

    for col in ws4.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        col_letter = col[0].column_letter
        ws4.column_dimensions[col_letter].width = min(max(max_len + 3, 13), 40)

    # =========================================================================
    # SHEET 5: BARCHA MUROJAATLAR REGISTRI (DETAILED INQUIRIES)
    # =========================================================================
    ws5 = wb.create_sheet(title="Murojaatlar Registri")
    ws5.views.sheetView[0].showGridLines = True

    headers5 = [
        "№", "ID", "Sana-vaqt", "Huquqiy soha", "Fuqaro F.I.Sh.", "Telefon", "Viloyat",
        "Nogironlik guruhi", "Savol matni", "Javob bergan mutaxassis", "Roli",
        "Javob matni", "Javob vaqti", "Fuqaro bahosi", "Fuqaro fikri (Izoh)"
    ]
    for col_idx, h in enumerate(headers5, 1):
        cell = ws5.cell(row=1, column=col_idx, value=h)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = align_center

    for r_idx, inq in enumerate(inquiries, 2):
        u_obj = user_map.get(inq.user_id) if inq.user_id else None
        citizen_name = f"{u_obj.first_name or ''} {u_obj.last_name or ''}".strip() if u_obj else f"User {inq.user_id}"
        citizen_phone = u_obj.phone if u_obj else "—"
        citizen_reg = resolve_user_region(u_obj)
        citizen_dt = resolve_disability_type(u_obj)

        resp_stat = specialist_stats.get(inq.responder_id)
        resp_name = resp_stat["name"] if resp_stat else (f"ID: {inq.responder_id}" if inq.responder_id else "Javob berilmagan")
        resp_role = resp_stat["role"] if resp_stat else "—"

        created_str = inq.created_at.strftime('%Y-%m-%d %H:%M') if inq.created_at else "—"
        replied_str = str(inq.replied_at)[:16] if inq.replied_at else "—"
        rating_str = f"⭐ {inq.rating}" if inq.rating else "Baholanmagan"

        row5 = [
            r_idx - 1,
            inq.id,
            created_str,
            inq.section_name or "Boshqa",
            citizen_name,
            citizen_phone or "—",
            citizen_reg,
            citizen_dt,
            (inq.question[:400] if inq.question else "—"),
            resp_name,
            resp_role,
            (inq.answer[:400] if inq.answer else "—"),
            replied_str,
            rating_str,
            inq.feedback or "—"
        ]

        for col_idx, val in enumerate(row5, 1):
            c = ws5.cell(row=r_idx, column=col_idx, value=val)
            c.font = regular_font
            c.border = thin_border
            c.alignment = align_center if col_idx in [1, 2, 3, 6, 8, 11, 13, 14] else align_left

    for col in ws5.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        col_letter = col[0].column_letter
        ws5.column_dimensions[col_letter].width = min(max(max_len + 3, 12), 45)

    # =========================================================================
    # SHEET 6: YURIST QABULLARI REGISTRI (APPOINTMENTS REGISTRY)
    # =========================================================================
    ws6 = wb.create_sheet(title="Yurist Qabullari")
    ws6.views.sheetView[0].showGridLines = True

    headers6 = [
        "№", "Ariza ID", "Ariza sanasi", "Fuqaro F.I.Sh.", "Telefon", "Viloyat",
        "Qabul shakli", "Muammo tavsifi", "Mas'ul yurist", "Holati",
        "Suhbat yakunlangan vaqt", "Fuqaro bahosi", "Fuqaro fikri (Izoh)"
    ]
    for col_idx, h in enumerate(headers6, 1):
        cell = ws6.cell(row=1, column=col_idx, value=h)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = align_center

    for r_idx, app in enumerate(appointments, 2):
        u_obj = user_map.get(app.user_id) if app.user_id else None
        citizen_name = f"{u_obj.first_name or ''} {u_obj.last_name or ''}".strip() if u_obj else f"User {app.user_id}"
        citizen_phone = u_obj.phone if u_obj else "—"
        citizen_reg = resolve_user_region(u_obj)

        lawyer_obj = lawyer_map.get(app.lawyer_id)
        lawyer_name = lawyer_obj.full_name if lawyer_obj else (f"ID: {app.lawyer_id}" if app.lawyer_id else "Biriktirilmagan")

        status_uz = {
            "pending": "Kutilmoqda",
            "accepted": "Qabul qilingan",
            "completed": "Yakunlangan",
            "cancelled": "Bekor qilingan"
        }.get(app.status, str(app.status))

        type_uz = "Masofaviy (Online)" if app.appointment_type == "remote_appointment" else "Yuzma-yuz (Bosh ofis)"
        created_str = app.created_at.strftime('%Y-%m-%d %H:%M') if app.created_at else "—"
        completed_str = app.completed_at.strftime('%Y-%m-%d %H:%M') if app.completed_at else "—"
        rating_str = f"⭐ {app.rating}" if app.rating else "Baholanmagan"

        row6 = [
            r_idx - 1,
            app.id,
            created_str,
            citizen_name,
            citizen_phone or "—",
            citizen_reg,
            type_uz,
            (app.problem_description[:400] if app.problem_description else "—"),
            lawyer_name,
            status_uz,
            completed_str,
            rating_str,
            app.feedback or "—"
        ]

        for col_idx, val in enumerate(row6, 1):
            c = ws6.cell(row=r_idx, column=col_idx, value=val)
            c.font = regular_font
            c.border = thin_border
            c.alignment = align_center if col_idx in [1, 2, 3, 5, 7, 10, 11, 12] else align_left

    for col in ws6.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        col_letter = col[0].column_letter
        ws6.column_dimensions[col_letter].width = min(max(max_len + 3, 12), 45)

    # Save to file
    today_str = datetime.now().strftime('%Y%m%d_%H%M')
    target_dir = "/app/user_data/reports" if os.path.exists("/app") and os.access("/app", os.W_OK) else "data/user_data/reports"
    os.makedirs(target_dir, exist_ok=True)
    file_path = f"{target_dir}/HuquqPlus_Hisobot_{today_str}.xlsx"
    wb.save(file_path)

    return file_path, summary_dict


def format_telegram_analytics_summary(summary_dict: dict, period_name: str) -> str:
    """Formats a concise, beautiful executive HTML message for Telegram chat"""
    tot_inq = summary_dict["total_inquiries"]
    tot_ans = summary_dict["total_answered"]
    res_rate = summary_dict["resolution_rate"]
    avg_r = summary_dict["avg_rating"]
    tot_r = summary_dict["total_rated"]
    csat = summary_dict["satisfaction_rate"]
    avg_resp = summary_dict["avg_response_str"]

    tot_app = summary_dict["total_appointments"]
    comp_app = summary_dict["completed_appointments"]
    rem_app = summary_dict["remote_appointments"]
    inp_app = summary_dict["in_person_appointments"]
    app_r = summary_dict["avg_app_rating"]

    top_reg_lines = []
    for idx, (r_name, r_d) in enumerate([x for x in summary_dict.get("top_regions", []) if x[1]["total"] > 0], 1):
        pct = (r_d["total"] / tot_inq * 100) if tot_inq > 0 else 0.0
        top_reg_lines.append(f"{idx}. <b>{r_name}</b>: {r_d['total']} ta ({pct:.1f}%)")
    top_reg_str = "<br/>".join(top_reg_lines) if top_reg_lines else "<i>Ma'lumot yo'q</i>"

    top_sec_lines = []
    for idx, (s_name, s_d) in enumerate([x for x in summary_dict.get("top_sections", []) if x[1]["total"] > 0], 1):
        pct = (s_d["total"] / tot_inq * 100) if tot_inq > 0 else 0.0
        top_sec_lines.append(f"{idx}. <b>{s_name}</b>: {s_d['total']} ta ({pct:.1f}%)")
    top_sec_str = "<br/>".join(top_sec_lines) if top_sec_lines else "<i>Ma'lumot yo'q</i>"

    top_spec = summary_dict.get("top_specialist")
    if top_spec and (top_spec.get("inquiries_count") or top_spec.get("kpi_score")):
        spec_r = f"⭐ {top_spec['avg_rating']}" if top_spec['avg_rating'] > 0 else "baho yo'q"
        top_spec_str = f"🥇 <b>{top_spec['name']}</b> ({top_spec['role']})<br/>   🎯 KPI: <b>{top_spec['kpi_score']}</b> ball | {top_spec['inquiries_count']} ta javob ({spec_r})"
    else:
        top_spec_str = "<i>Hozircha natijalar mavjud emas</i>"

    app_avg_str = f"⭐ {app_r:.2f} / 5.0" if app_r > 0 else "baholanmagan"
    ai_total = summary_dict.get("ai_answers_total", 0)
    ai_line = (
        f"\n• Avtomatik javob berilgan savollar: <b>{ai_total}</b> ta "
        f"(huquqshunosga o'tgan: <b>{summary_dict.get('ai_answers_escalated', 0)}</b> ta, "
        f"baho: 👍 {summary_dict.get('ai_answers_up', 0)} / 👎 {summary_dict.get('ai_answers_down', 0)})"
        if ai_total else ""
    )

    text = f"""📊 <b>HuquqPlus — Keng Qamrovli Tahliliy Hisobot</b>
━━━━━━━━━━━━━━━━━━━━━
🗓 <b>Hisobot davri:</b> <b>{period_name}</b>

📈 <b>ASOSIY KO'RSATKICHLAR:</b>
• Jami murojaatlar: <b>{tot_inq}</b> ta
• Hal etilgan (javob berilgan): <b>{tot_ans}</b> ta (<b>{res_rate:.1f}%</b>)
• Fuqarolar qoniqishi: <b>⭐ {avg_r:.2f} / 5.0</b> ({tot_r} ta baho, ijobiy: <b>{csat:.1f}%</b>)
• O'rtacha javob tezligi: <b>⚡️ {avg_resp}</b>{ai_line}

🏢 <b>YURIST QABULLARI:</b>
• Jami arizalar: <b>{tot_app}</b> ta | O'tkazilgan: <b>{comp_app}</b> ta
• Masofaviy (Online): <b>{rem_app}</b> ta | Bosh ofisda: <b>{inp_app}</b> ta
• Suhbatlarning o'rtacha bahosi: <b>{app_avg_str}</b>

📍 <b>ENG KO'P MUROJAAT TUSHGAN HUDUDLAR (Top 3):</b>
{top_reg_str}

⚖️ <b>ENG KO'P SO'RALGAN SOHALAR (Top 3):</b>
{top_sec_str}

🏆 <b>ENG YUQORI NATIJA KO'RSATGAN MUTAXASSIS:</b>
{top_spec_str}
━━━━━━━━━━━━━━━━━━━━━
<i>Barcha 6 ta tahliliy varaqli batafsil Excel jadval biriktirildi.</i>"""
    # xabar SULGUK (HTML) rejimida yuboriladi: oddiy "\n" u yerda qator tashlamaydi
    return text.replace("\n", "<br/>")


async def send_report_document(bot, chat_id: int | str, file_path: str, filename: str, summary_html: str, period_name: str) -> None:
    """Hisobot xulosasi + Excel fayl. Xulosa caption chegarasidan (1024) uzun bo'lsa alohida xabar bo'ladi."""
    from aiogram.types import FSInputFile
    from sulguk import SULGUK_PARSE_MODE
    try:
        from sulguk import transform_html
        summary_len = len(transform_html(summary_html).text)
    except Exception:
        summary_len = len(summary_html)
    document = FSInputFile(path=file_path, filename=filename)
    if summary_len <= 1024:
        await bot.send_document(chat_id=chat_id, document=document, caption=summary_html, parse_mode=SULGUK_PARSE_MODE)
        return
    await bot.send_message(chat_id=chat_id, text=summary_html, parse_mode=SULGUK_PARSE_MODE)
    await bot.send_document(
        chat_id=chat_id, document=document,
        caption=f"📊 <b>HuquqPlus Tahliliy Hisoboti:</b> {period_name}", parse_mode=SULGUK_PARSE_MODE,
    )
