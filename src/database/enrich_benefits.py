import json
import re

def cyr_to_lat(text: str) -> str:
    if not text:
        return ""
    vowels = "аеёиоуэюяўАЕЁИОУЭЮЯЎ"
    text = re.sub(r"(^|[\s\(\[\{\"\'«])Е", r"\1Ye", text)
    text = re.sub(r"(^|[\s\(\[\{\"\'«])е", r"\1ye", text)
    for v in vowels:
        text = text.replace(v + "е", v + "ye")
        text = text.replace(v + "Е", v + "Ye")
    table = {
        "А": "A", "а": "a", "Б": "B", "б": "b", "В": "V", "в": "v",
        "Г": "G", "г": "g", "Д": "D", "д": "d", "Е": "E", "е": "e",
        "Ё": "Yo", "ё": "yo", "Ж": "J", "ж": "j", "З": "Z", "з": "z",
        "И": "I", "и": "i", "Й": "Y", "й": "y", "К": "K", "к": "k",
        "Л": "L", "л": "l", "М": "M", "м": "m", "Н": "N", "н": "n",
        "О": "O", "о": "o", "П": "P", "п": "p", "Р": "R", "р": "r",
        "С": "S", "с": "s", "Т": "T", "т": "t", "У": "U", "у": "u",
        "Ф": "F", "ф": "f", "Х": "X", "х": "x", "Ц": "Ts", "ц": "ts",
        "Ч": "Ch", "ч": "ch", "Ш": "Sh", "ш": "sh", "Щ": "Sh", "щ": "sh",
        "Ъ": "’", "ъ": "’", "Ь": "", "ь": "", "Э": "E", "э": "e",
        "Ю": "Yu", "ю": "yu", "Я": "Ya", "я": "ya", "Ў": "O‘", "ў": "o‘",
        "Қ": "Q", "қ": "q", "Ғ": "G‘", "ғ": "g‘", "Ҳ": "H", "ҳ": "h",
    }
    res = []
    for char in text:
        res.append(table.get(char, char))
    return "".join(res)


def lat_to_cyr(text: str) -> str:
    if not text:
        return ""
    # Map multi-character letters first
    replacements = [
        ("O‘", "Ў"), ("o‘", "ў"), ("O'", "Ў"), ("o'", "ў"), ("O`", "Ў"), ("o`", "ў"),
        ("G‘", "Ғ"), ("g‘", "ғ"), ("G'", "Ғ"), ("g'", "ғ"), ("G`", "Ғ"), ("g`", "ғ"),
        ("Sh", "Ш"), ("sh", "ш"), ("SH", "Ш"),
        ("Ch", "Ч"), ("ch", "ч"), ("CH", "Ч"),
        ("Yo", "Ё"), ("yo", "ё"), ("YO", "Ё"),
        ("Yu", "Ю"), ("yu", "ю"), ("YU", "Ю"),
        ("Ya", "Я"), ("ya", "я"), ("YA", "Я"),
        ("Ye", "Е"), ("ye", "е"), ("YE", "Е"),
        ("Ts", "Ц"), ("ts", "ц"), ("TS", "Ц"),
    ]
    for lat, cyr in replacements:
        text = text.replace(lat, cyr)

    # In Uzbek Cyrillic: E at start of word or after vowel is Э/э, otherwise Е/е
    text = re.sub(r"(^|[\s\(\[\{\"\'«])E", r"\1Э", text)
    text = re.sub(r"(^|[\s\(\[\{\"\'«])e", r"\1э", text)
    text = re.sub(r"([АЕЁИОУЭЮЯЎаеёиоуэюяў])E", r"\1Э", text)
    text = re.sub(r"([АЕЁИОУЭЮЯЎаеёиоуэюяў])e", r"\1э", text)

    single_map = {
        "A": "А", "a": "а", "B": "Б", "b": "б", "V": "В", "v": "в",
        "G": "Г", "g": "г", "D": "Д", "d": "д", "E": "Е", "e": "е",
        "J": "Ж", "j": "ж", "Z": "З", "z": "з", "I": "И", "i": "и",
        "Y": "Й", "y": "й", "K": "К", "k": "к", "L": "Л", "l": "л",
        "M": "М", "m": "м", "N": "Н", "n": "н", "O": "О", "o": "о",
        "P": "П", "p": "п", "R": "Р", "r": "р", "S": "С", "s": "с",
        "T": "Т", "t": "т", "U": "У", "u": "у", "F": "Ф", "f": "ф",
        "X": "Х", "x": "х", "Q": "Қ", "q": "қ", "H": "Ҳ", "h": "ҳ",
        "’": "ъ", "'": "ъ", "`": "ъ",
    }
    res = []
    for char in text:
        res.append(single_map.get(char, char))
    return "".join(res)


