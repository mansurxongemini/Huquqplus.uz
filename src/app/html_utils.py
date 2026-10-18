"""SULGUK (HTML) rejimi uchun matn yordamchilari.

Sulguk oddiy "\\n" ni bo'sh joy deb hisoblaydi: fuqaro yozgan ko'p qatorli matn yoki Telegram'dan
olingan message.html_text bitta qatorga yopishib qoladi. Qator tashlash faqat <br/> bilan saqlanadi.
"""
import html


def nl2br(text: str) -> str:
    """Tayyor HTML ichidagi qator tashlashlarni <br/> ga aylantiradi."""
    return (text or "").replace("\r\n", "\n").replace("\n", "<br/>")


def escape_multiline(text: str | None) -> str:
    """Foydalanuvchi matnini xavfsiz HTML ga (qatorlarini saqlab) aylantiradi."""
    return nl2br(html.escape(text or ""))
