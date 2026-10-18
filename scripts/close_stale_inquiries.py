"""Javob berib bo'lmaydigan eski ochiq murojaatlarni yopish (masalan, guruh superguruhga ko'chishidan oldingilar).

Fuqaroga xabar yuborilmaydi; murojaat `closed`, ochiq biriktirishlar `closed` bo'ladi — volontyor
ro'yxatida va eslatmalarda ular endi chiqmaydi.

Ishlatish (konteyner ichida):
  python scripts/close_stale_inquiries.py --group-id -5350260753            # faqat ko'rsatadi
  python scripts/close_stale_inquiries.py --group-id -5350260753 --apply    # yopadi
"""
import argparse
from datetime import datetime

import src.models.db_models  # noqa: F401  (barcha modellar ro'yxatga olinsin)
from sqlmodel import Session, select

from src.database.mysql import engine
from src.models.assignment import AssignmentStatus, InquiryAssignment
from src.models.inquiry import Inquiry, InquiryStatus


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--group-id", required=True, help="eski guruh ID si")
    parser.add_argument("--apply", action="store_true", help="haqiqatan yopish (aks holda faqat ro'yxat)")
    args = parser.parse_args()

    with Session(engine) as session:
        inquiries = session.exec(
            select(Inquiry).where(Inquiry.group_id == str(args.group_id), Inquiry.status == InquiryStatus.active)
        ).all()
        for inq in inquiries:
            print(f"№{inq.id}  {inq.created_at:%d.%m.%Y %H:%M}  {inq.section_name}")
            if not args.apply:
                continue
            inq.status = InquiryStatus.closed
            inq.updated_at = datetime.now()
            session.add(inq)
            for row in session.exec(
                select(InquiryAssignment).where(
                    InquiryAssignment.inquiry_id == inq.id,
                    InquiryAssignment.status.in_(AssignmentStatus.OPEN),
                )
            ).all():
                row.status = AssignmentStatus.closed
                session.add(row)
        if args.apply:
            session.commit()
        print(f"{'Yopildi' if args.apply else 'Topildi'}: {len(inquiries)} ta")


if __name__ == "__main__":
    main()