# Aniq va tushunarli sarlavhalar lug'ati (ID bo'yicha)
ENRICHED_TITLES = {
    1: ("Yuridik shaxslardan olinadigan yer solig‘i imtiyozi", "tax_fee"),
    2: ("Jismoniy shaxslardan olinadigan yer solig‘idan to‘liq ozod qilish", "tax_fee"),
    3: ("Urush qatnashchilari va parvarishlovchilar daromad solig‘i imtiyozi", "tax_fee"),
    4: ("Bolalikdan va I-II guruh nogironligi bor shaxslar daromad solig‘i imtiyozi", "tax_fee"),
    5: ("Qat’iy belgilangan daromad solig‘idan 50% chegirma", "tax_fee"),
    6: ("Nogironlar jamoat birlashmalari uchun foyda solig‘i (0%)", "tax_fee"),
    7: ("Qarovchilar xizmatiga yo‘naltirilgan mablag‘lar foyda solig‘i imtiyozi", "tax_fee"),
    8: ("Nogiron xodimlarni ishga olgan korxonalar foyda solig‘i imtiyozi", "tax_fee"),
    9: ("Ixtisoslashtirilgan sex va korxonalar uchun ijtimoiy soliq imtiyozi", "tax_fee"),
    10: ("I va II guruh yakka tartibdagi tadbirkorlar uchun ijtimoiy soliq imtiyozi", "tax_fee"),
    11: ("Urush nogironlari uchun mol-mulk solig‘idan to‘liq ozod qilish", "tax_fee"),
    12: ("I va II guruh uchun mol-mulk solig‘idan ozod qilish (60 kv.m gacha)", "tax_fee"),
    13: ("Nogironlar jamoat birlashmalari uchun mol-mulk solig‘i (to‘liq ozod)", "tax_fee"),
    14: ("Aylanmadan olinadigan soliq bo‘yicha 0% stavka", "tax_fee"),
    15: ("Qo‘shilgan qiymat solig‘i (QQS) bo‘yicha imtiyoz", "tax_fee"),
    16: ("Yillik 30 kalendar kunlik uzaytirilgan mehnat ta’tili", "labor"),
    17: ("Ish boshlaganiga 6 oy to‘lmasdan mehnat ta’tili olish huquqi", "labor"),
    18: ("Yillik mehnat ta’tilini o‘ziga qulay vaqtda olish huquqi", "labor"),
    19: ("Mehnat ta’tillarini pulli kompensatsiyaga almashtirish huquqi", "labor"),
    20: ("Ish haqi saqlanadigan 14 kalendar kunlik qo‘shimcha ta’til", "labor"),
    21: ("Ish haqi saqlanmaydigan 30 kungacha ta’til olish huquqi", "labor"),
    22: ("Qisqartirilgan ish haftasi (haftasiga ko‘pi bilan 36 soat)", "labor"),
    23: ("Nogiron bolani tarbiyalayotganlarga oyiga 1 kun qo‘shimcha dam olish", "labor"),
    24: ("Tungi va qo‘shimcha ishlarga faqat yozma rozilik bilan jalb etish", "labor"),
    25: ("Tibbiy xulosaga asosan to‘liqsiz ish vaqti belgilash kafolati", "labor"),
    26: ("Tashkilotlarda 3% zaxiralangan ish o‘rinlariga joylashish kafolati", "labor"),
    27: ("Sog‘lig‘iga zid bo‘lmagan yengilroq ishga o‘tkazish majburiyati", "labor"),
    28: ("Ishga qabul qilishda dastlabki sinov muddatisiz ishga olish", "labor"),
    29: ("Tabiiy ofatlar vaqtida masofaviy mehnatga o‘tkazish kafolati", "labor"),
    30: ("Tibbiy, kasbiy va ijtimoiy reabilitatsiya xizmatlari kafolati", "health_rehab"),
    31: ("Barcha bosqichdagi ta’limni bepul yoki imtiyozli olish kafolati", "education"),
    32: ("Jismoniy tarbiya va sport inshootlaridan bepul foydalanish", "education"),
    33: ("Madaniy meros ob’yektlari, muzey va teatrlarga bepul kirish", "education"),
    34: ("Protez-ortopediya moslamalari va aravachalar bilan bepul ta’minlash", "health_rehab"),
    35: ("Ijtimoiy ehtiyojmand aholi uchun kvotalangan ish o‘rinlariga joylashish", "labor"),
    36: ("Shahar jamoat transportidan bepul foydalanish (urush nogironlari)", "transport"),
    37: ("Yuqori texnologik ixtisoslashtirilgan bepul tibbiy yordam olish", "health_rehab"),
    38: ("Uy-joy kommunal to‘lovlari xarajatlari uchun oylik kompensatsiya", "housing_communal"),
    39: ("O‘zgalar parvarishiga muhtoj bolaga qarovchilar uchun oylik nafaqa", "pension_aid"),
    40: ("Yadro poligonlarida bo‘lgan fuqarolarga salomatlikni tiklash yordami", "pension_aid"),
    41: ("Temir yo‘l va avia chiptalarni navbatsiz xarid qilish huquqi", "transport"),
    42: ("OTMga kirishda 2 foizli qo‘shimcha davlat granti kvotasi", "education"),
    43: ("«Sahovat» va «Muruvvat» uylarida yashovchilarga pensiyaning 20%ini to‘lash", "pension_aid"),
    44: ("Ixtisoslashtirilgan maktab-internatlarda to‘liq davlat ta’minoti", "education"),
    45: ("Sanatoriy turidagi ixtisoslashtirilgan maktablarda bepul ta’lim", "education"),
    46: ("Uyda yakka tartibda bepul ta’lim olish imkoniyati", "education"),
    47: ("Alohida ehtiyojli bolalar uchun inklyuziv ta’lim sinflari", "education"),
    48: ("Maktab o‘quvchilarini kasb-hunarga bepul o‘qitish", "education"),
    49: ("Ixtisoslashtirilgan bog‘chalarda ota-onalar to‘lovidan ozod etish", "education"),
    50: ("Reabilitatsiya markaziga ega ko‘p tarmoqli bog‘chada bepul ta’minot", "education"),
    51: ("Rivojlanishida nuqsoni bor bolalar bog‘chasi to‘lovidan ozod qilish", "education"),
    52: ("Paralimpiyachilar matonat maktabida bepul ijtimoiy xizmatlar", "education"),
    53: ("Kasaba uyushmalari sanatoriylariga bepul yoki imtiyozli yo‘llanma", "health_rehab"),
    54: ("Yolg‘iz yashovchi nogiron shaxslarga bir martalik moddiy yordam", "pension_aid"),
    55: ("Nodavlat kurslarda kasb va xorijiy til o‘rganish subsidiyasi (50 BHM)", "education"),
    56: ("Kasbga tayyorlash va qayta tayyorlashda stipendiya to‘lash", "education"),
    57: ("Ish o‘rnini nogiron xodimlarga moslashtirish uchun subsidiya", "labor"),
    58: ("Davlat tomonidan bepul psixologik yordam ko‘rsatish", "health_rehab"),
    59: ("Avtoturargohlarda nogironlar transporti uchun bepul to‘xtash joyi", "transport"),
    60: ("Ovchilik guvohnomasini rasmiylashtirish to‘lovidan ozod etish", "tax_fee"),
    61: ("Mo‘ynoq va Zomin aeroportlariga aviachipta to‘loviga 50% chegirma", "transport"),
    62: ("Nogironligi bor bolalar uchun kunduzgi parvarish markazi xizmati", "health_rehab"),
    63: ("Nogironligi bo‘lgan shaxslarga kasb o‘rganish davrida stipendiya", "education"),
    64: ("I guruh va hamrohiga shahar yo‘lovchi transportida bepul yurish", "transport"),
    65: ("Shaxsiy avtotransportni moslashtirish xarajatini 50% qoplash", "transport"),
    66: ("Nodavlat ta’lim kurslarida o‘qish xarajatlarini qoplash (subsidiya)", "education"),
    67: ("Nogironligi bor shaxslarni kasbga o‘qitish markazlari subsidiyasi", "education"),
    68: ("Haq to‘lanadigan ishlab chiqarish amaliyotini tashkil etish", "labor"),
    69: ("Pedagog kadrlarni kasbiy sertifikatlash to‘loviga 50% chegirma", "tax_fee"),
    70: ("Poyezd yoki shaharlararo avtobusda bepul yurish (yiliga 1 marta)", "transport"),
    71: ("Kadastr, notarius va davlat xizmatlari yig‘imlariga 50% chegirma", "tax_fee"),
    72: ("Davlat sport tadbirlari, teatr va muzeylarga bepul kirish", "education"),
    73: ("Davlat sport zallari va suzish havzalaridan bepul foydalanish", "education"),
    74: ("Yashash joyida bepul dezinfeksiya va dezinseksiya o‘tkazish", "housing_communal"),
    75: ("Davlat xizmatlarini uyga (joylarga) chiqqan holda bepul ko‘rsatish", "tax_fee"),
    76: ("Haydovchilik guvohnomasi imtihoni to‘loviga 50% chegirma", "tax_fee"),
    77: ("Umumta’lim fanlari sertifikat imtihoni to‘loviga 50% chegirma", "tax_fee"),
    78: ("Davlat chegarasidan o‘tishda «Fast-track» bepul xizmati", "transport"),
    79: ("«Yoshlar daftari» orqali davolanish va reabilitatsiyaga yordam", "health_rehab"),
    80: ("«Ayollar daftari» orqali bir martalik moddiy yordam", "pension_aid"),
    81: ("Uy-joy sharoitini nogironlikka moslashtirish yordami (50 BHM)", "housing_communal"),
    82: ("Kichik kemalarni ro‘yxatdan o‘tkazish to‘loviga 50% chegirma", "tax_fee"),
    83: ("Barcha davlat xizmatlari ko‘rsatish bojlari va yig‘imlariga 50% chegirma", "tax_fee"),
    84: ("Sudlarga murojaat qilishda davlat bojidan to‘liq ozod etish", "tax_fee"),
    85: ("Yer uchastkasiga ijara huquqini e’tirof etish to‘loviga 50% chegirma", "tax_fee"),
    86: ("Xorijga chiqish biometrik pasporti (zagranpasport)ga 50% chegirma", "tax_fee"),
    87: ("Kadastr xizmatlari bo‘yicha to‘lovlarga 50% chegirma", "tax_fee"),
    88: ("Bolalarni davlat maktabgacha ta’limiga navbatsiz qabul qilish", "education"),
    89: ("Gaz, issiqlik va suv tarmoqlariga ulanish to‘loviga 50% chegirma", "housing_communal"),
    90: ("ERI (Elektron raqamli imzo) sertifikati olishga 50% chegirma", "tax_fee"),
    91: ("Xorijiy diplomni tan olish (nostrifikatsiya) to‘loviga 50% chegirma", "education"),
    92: ("Trener va yo‘riqchilarga malaka toifasi berishga 50% chegirma", "tax_fee"),
    93: ("Yuridik va advokatlik litsenziyasi to‘loviga 50% chegirma", "tax_fee"),
    94: ("Elektr tarmoqlariga ulanish davlat xizmatiga 50% chegirma", "housing_communal"),
    95: ("Mobil-ID tizimida identifikatsiyadan o‘tish to‘loviga 50% chegirma", "tax_fee"),
    96: ("Qishloq xo‘jaligi texnikalarini ro‘yxatga olishga 50% chegirma", "tax_fee"),
    97: ("Sport pasportini berish bo‘yicha to‘lovga 50% chegirma", "tax_fee"),
    98: ("Tibbiyot xodimlarini attestatsiyadan o‘tkazishga 50% chegirma", "tax_fee"),
    99: ("Arxiv ma’lumotnomalari olish davlat xizmatiga 50% chegirma", "tax_fee"),
    100: ("Malaka sertifikati berish davlat xizmatlariga 50% chegirma", "tax_fee"),
    101: ("Urush qatnashchilari va nogironlariga har yillik pul mukofoti", "pension_aid"),
    102: ("«Ayollar daftari»dagi I va II guruh xotin-qizlarga moddiy yordam", "pension_aid"),
    103: ("30 yoshdan oshgan xotin-qizlarga ijtimoiy yordam to‘lovi", "pension_aid"),
    104: ("Nogironligi bor yoshlarga bir martalik ijtimoiy yordam (1 BHM)", "pension_aid"),
    105: ("Auksionda yer uchastkasi sotib olish xarajatlarini qoplash", "housing_communal"),
    106: ("Yolg‘iz yashovchi nogiron shaxslarga uy-joy ta’miri (50 BHM)", "housing_communal"),
    107: ("Yer uchastkasi auksioni xarajatlarini davlat hisobidan qoplash", "housing_communal"),
    108: ("OTM test sinovlarida qatnashish to‘lovidan to‘liq ozod etish", "education"),
    109: ("Magistratura mutaxassisliklariga qabulda qo‘shimcha imtiyoz", "education"),
    110: ("Davlat va ijtimoiy xizmatlardan navbatsiz foydalanish kafolati", "tax_fee"),
    111: ("Shifoxonada yotgan nogiron bolaning ota-onasi uchun sharoit kafolati", "health_rehab"),
    112: ("Shifoxonada bolaga qarovchi ota-ona uchun bepul ovqatlanish", "health_rehab"),
    113: ("Ambulatoriyada davolanishda dori vositalari bilan bepul ta’minlash", "health_rehab"),
    114: ("«Muruvvat» internat uylarida bepul tibbiy-ijtimoiy xizmatlar", "health_rehab"),
    115: ("«Imkon ta’lim» IT grantlari orqali bepul dasturlashni o‘rganish", "education"),
    116: ("Ish stajiga ega bo‘lmagan shaxslarga nogironlik nafaqasi tayinlash", "pension_aid"),
    117: ("Urush nogironlariga har yili sanatoriyda bepul davolanish", "health_rehab"),
    118: ("Avtomobil benzini xarajatlari uchun oylik pul kompensatsiyasi", "transport"),
    119: ("Chernobil AES halokati nogironlariga to‘liq ijtimoiy paket", "pension_aid"),
    120: ("I va II guruh uchun har 2 yilda sanatoriyda bepul davolanish", "health_rehab"),
    121: ("Urush nogironlariga imtiyozli dori-darmon ta’minoti kafolati", "health_rehab"),
    122: ("I va II guruh talabalari uchun 50% oshirilgan stipendiya", "education"),
    123: ("Protez-ortopediya moslamalari o‘rniga pul kompensatsiyasi olish", "health_rehab"),
    124: ("Poyezd chiptasini qaytarishda ushlab qolinadigan jarimadan ozod qilish", "transport"),
    125: ("Temir yo‘llarda yiliga bir marta bepul borish-kelish huquqi", "transport"),
    126: ("Temir yo‘l vokzallarida navbatsiz dam olish xonasi berilishi", "transport"),
    127: ("Nogironlar aravachasini jamoat transportida bepul tashish", "transport"),
    128: ("Chet tili bilish darajasi imtihoni to‘loviga 50% chegirma", "education"),
    129: ("OTM talabalar turar joyiga (yotoqxonaga) ustuvor qabul", "education"),
    130: ("Olimpiya va Paralimpiya kollejlariga 5% qo‘shimcha kvota", "education"),
    131: ("Nogiron bolasi bor onalarga 5 yil oldin pensiyaga chiqish huquqi", "pension_aid"),
    132: ("Urush oqibatida nogiron bo‘lganlar pensiyasiga ustamalar", "pension_aid"),
    133: ("I va II guruh pensiyasini ish stajiga qarab qayta hisoblash", "pension_aid"),
    134: ("Uy-joy subsidiyasi olishda nogironligi bor shaxslarga ustuvorlik", "housing_communal"),
}

