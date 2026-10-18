import json
import os
from sqlmodel import Session, select
from src.database.mysql import engine
from src.models.benefit import Benefit


def seed_benefits():
    """Imtiyozlarni faqat imtiyozlar_boshqaruvi/imtiyozlar.json (Yagona Haqiqat Manbasi) dan yuklash."""
    json_file = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "../../imtiyozlar_boshqaruvi/imtiyozlar.json")
    )
    if not os.path.exists(json_file):
        raise FileNotFoundError(
            f"Yagona manba fayli topilmadi: {json_file}. "
            "Barcha imtiyozlar faqat imtiyozlar_boshqaruvi/imtiyozlar.json dan yuklanishi shart!"
        )

    with Session(engine) as session:
        print(f"Tayyor ma'lumotlar {json_file} dan yuklanmoqda...")
        with open(json_file, "r", encoding="utf-8") as f:
            items = json.load(f)

        new_order_indices = {item["order_index"] for item in items if "order_index" in item}

        # Yangi ro'yxatda (112 ta imtiyozda) mavjud bo'lmagan eski imtiyozlarni bazadan o'chirish
        deleted_count = 0
        for b in session.exec(select(Benefit)).all():
            if b.order_index not in new_order_indices:
                session.delete(b)
                deleted_count += 1
        if deleted_count > 0:
            session.flush()
            print(f"Eski ortiqcha {deleted_count} ta imtiyoz bazadan o'chirildi.")

        # Mavjud imtiyozlarni order_index bo'yicha lug'atga olish
        existing_benefits = {
            b.order_index: b for b in session.exec(select(Benefit)).all()
            if b.order_index is not None
        }

        inserted_count = 0
        updated_count = 0

        for item in items:
            idx = item.get("order_index")
            if idx in existing_benefits:
                b = existing_benefits[idx]
                for k, v in item.items():
                    if hasattr(b, k) and k != "id":
                        setattr(b, k, v)
                b.is_active = item.get("is_active", True)
                session.add(b)
                updated_count += 1
            else:
                b = Benefit(**item)
                b.is_active = item.get("is_active", True)
                session.add(b)
                inserted_count += 1

        session.commit()
        print(
            f"Muvaffaqiyatli yakunlandi: {inserted_count} ta yangi qo'shildi, "
            f"{updated_count} ta imtiyoz yangilandi. Jami amaldagi: {len(items)} ta."
        )


if __name__ == "__main__":
    seed_benefits()
