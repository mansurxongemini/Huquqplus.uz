"""Asosiy oqimlarni haqiqiy baza va Redis bilan tekshirish (Telegram'ga hech narsa yuborilmaydi).

Ishlatish (konteyner ichida, admin+volontyor bo'lgan foydalanuvchi ID si bilan):
    python scripts/flow_check.py 8904838656

Har bir oqimda bot javob berganini va kerakli tugma/xabar borligini tekshiradi; yaratilgan sinov
yozuvlarini (murojaat, ariza) oxirida o'chiradi. Hammasi o'tsa — chiqish kodi 0.
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))

import src.models.db_models  # noqa: E402,F401
from sqlmodel import Session, select  # noqa: E402

from simulate_update import feed, make_bot  # noqa: E402
from src.app.keyboards import inquiry_sections_uz  # noqa: E402
from src.app.translations import t  # noqa: E402
from src.config.settings import settings  # noqa: E402
from src.database.mysql import engine  # noqa: E402
from src.models.appointment import Appointment  # noqa: E402
from src.models.inquiry import Inquiry  # noqa: E402

FAKE_ID_FROM = 100000  # RecordingSession qaytaradigan xabar ID lari shundan boshlanadi


def _texts(calls) -> list[str]:
    return [str(getattr(c, "text", None) or getattr(c, "caption", None) or "") for c in calls]


def _callbacks(calls) -> list[str]:
    out = []
    for c in calls:
        markup = getattr(c, "reply_markup", None)
        for row in getattr(markup, "inline_keyboard", None) or []:
            out.extend(b.callback_data for b in row if getattr(b, "callback_data", None))
    return out


async def run(user_id: int) -> int:
    bot = make_bot(verbose=False)
    results: list[tuple[str, bool, str]] = []

    async def check(name: str, steps: list[str], predicate) -> None:
        calls = []
        try:
            for step in steps:
                calls = await feed(bot, user_id, step)
            ok, detail = predicate(calls)
        except Exception as e:  # noqa: BLE001
            ok, detail = False, f"{type(e).__name__}: {e}"
        results.append((name, ok, detail))

    sent = lambda calls: (bool(_texts(calls)) and any(_texts(calls)), f"{len(calls)} so'rov")  # noqa: E731

    # Volontyor paneli
    await check("Volontyor: Biriktirilgan murojaatlar", [t("menu_vol_assigns", "uz")], sent)
    await check("Volontyor: Mening natijam", [t("menu_vol_result", "uz")], sent)
    await check("Volontyor: Sohalarim", [t("menu_vol_sections", "uz")], sent)
    await check("Volontyor: Javobni tasdiqlatish", [t("menu_vol_review", "uz")], sent)
    await check("Volontyor: fuqaro menyusiga o'tish", [t("menu_vol_citizen", "uz")], sent)

    # Admin panel
    for cb in ("admin:main", "admin:asg_panel", "admin:ai_sections", "admin:admins_list"):
        await check(f"Admin: {cb}", [f"cb:{cb}"], sent)

    # Menyu tugmasi FSM holatini buzmasligi: savol kutilayotganda menyu bosilsa, savol bo'lib ketmaydi
    section = next(iter(inquiry_sections_uz))
    await check(
        "Holat: savol o'rniga menyu tugmasi",
        [t("menu_inquiry", "uz"), section, t("menu_about_us", "uz")],
        lambda calls: (not any("blockquote" in x for x in _texts(calls)), "guruhga yuborilmadi"),
    )

    # Murojaat: guruhga karta + Biriktirish tugmasi (avtomatik javob o'chiq bo'lsa yoki ishonchsiz bo'lsa)
    def inquiry_ok(calls):
        cbs = _callbacks(calls)
        has_card = any("blockquote" in x for x in _texts(calls))
        return (has_card and any(c.startswith("inq_assign:") for c in cbs)) or any(c.startswith("aiesc:") for c in cbs), \
            "karta+Biriktirish yoki avtomatik javob"
    await check("Murojaat yuborish", [t("menu_inquiry", "uz"), section, "Sinov savoli: ish haqi kechikmoqda, nima qilish kerak?"],
                inquiry_ok)

    # Qabulga yozilish: oxirida guruhga yagona qabul kartasi
    await check(
        "Qabulga yozilish",
        [t("menu_appointment", "uz"), "cb:remote_appointment", "Sinov: qabulga yozilmoqchiman", t("btn_send", "uz"), "cb:app_confirm:yes"],
        lambda calls: (any("YURIST QABULIGA ARIZA" in x for x in _texts(calls))
                       or any("faol ariza" in x for x in _texts(calls)), "qabul kartasi yoki faol ariza ogohlantirishi"),
    )

    # Tozalash
    with Session(engine) as session:
        for inq in session.exec(select(Inquiry).where(Inquiry.user_id == user_id, Inquiry.group_question_id >= FAKE_ID_FROM)).all():
            session.delete(inq)
        for app in session.exec(select(Appointment).where(Appointment.user_id == user_id, Appointment.group_message_id >= FAKE_ID_FROM)).all():
            session.delete(app)
        session.commit()
    await feed(bot, user_id, t("btn_back_main", "uz"))

    failed = 0
    for name, ok, detail in results:
        failed += not ok
        print(f"{'✅' if ok else '❌'} {name} — {detail}")
    print(f"\n{len(results) - failed}/{len(results)} oqim o'tdi (AI_CITIZEN_ANSWERS={settings.AI_CITIZEN_ANSWERS})")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run(int(sys.argv[1]))))