def clean_org(org):
    if not org:
        return ""
    org = re.sub(r",\s*", ", ", org)
    org = re.sub(r"\s+", " ", org).strip()
    return org

def clean_legal_uz(legal):
    if not legal:
        return ""
    # Deduplicate existing repetitive consecutive prefixes
    legal = re.sub(r'(?:Vazirlar\s+Mahkamasining\s*)+', 'Vazirlar Mahkamasining ', legal, flags=re.IGNORECASE)
    legal = re.sub(r'(?:Prezident\s+Farmoni\s*)+', 'Prezident Farmoni ', legal, flags=re.IGNORECASE)
    legal = re.sub(r'(?:Prezident\s+Qarori\s*)+', 'Prezident Qarori ', legal, flags=re.IGNORECASE)
    legal = re.sub(r'(?:Qonun\s*)+', 'Qonun ', legal, flags=re.IGNORECASE)

    # Standardize replacements idempotently
    legal = re.sub(r'(?:Vazirlar\s+Mahkamasining\s+)*(?:ПКМ|PKM|ВМҚ|VMQ)[-\s–—]*(\d+)(?:-son\s+qarori)?', r'Vazirlar Mahkamasining \1-son qarori', legal, flags=re.IGNORECASE)
    legal = re.sub(r'(?:Prezident\s+Farmoni\s+)*(?:ПФ|PF)[-\s–—]*(\d+)', r'Prezident Farmoni PF-\1', legal, flags=re.IGNORECASE)
    legal = re.sub(r'(?:Prezident\s+Qarori\s+)*(?:ПҚ|PQ)[-\s–—]*(\d+)', r'Prezident Qarori PQ-\1', legal, flags=re.IGNORECASE)
    legal = re.sub(r'(?:Qonun\s+)*(?:ЎРҚ|O‘RQ|ORQ|O\'RQ)[-\s–—]*(\d+)', r'Qonun O‘RQ-\1', legal, flags=re.IGNORECASE)

    legal = re.sub(r'\)', r') ', legal)
    legal = re.sub(r'\(', r' (', legal)
    legal = re.sub(r',\s*', r', ', legal)
    legal = re.sub(r'\s+', ' ', legal).strip()
    return legal

