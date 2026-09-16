from src.models.user import Region, User, GenderType


gender_types_uz = {
    'male': 'Erkak',
    'female': 'Ayol',
}
gender_types_ru = {
    'male': 'Мужской',
    'female': 'Женский',
}
gender_types = gender_types_uz

disability_types_uz = {
    'first_degree': '1⃣ Birinchi guruh',
    'second_degree': '2⃣ Ikkinchi guruh',
    'third_degree': '3⃣ Uchinchi guruh',
    'forth_degree': '4⃣ Toʻrtinchi guruh (18 yoshgacha nogironligi boʻlgan bola)',
    'none': '🚫 Nogironlik guruhi yoʻq',
}
disability_types_ru = {
    'first_degree': '1⃣ Первая группа',
    'second_degree': '2⃣ Вторая группа',
    'third_degree': '3⃣ Третья группа',
    'forth_degree': '4⃣ Четвертая группа (ребенок с инвалидностью до 18 лет)',
    'none': '🚫 Нет группы инвалидности',
}
disability_types = disability_types_uz

disability_states_uz = {
    'physical': '👩🏻‍🦽 Jismoniy nogironlik',
    'vision': '🧑🏻‍🦯 Ko‘rish bo‘yicha nogironlik',
    'hearing': '🧏🏻‍♀ Eshitish bo‘yicha nogironlik',
    'mental': '🧠 Aqliy nogironlik',
    'psychological': '❤️‍🩹 Ruhiy nogironlik',
    'parent': '👩🏻‍🍼Nogironligi bo‘lgan bolaning ota-onasi',
    'aids': '🩸OIV/OITS bo‘yicha nogironlik',
    'other': 'Boshqa',
}
disability_states_ru = {
    'physical': '👩🏻‍🦽 Физическая инвалидность',
    'vision': '🧑🏻‍🦯 Инвалидность по зрению',
    'hearing': '🧏🏻‍♀ Инвалидность по слуху',
    'mental': '🧠 Ментальная инвалидность',
    'psychological': '❤️‍🩹 Психологическая инвалидность',
    'parent': '👩🏻‍🍼Родитель ребенка с инвалидностью',
    'aids': '🩸Инвалидность в связи с ВИЧ/СПИД',
    'other': 'Другое',
}
disability_states = disability_states_uz

regions_uz = {region.name: region.value for region in Region}
regions_ru = {
    'R0': 'г. Ташкент',
    'R1': 'Андижанская область',
    'R2': 'Бухарская область',
    'R3': 'Ферганская область',
    'R4': 'Джизакская область',
    'R5': 'Хорезмская область',
    'R6': 'Наманганская область',
    'R7': 'Навоийская область',
    'R8': 'Кашкадарьинская область',
    'R9': 'Республика Каракалпакстан',
    'R10': 'Самаркандская область',
    'R11': 'Сырдарьинская область',
    'R12': 'Сурхандарьинская область',
    'R13': 'Ташкентская область',
}
regions = regions_uz


def get_gender_types(lang: str = "uz") -> dict[str, str]:
    return gender_types_ru if lang == "ru" else gender_types_uz


def get_disability_types(lang: str = "uz") -> dict[str, str]:
    return disability_types_ru if lang == "ru" else disability_types_uz


def get_disability_states(lang: str = "uz") -> dict[str, str]:
    return disability_states_ru if lang == "ru" else disability_states_uz


def get_regions(lang: str = "uz") -> dict[str, str]:
    return regions_ru if lang == "ru" else regions_uz


import html


def create_user_info(user: User, with_link=True, lang: str | None = None) -> str:
    user_lang = lang or getattr(user, 'language', 'uz') or 'uz'
    if not user.username:
        user_link = f'tg://user?id={user.user_id}'
    else:
        user_link = f'https://t.me/{user.username}'

    name = html.escape(f"{user.first_name or ''} {user.last_name or ''}".strip()) or "Foydalanuvchi"

    if user_lang == "ru":
        gender_text = 'Мужской' if user.gender == GenderType.male else 'Женский'
        region_text = regions_ru.get(user.region.name if user.region else '', 'Не указан')
        d_type = disability_types_ru.get(user.disability_type.value if user.disability_type else '', 'Не указана')
        d_state = disability_states_ru.get(user.disability_state.value if user.disability_state else '', 'Не указано')
        user_str = (
            f"• <b>Имя:</b> {name}<br/>"
            f"• <b>ID:</b> <code>{user.user_id}</code><br/>"
            f"• <b>Год рождения:</b> {user.birth_year or 'Не указан'}<br/>"
            f"• <b>Пол:</b> {gender_text}<br/>"
            f"• <b>Регион:</b> {region_text}<br/>"
            f"• <b>Группа инвалидности:</b> {d_type}<br/>"
            f"• <b>Форма инвалидности:</b> {d_state}<br/>"
            f"• <b>Номер телефона:</b> {user.phone or 'Не указан'}<br/>"
            f"• <b>Язык общения:</b> Русский 🇷🇺<br/>"
        )
        if with_link:
            user_str += f'• 🔗 <b><a href="{user_link}">Ссылка для связи</a></b><br/>'
    else:
        gender_text = 'Erkak' if user.gender == GenderType.male else 'Ayol'
        not_specified = "Ko'rsatilmadi"
        region_text = regions_uz.get(user.region.name if user.region else '', not_specified)
        d_type = disability_types_uz.get(user.disability_type.value if user.disability_type else '', not_specified)
        d_state = disability_states_uz.get(user.disability_state.value if user.disability_state else '', not_specified)
        birth_year_text = str(user.birth_year) if user.birth_year else not_specified
        phone_text = user.phone or not_specified
        user_str = (
            f"• <b>Ismi:</b> {name}<br/>"
            f"• <b>ID:</b> <code>{user.user_id}</code><br/>"
            f"• <b>Tug'ilgan yili:</b> {birth_year_text}<br/>"
            f"• <b>Jinsi:</b> {gender_text}<br/>"
            f"• <b>Hudud:</b> {region_text}<br/>"
            f"• <b>Nogironlik guruhi:</b> {d_type}<br/>"
            f"• <b>Nogironlik holati:</b> {d_state}<br/>"
            f"• <b>Telefon raqami:</b> {phone_text}<br/>"
            f"• <b>Muloqot tili:</b> O'zbekcha 🇺🇿<br/>"
        )
        if with_link:
            user_str += f'• 🔗 <b><a href="{user_link}">Bog\'lanish uchun havola</a></b><br/>'

    return user_str
