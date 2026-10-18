#!/usr/bin/env python3
"""
scripts/apply_link_updates.py
Applies verified Lex.uz URLs and cleans authentic/fake mygov URLs
across enrich_guides.py, enrich_russian.py, and benefits_seed_data.json.
"""

import json
import os
import re

VERIFIED_LEX_URLS = {
    2: "https://lex.uz/docs/-4674902#-6032725",
    3: "https://lex.uz/docs/-4674902#-5997493",
    4: "https://lex.uz/docs/-4674902#-7606035",
    11: "https://lex.uz/docs/-4674902#-4688099",
    12: "https://lex.uz/docs/-4674902#-4688106",
    16: "https://lex.uz/docs/-6257288#-6263028",
    17: "https://lex.uz/docs/-6257288#-6263117",
    18: "https://lex.uz/docs/-6257288#-6263146",
    19: "https://lex.uz/docs/-6257288#-6263212",
    20: "https://lex.uz/docs/-6257288#-6266481",
    21: "https://lex.uz/docs/-6257288#-6266783",
    22: "https://lex.uz/docs/-6257288#-6266774",
    23: "https://lex.uz/docs/-6257288#-7901292",
    24: "https://lex.uz/docs/-6257288#-6266443",
    25: "https://lex.uz/docs/-6257288#-8276111",
    26: "https://lex.uz/docs/-6257288#-6266758",
    27: "https://lex.uz/docs/-6257288#-6266760",
    28: "https://lex.uz/docs/-6257288#-6266770",
    29: "https://lex.uz/docs/-6257288#-6267264",
    30: "https://lex.uz/docs/-6636282#-8045315",
    31: "https://lex.uz/docs/-5049511#-5054389",
    32: "https://lex.uz/docs/-7215989#-7216081",
    33: "https://lex.uz/docs/-5049511#-5054210",
    34: "https://lex.uz/docs/-5049511#-5054355",
    35: "https://lex.uz/docs/-7386982#-7390576",
    36: "https://lex.uz/docs/-39646#-8159563",
    37: "https://lex.uz/docs/-170143#-6104868",
    38: "https://lex.uz/docs/-2624884#-8161413",
    39: "https://lex.uz/docs/-5865484#-5867728",
    40: "https://lex.uz/docs/-152415#-5758654",
    41: "https://lex.uz/docs/-6181114#-6182264",
    42: "https://lex.uz/docs/-3765153#-6075856",
    43: "https://lex.uz/docs/-7374261#-7376203",
    44: "https://lex.uz/docs/-5679836#-8042886",
    53: "https://lex.uz/docs/-5893253#-8024173",
    54: "https://lex.uz/docs/-5893253#-8024174",
    55: "https://lex.uz/docs/-6076304#-6077809",
    56: "https://lex.uz/docs/-6076304#-6077981",
    57: "https://lex.uz/docs/-7386982#-7390576",
    58: "https://lex.uz/docs/-7196808#-7200630",
    59: "https://lex.uz/docs/-6764454#-6765631",
    60: "https://lex.uz/docs/-7036488#-7037321",
    61: "https://lex.uz/docs/-6759637#-6761411",
    62: "https://lex.uz/docs/-7362704#-8024592",
    63: "https://lex.uz/docs/-7327821#-8023074",
    64: "https://lex.uz/docs/-7027440#-7027781",
    65: "https://lex.uz/docs/-7027440#-7027755",
    66: "https://lex.uz/docs/-6786586#-6787082",
    67: "https://lex.uz/docs/-6759699#-6760300",
    68: "https://lex.uz/docs/-6738217#-6746431",
    69: "https://lex.uz/docs/-6796327#-8045656",
    70: "https://lex.uz/docs/-6725077#-6729291",
    71: "https://lex.uz/docs/-7125707#-8045784",
    72: "https://lex.uz/docs/-6834968#-6835845",
    73: "https://lex.uz/docs/-6834968#-6835846",
    74: "https://lex.uz/docs/-6834968#-6835847",
    75: "https://lex.uz/docs/-6590131#-8465214",
    76: "https://lex.uz/docs/-5409456#-8039036",
    77: "https://lex.uz/docs/-5044726#-8039362",
    78: "https://lex.uz/docs/-7357259#-7357788",
    79: "https://lex.uz/docs/-7374261#-7375944",
}