def clean_legal_oz(legal):
    if not legal:
        return ""
    # Deduplicate existing repetitive consecutive prefixes
    legal = re.sub(r'(?:Вазирлар\s+Маҳкамасининг\s*)+', 'Вазирлар Маҳкамасининг ', legal, flags=re.IGNORECASE)
    legal = re.sub(r'(?:Президент\s+Фармони\s*)+', 'Президент Фармони ', legal, flags=re.IGNORECASE)
    legal = re.sub(r'(?:Президент\s+Қарори\s*)+', 'Президент Қарори ', legal, flags=re.IGNORECASE)
    legal = re.sub(r'(?:Қонун\s*)+', 'Қонун ', legal, flags=re.IGNORECASE)

    # Standardize replacements idempotently
    legal = re.sub(r'(?:Вазирлар\s+Маҳкамасининг\s+)*(?:ПКМ|PKM|ВМҚ|VMQ)[-\s–—]*(\d+)(?:-сон\s+қарори)?', r'Вазирлар Маҳкамасининг \1-сон қарори', legal, flags=re.IGNORECASE)
    legal = re.sub(r'(?:Президент\s+Фармони\s+)*(?:ПФ|PF)[-\s–—]*(\d+)', r'Президент Фармони ПФ-\1', legal, flags=re.IGNORECASE)
    legal = re.sub(r'(?:Президент\s+Қарори\s+)*(?:ПҚ|PQ)[-\s–—]*(\d+)', r'Президент Қарори ПҚ-\1', legal, flags=re.IGNORECASE)
    legal = re.sub(r'(?:Қонун\s+)*(?:ЎРҚ|O‘RQ|ORQ|O\'RQ)[-\s–—]*(\d+)', r'Қонун ЎРҚ-\1', legal, flags=re.IGNORECASE)

    legal = re.sub(r'\)', r') ', legal)
    legal = re.sub(r'\(', r' (', legal)
    legal = re.sub(r',\s*', r', ', legal)
    legal = re.sub(r'\s+', ' ', legal).strip()
    return legal

