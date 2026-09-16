from datetime import datetime, date, time, timedelta
from sqlmodel import Session, select
from src.app.timeutils import tz
from src.models.appointment import Appointment, AppointmentStatus
from src.models.lawyer import OfficialLawyer

UZ_MONTHS = {
    1: "Yanvar", 2: "Fevral", 3: "Mart", 4: "Aprel",
    5: "May", 6: "Iyun", 7: "Iyul", 8: "Avgust",
    9: "Sentabr", 10: "Oktabr", 11: "Noyabr", 12: "Dekabr"
}

UZ_WEEKDAYS = {
    0: "Dushanba", 1: "Seshanba", 2: "Chorshanba",
    3: "Payshanba", 4: "Juma", 5: "Shanba", 6: "Yakshanba"
}

DEFAULT_WORKING_HOURS = ["09:00", "10:00", "11:00", "14:00", "15:00", "16:00", "17:00"]
IN_PERSON_HOURS = ["10:00", "11:00", "12:00", "14:00", "15:00", "16:00"]


def format_uz_date(dt: datetime) -> str:
    month_name = UZ_MONTHS.get(dt.month, "")
    weekday_name = UZ_WEEKDAYS.get(dt.weekday(), "")
    return f"{dt.day}-{month_name} ({weekday_name}), {dt.strftime('%H:%M')}"


def get_available_dates(appointment_type: str = "remote_appointment", count: int = 8) -> list[dict]:
    """Returns a list of available upcoming dates for appointment booking"""
    now = datetime.now(tz)
    dates = []
    
    # If late in the day (after 16:00), start from tomorrow
    start_offset = 1 if now.hour >= 16 else 0
    curr = now.date() + timedelta(days=start_offset)
    
    attempts = 0
    while len(dates) < count and attempts < 30:
        attempts += 1
        w = curr.weekday()
        if appointment_type == "in_person_appointment":
            # Only Saturdays (weekday 5)
            if w == 5:
                month_name = UZ_MONTHS.get(curr.month, "")
                dates.append({
                    "date_str": curr.strftime("%Y-%m-%d"),
                    "label": f"📅 {curr.day}-{month_name} (Shanba)",
                    "date": curr
                })
        else:
            # Remote appointments: Weekdays (Monday-Friday: 0..4)
            if w in [0, 1, 2, 3, 4]:
                month_name = UZ_MONTHS.get(curr.month, "")
                w_name = UZ_WEEKDAYS.get(w, "")
                label_prefix = "Bugun" if curr == now.date() else ("Ertaga" if curr == now.date() + timedelta(days=1) else w_name)
                dates.append({
                    "date_str": curr.strftime("%Y-%m-%d"),
                    "label": f"📅 {curr.day}-{month_name} ({label_prefix})",
                    "date": curr
                })
        curr += timedelta(days=1)
        
    return dates


def get_time_slots_for_date(
    date_str: str,
    lawyer_id: int | None,
    appointment_type: str,
    db_session: Session
) -> list[dict]:
    """Generates available time slots for a given date and lawyer"""
    now = datetime.now(tz)
    target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    
    hours = IN_PERSON_HOURS if appointment_type == "in_person_appointment" else DEFAULT_WORKING_HOURS
    
    # Active lawyers count
    active_lawyers = db_session.exec(select(OfficialLawyer).where(OfficialLawyer.is_active == True)).all()
    total_lawyers = max(len(active_lawyers), 1)

    # Fetch booked appointments for this date
    start_of_day = datetime.combine(target_date, time.min)
    end_of_day = datetime.combine(target_date, time.max)
    
    booked_appointments = db_session.exec(
        select(Appointment).where(
            Appointment.scheduled_at >= start_of_day,
            Appointment.scheduled_at <= end_of_day,
            Appointment.status.in_([AppointmentStatus.pending, AppointmentStatus.accepted])
        )
    ).all()

    slots = []
    for h_str in hours:
        h_int = int(h_str.split(":")[0])
        slot_dt = datetime.combine(target_date, time(h_int, 0)).replace(tzinfo=tz)
        
        # Check if time has already passed today
        if target_date == now.date() and slot_dt <= now + timedelta(minutes=30):
            continue

        # Check if slot is occupied
        is_available = True
        if lawyer_id:
            # Specific lawyer requested
            for app in booked_appointments:
                if app.lawyer_id == lawyer_id and app.scheduled_at and app.scheduled_at.hour == h_int:
                    is_available = False
                    break
        else:
            # Any lawyer: count how many bookings exist in this slot
            booked_count = sum(1 for app in booked_appointments if app.scheduled_at and app.scheduled_at.hour == h_int)
            if booked_count >= total_lawyers:
                is_available = False

        next_h = f"{h_int + 1:02d}:00"
        slots.append({
            "time_str": h_str,
            "label": f"{h_str} - {next_h}",
            "is_available": is_available
        })

    return slots