AUTHENTIC_MYGOV_MAP = {
    34: "https://my.gov.uz/uz/service/972",  # Protez va aravacha vaucheri
    38: "https://my.gov.uz/uz/service/308",  # Kommunal kompensatsiya
    39: "https://my.gov.uz/uz/service/601",  # Bola parvarishi nafaqasi
    42: "https://my.gov.uz/uz/service/260",  # OTM bakalavriat qabuli
    53: "https://my.gov.uz/uz/service/283",  # Sanatoriyga yo'llanma
    55: "https://yoshlardaftari.uz",        # Yoshlar daftari kursi
    56: "https://yoshlardaftari.uz",        # Yoshlar asbob-uskunalar subsidiyasi
    60: "https://my.gov.uz/uz/service/105",  # Ovchilik guvohnomasi
    61: "https://www.uzairways.com",        # Aviachipta
    69: "https://my.gov.uz/uz/service/712",  # Pedagog sertifikatlash
    70: "https://eticket.railway.uz",       # Poyezd chiptasi
    71: "https://my.gov.uz/uz/service/147",  # Kadastr xizmatlari
    75: "https://my.gov.uz/uz/service/791",  # Uyga chiqib xizmat ko'rsatish
    76: "https://my.gov.uz/uz/service/261",  # Haydovchilik imtihoni
    77: "https://my.gov.uz/uz/service/556",  # Fan sertifikati
    82: "https://my.gov.uz/uz/service/522",  # Kichik kema ro'yxati
    84: "https://my.sud.uz",                # Sudga murojaat portali
    86: "https://my.gov.uz/uz/service/328",  # Zagranpasport
    87: "https://my.gov.uz/uz/service/147",  # Kadastr pasporti
    88: "https://my.gov.uz/uz/service/216",  # Bog'chaga navbat
    89: "https://my.gov.uz/uz/service/270",  # Gaz va suv ulanish
    90: "https://my.gov.uz/uz/service/238",  # ERI sertifikati
    91: "https://my.gov.uz/uz/service/132",  # Nostrifikatsiya
    92: "https://my.gov.uz/uz/service/514",  # Trener toifasi
    93: "https://license.gov.uz",           # Litsenziya portali
    94: "https://my.gov.uz/uz/service/273",  # Elektrga ulanish
    95: "https://my.gov.uz/uz/service/723",  # Mobile-ID
    96: "https://my.gov.uz/uz/service/462",  # Agrotexnika ro'yxati
    97: "https://my.gov.uz/uz/service/512",  # Sport pasporti
    98: "https://my.gov.uz/uz/service/640",  # Tibbiyot attestatsiyasi
    99: "https://my.gov.uz/uz/service/114",  # Arxiv ma'lumotnomalari
    100: "https://my.gov.uz/uz/service/635", # Malaka sertifikati
    104: "https://yoshlardaftari.uz",       # Yoshlar moddiy yordami
    105: "https://yoshlardaftari.uz",       # Yer auksioni qoplash
    108: "https://my.gov.uz/uz/service/260", # Test to'lovidan ozod
    109: "https://my.gov.uz/uz/service/260", # Magistratura qabuli
    115: "https://yoshlardaftari.uz",       # IT grantlar
    117: "https://my.gov.uz/uz/service/283", # Sanatoriy yo'llanmasi
    120: "https://my.gov.uz/uz/service/283", # Sanatoriy yo'llanmasi
    124: "https://eticket.railway.uz",      # Poyezd chiptasi
    125: "https://eticket.railway.uz",      # Poyezd chiptasi
    128: "https://my.gov.uz/uz/service/556", # Til imtihoni 50%
    129: "https://my.gov.uz/uz/service/782", # Yotoqxonaga ustuvor qabul
    134: "https://my.gov.uz/uz/service/348", # Uy-joy subsidiyasi
}

print(f"Loaded {len(VERIFIED_LEX_URLS)} verified Lex URLs.")
print(f"Loaded {len(AUTHENTIC_MYGOV_MAP)} authentic MyGov/portal URLs.")