def clean_desc_uz(desc):
    if not desc:
        return ""
    desc = re.sub(r"shaxslarBolaligidan", "shaxslar, Bolaligidan", desc)
    desc = re.sub(r"biriNogironligi", "biri, Nogironligi", desc)
    desc = re.sub(r"llaniladiYer", "llaniladi. Yer", desc)
    desc = re.sub(r"lariBHMning", "lari, BHMning", desc)
    desc = re.sub(r"foiziYaIDXP", "foizi, YaIDXP", desc)
    desc = re.sub(r"shaxslarChernobil", "shaxslar, Chernobil", desc)
    desc = re.sub(r"shaxslarUrush", "shaxslar, Urush", desc)
    desc = re.sub(r"shaxslarI va II", "shaxslar, I va II", desc)
    desc = re.sub(r";\s*(\d+[\.\)])\s*", r";\n\1 ", desc)
    return desc

def clean_desc_oz(desc):
    if not desc:
        return ""
    desc = re.sub(r"шахсларБолалигидан", "шахслар, Болалигидан", desc)
    desc = re.sub(r"бириНогиронлиги", "бири, Ногиронлиги", desc)
    desc = re.sub(r"лланиладиЕр", "лланилади. Ер", desc)
    desc = re.sub(r"лариБҲМнинг", "лари, БҲМнинг", desc)
    desc = re.sub(r"шахсларЧернобил", "шахслар, Чернобил", desc)
    desc = re.sub(r"шахсларУруш", "шахслар, Уруш", desc)
    desc = re.sub(r"шахсларI ва II", "шахслар, I ва II", desc)
    desc = re.sub(r";\s*(\d+[\.\)])\s*", r";\n\1 ", desc)
    return desc

def enrich_all(seed_path: str = "imtiyozlar_boshqaruvi/imtiyozlar.json"):
    with open(seed_path, "r", encoding="utf-8") as f:
        items = json.load(f)

    for it in items:
        idx = it["order_index"]
        if idx in ENRICHED_TITLES:
            new_title_uz, new_cat = ENRICHED_TITLES[idx]
            it["title_uz"] = new_title_uz
            it["title_oz"] = lat_to_cyr(new_title_uz)
            it["category"] = new_cat

        # Clean org and legal
        it["organization_uz"] = clean_org(it["organization_uz"])
        it["organization_oz"] = clean_org(it["organization_oz"])
        it["legal_basis_uz"] = clean_legal_uz(it["legal_basis_uz"])
        it["legal_basis_oz"] = clean_legal_oz(it["legal_basis_oz"])

        # Clean descriptions
        it["description_uz"] = clean_desc_uz(it.get("description_uz", ""))
        it["description_oz"] = clean_desc_oz(it.get("description_oz", ""))

    with open(seed_path, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)

    print(f"Successfully enriched all {len(items)} benefits with clean titles, categories, and legal bases!")

if __name__ == "__main__":
    enrich_all()
