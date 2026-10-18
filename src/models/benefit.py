from datetime import datetime, timezone
from typing import TypeVar, List
from sqlmodel import Field, select
from src.models.base import BaseModel, table_prefix
from src.routes.deps.db_session import DBSession

BenefitType = TypeVar("BenefitType", bound="Benefit")


class BenefitCategory:
    PENSION_AID = "pension_aid"            # Nafaqa va moddiy yordam
    HEALTH_REHAB = "health_rehab"          # Tibbiyot va reabilitatsiya
    EDUCATION = "education"                # Ta'lim va yoshlar
    LABOR = "labor"                        # Mehnat va bandlik
    TRANSPORT = "transport"                # Transport va yo'l haqi
    HOUSING_COMMUNAL = "housing_communal"  # Uy-joy va kommunal
    TAX_FEE = "tax_fee"                    # Soliq va davlat bojlari
    OTHER = "other"                        # Boshqa


class Benefit(BaseModel, table=True):
    __tablename__ = table_prefix + "benefits"

    category: str = Field(default=BenefitCategory.OTHER, index=True)

    # Mos keluvchi toifalar
    for_first_group: bool = Field(default=True)
    for_second_group: bool = Field(default=True)
    for_third_group: bool = Field(default=True)
    for_child: bool = Field(default=True)
    for_parent: bool = Field(default=False)
    is_for_organization: bool = Field(default=False)

    # Qo'shimcha filtrlar
    min_age: int | None = Field(default=None)
    max_age: int | None = Field(default=None)
    gender: str | None = Field(default=None)            # male, female yoki None
    disability_state: str | None = Field(default=None)  # physical, vision, hearing, mental va h.k.

    # O'zbek tili (Lotin)
    title_uz: str = Field(sa_column_kwargs={"nullable": False})
    description_uz: str = Field(sa_column_kwargs={"nullable": False})
    amount_uz: str | None = Field(default=None)
    organization_uz: str | None = Field(default=None)
    legal_basis_uz: str | None = Field(default=None)

    # O'zbek tili (Kirill)
    title_oz: str = Field(sa_column_kwargs={"nullable": False})
    description_oz: str = Field(sa_column_kwargs={"nullable": False})
    amount_oz: str | None = Field(default=None)
    organization_oz: str | None = Field(default=None)
    legal_basis_oz: str | None = Field(default=None)

    # Rus tili
    title_ru: str | None = Field(default=None)
    description_ru: str | None = Field(default=None)
    amount_ru: str | None = Field(default=None)
    organization_ru: str | None = Field(default=None)
    legal_basis_ru: str | None = Field(default=None)

    # 5-blokli yo'riqnomalar va havolalar
    guide_uz: str | None = Field(default=None)
    guide_oz: str | None = Field(default=None)
    guide_ru: str | None = Field(default=None)
    mygov_url: str | None = Field(default=None)
    lex_url: str | None = Field(default=None)
    keywords: str | None = Field(default=None)

    is_active: bool = Field(default=True, index=True)
    order_index: int = Field(default=0)
    created_at: datetime | None = Field(default_factory=lambda: datetime.now(timezone.utc), index=True)

    def to_dict(self) -> dict:
        """Imtiyoz ma'lumotlarini lug'at (dict) ko'rinishida qaytaradi."""
        return {
            "id": self.id,
            "category": self.category,
            "for_first_group": self.for_first_group,
            "for_second_group": self.for_second_group,
            "for_third_group": self.for_third_group,
            "for_child": self.for_child,
            "for_parent": self.for_parent,
            "is_for_organization": self.is_for_organization,
            "min_age": self.min_age,
            "max_age": self.max_age,
            "gender": self.gender,
            "disability_state": self.disability_state,
            "title_uz": self.title_uz,
            "description_uz": self.description_uz,
            "amount_uz": self.amount_uz,
            "organization_uz": self.organization_uz,
            "legal_basis_uz": self.legal_basis_uz,
            "guide_uz": self.guide_uz,
            "title_oz": self.title_oz,
            "description_oz": self.description_oz,
            "amount_oz": self.amount_oz,
            "organization_oz": self.organization_oz,
            "legal_basis_oz": self.legal_basis_oz,
            "guide_oz": self.guide_oz,
            "title_ru": self.title_ru,
            "description_ru": self.description_ru,
            "amount_ru": self.amount_ru,
            "organization_ru": self.organization_ru,
            "legal_basis_ru": self.legal_basis_ru,
            "guide_ru": self.guide_ru,
            "mygov_url": self.mygov_url,
            "lex_url": self.lex_url,
            "keywords": self.keywords,
            "is_active": self.is_active,
            "order_index": self.order_index,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    @classmethod
    def get_user_benefits(
        cls,
        session: DBSession,
        category: str | None = None,
        disability_type: str | None = None,
        disability_state: str | None = None,
        age: int | None = None,
        gender: str | None = None,
    ) -> List["Benefit"]:
        """Foydalanuvchi profiliga mos keladigan imtiyozlarni saralab qaytaradi."""
        statement = select(cls).where(cls.is_active == True, cls.is_for_organization == False)

        if category:
            statement = statement.where(cls.category == category)

        # Guruh bo'yicha filtrlash
        if disability_type == "first_degree":
            statement = statement.where(cls.for_first_group == True)
        elif disability_type == "second_degree":
            statement = statement.where(cls.for_second_group == True)
        elif disability_type == "third_degree":
            statement = statement.where(cls.for_third_group == True)
        elif disability_type == "forth_degree":
            statement = statement.where(cls.for_child == True)

        # Ota-ona yoki maxsus holat
        if disability_state == "parent":
            statement = statement.where((cls.for_parent == True) | (cls.for_child == True))

        results = list(session.exec(statement.order_by(cls.order_index, cls.id)).all())

        # Qo'shimcha yosh, jins va kasallik turi bo'yicha tekshirish
        filtered = []
        for b in results:
            # Yosh filtri
            if age is not None:
                if b.min_age is not None and age < b.min_age:
                    continue
                if b.max_age is not None and age > b.max_age:
                    continue

            # Jins filtri
            if b.gender and gender and b.gender != gender:
                continue

            # Kasallik shakli (agar imtiyozda aniq ko'rsatilgan bo'lsa)
            if b.disability_state and disability_state and b.disability_state != disability_state:
                continue

            filtered.append(b)

        return filtered

    @classmethod
    def search_benefits(
        cls,
        session: DBSession,
        query: str,
        lang: str = "uz",
        category: str | None = None,
        user = None,
    ) -> List["Benefit"]:
        """
        Qidiruv so'rovi bo'yicha imtiyozlarni topish.
        Qidiruv: title, description, keywords, guide va legal_basis bo'yicha amalga oshiriladi.
        """
        if not query or not query.strip():
            return []

        clean_query = query.strip().lower()
        search_terms = clean_query.split()

        # Asosiy faol va jismoniy shaxslarga mo'ljallangan imtiyozlarni olish
        if user:
            age = (datetime.now().year - user.birth_year) if getattr(user, "birth_year", None) else None
            gender = user.gender.value if (getattr(user, "gender", None) and hasattr(user.gender, "value")) else (str(user.gender) if getattr(user, "gender", None) else None)
            d_type = user.disability_type.value if (getattr(user, "disability_type", None) and hasattr(user.disability_type, "value")) else (str(user.disability_type) if getattr(user, "disability_type", None) else None)
            d_state = user.disability_state.value if (getattr(user, "disability_state", None) and hasattr(user.disability_state, "value")) else (str(user.disability_state) if getattr(user, "disability_state", None) else None)

            base_benefits = cls.get_user_benefits(
                session=session,
                category=category if category != "all" else None,
                disability_type=d_type,
                disability_state=d_state,
                age=age,
                gender=gender,
            )
        else:
            statement = select(cls).where(cls.is_active == True, cls.is_for_organization == False)
            if category and category != "all":
                statement = statement.where(cls.category == category)
            base_benefits = list(session.exec(statement.order_by(cls.order_index, cls.id)).all())

        matched = []
        for b in base_benefits:
            searchable_parts = []
            if lang == "oz":
                searchable_parts.extend([
                    b.title_oz or "", b.description_oz or "", b.guide_oz or "", b.legal_basis_oz or ""
                ])
            elif lang == "ru":
                searchable_parts.extend([
                    b.title_ru or "", b.description_ru or "", b.guide_ru or "", b.legal_basis_ru or ""
                ])
            else:
                searchable_parts.extend([
                    b.title_uz or "", b.description_uz or "", b.guide_uz or "", b.legal_basis_uz or ""
                ])

            if b.keywords:
                searchable_parts.append(b.keywords)
            searchable_parts.append(b.title_uz or "")
            if b.title_oz:
                searchable_parts.append(b.title_oz)
            if b.title_ru:
                searchable_parts.append(b.title_ru)

            combined_text = " ".join(searchable_parts).lower()
            if all(term in combined_text for term in search_terms):
                matched.append(b)

        return matched
