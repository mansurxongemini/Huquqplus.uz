"""Ishlash holatini kuzatish: sozlamalar tekshiruvi, LLM balansi, xatolar xulosasi — asosiy adminlarga."""
import html
import json
import logging
from collections import Counter
from datetime import datetime

from aiogram import Bot
from aiogram.exceptions import TelegramMigrateToChat
from sulguk import SULGUK_PARSE_MODE

from src.config.settings import settings

logger = logging.getLogger(__name__)

ERRORS_KEY = "bot_errors:{day}"
ERRORS_MAX = 500


def _redis():
    from src.database.redisdb import get_redis
    return get_redis(is_async=False)


async def notify_super_admins(bot: Bot, text: str, dedupe_key: str | None = None, dedupe_seconds: int = 0) -> int:
    """Asosiy adminlarga DM. dedupe_key berilsa, shu muddat ichida takror yuborilmaydi."""
    if dedupe_key:
        try:
            if not _redis().set(f"ops_notice:{dedupe_key}", "1", ex=dedupe_seconds, nx=True):
                return 0
        except Exception:
            pass
    sent = 0
    for admin_id in settings.super_admin_ids_list:
        try:
            await bot.send_message(chat_id=admin_id, text=text, parse_mode=SULGUK_PARSE_MODE)
            sent += 1
        except Exception as e:
            logger.warning("Admin %s ga xabar yuborilmadi: %s", admin_id, type(e).__name__)
    return sent


def _configured_groups() -> dict[str, str]:
    groups: dict[str, str] = {}
    for section, gid in settings.get_inquiry_groups().items():
        if gid:
            groups.setdefault(str(gid), section)
    if settings.LAWYER_APPOINTMENT_GROUP_ID:
        groups.setdefault(str(settings.LAWYER_APPOINTMENT_GROUP_ID), "Yurist qabullari")
    return groups


async def collect_config_issues(bot: Bot) -> list[str]:
    """Guruhlar superguruhmi, bot ularda xabar o'chira oladigan adminmi, RAG ulanganmi."""
    issues: list[str] = []
    for gid, label in _configured_groups().items():
        try:
            chat = await bot.get_chat(gid)
        except TelegramMigrateToChat as e:
            issues.append(f"«{label}» ({gid}) superguruhga ko'chgan, yangi ID: <code>{e.migrate_to_chat_id}</code> — .env ni yangilang")
            continue
        except Exception as e:
            issues.append(f"«{label}» ({gid}) guruhiga ulanib bo'lmadi: {html.escape(type(e).__name__)}")
            continue
        if chat.type != "supergroup":
            issues.append(f"«{label}» ({gid}) oddiy guruh: xabar havolalari ishlamaydi, superguruhga aylantiring")
        try:
            me = await bot.get_chat_member(gid, bot.id)
            if me.status != "administrator":
                issues.append(f"«{label}»: bot admin emas — ruxsatsiz javoblarni o'chira olmaydi")
            elif not getattr(me, "can_delete_messages", False):
                issues.append(f"«{label}»: botda xabar o'chirish huquqi yo'q")
        except Exception as e:
            issues.append(f"«{label}»: bot huquqlarini tekshirib bo'lmadi ({html.escape(type(e).__name__)})")
    from src.app.rag_client import rag_client
    if not rag_client.is_configured():
        issues.append("RAG ulanmagan (RAG_API_URL/RAG_API_KEY): javob tekshiruvi va avtomatik javob ishlamaydi")
    return issues


async def run_startup_checks(bot: Bot) -> None:
    try:
        issues = await collect_config_issues(bot)
    except Exception as e:
        logger.warning("Ishga tushish tekshiruvi bajarilmadi: %s", e)
        return
    if not issues:
        logger.info("Ishga tushish tekshiruvi: muammo yo'q")
        return
    for issue in issues:
        logger.error("Sozlama muammosi: %s", issue)
    text = "⚙️ <b>Bot ishga tushdi, sozlamalarda muammo bor:</b><br/>" + "<br/>".join(f"• {i}" for i in issues)
    await notify_super_admins(bot, text, dedupe_key="startup_issues", dedupe_seconds=6 * 3600)


async def check_llm_balance(bot: Bot) -> dict | None:
    """Balans tugagan/kam bo'lsa asosiy adminlarga ogohlantirish (12 soatda ko'pi bilan bir marta)."""
    from src.app.rag_client import rag_client
    if not rag_client.is_configured():
        return None
    try:
        status = (await rag_client.status()).get("llm") or {}
    except Exception as e:
        logger.warning("LLM holatini olib bo'lmadi: %s", e)
        return None
    remaining = status.get("credits_remaining")
    low = remaining is not None and remaining < settings.AI_BALANCE_ALERT_USD
    if status.get("ok") and not low:
        return status
    if status.get("error") == "insufficient_credits" or (remaining is not None and remaining <= 0):
        reason = "OpenRouter balansi tugadi"
    elif low:
        reason = f"OpenRouter balansi kam qoldi: ${remaining:.2f}"
    else:
        reason = f"LLM xizmati javob bermayapti ({html.escape(str(status.get('error')))})"
    text = (
        f"💳 <b>{reason}</b><br/>Javoblarni tekshirish va avtomatik javob ishlamaydi yoki tez orada to'xtaydi. "
        "Savollar huquqshunoslarga yuborilishda davom etadi.<br/>Balansni to'ldiring: openrouter.ai/settings/credits"
    )
    await notify_super_admins(bot, text, dedupe_key="llm_balance", dedupe_seconds=12 * 3600)
    return status


def record_bot_error(exception: BaseException, where: str = "") -> None:
    """Kutilmagan xatoni kunlik ro'yxatga yozadi (xulosa uchun)."""
    try:
        entry = json.dumps({
            "t": datetime.now().strftime("%H:%M"),
            "type": type(exception).__name__,
            "msg": str(exception)[:200],
            "where": where[:80],
        }, ensure_ascii=False)
        r = _redis()
        key = ERRORS_KEY.format(day=datetime.now().strftime("%Y%m%d"))
        r.rpush(key, entry)
        r.ltrim(key, -ERRORS_MAX, -1)
        r.expire(key, 3 * 86400)
    except Exception:
        pass


def build_error_digest(entries: list[dict], day_label: str) -> str | None:
    if not entries:
        return None
    by_kind = Counter(f"{e.get('type')}: {e.get('msg', '')[:90]}" for e in entries)
    lines = [f"🧾 <b>Bot xatolari xulosasi ({day_label})</b> — jami {len(entries)} ta:"]
    for text, n in by_kind.most_common(10):
        lines.append(f"• {n} ×  {html.escape(text)}")
    if len(by_kind) > 10:
        lines.append(f"… yana {len(by_kind) - 10} xil xato")
    return "<br/>".join(lines)


async def send_error_digest(bot: Bot, day: datetime) -> bool:
    key = ERRORS_KEY.format(day=day.strftime("%Y%m%d"))
    try:
        raw = _redis().lrange(key, 0, -1)
    except Exception:
        return False
    entries = []
    for item in raw:
        try:
            entries.append(json.loads(item.decode() if isinstance(item, bytes) else item))
        except ValueError:
            continue
    text = build_error_digest(entries, day.strftime("%d.%m.%Y"))
    if not text:
        return False
    await notify_super_admins(bot, text)
    return True


# -- Darvoza rad etgan guruh javoblari: haftalik xulosa ---------------------------------------------------

GATE_KEY = "gate_denials:{week}"
GATE_NAMES_KEY = "gate_denial_names"


def _week_id(day: datetime) -> str:
    year, week, _ = day.isocalendar()
    return f"{year}w{week:02d}"


def record_gate_denial(user_id: int, full_name: str, reason: str) -> None:
    """Ruxsatsiz/tasdiqlanmagan guruh javobini haftalik hisobga yozadi."""
    try:
        r = _redis()
        key = GATE_KEY.format(week=_week_id(datetime.now()))
        r.hincrby(key, f"{user_id}|{reason}", 1)
        r.expire(key, 21 * 86400)
        r.hset(GATE_NAMES_KEY, str(user_id), full_name[:80])
    except Exception:
        pass


GATE_REASONS = {
    "unassigned": "biriktirilmagan murojaatga",
    "foreign": "boshqaga biriktirilgan murojaatga",
    "no_review": "tekshiruvsiz",
    "changed": "tasdiqlangandan keyin o'zgartirilgan matn bilan",
}


def build_gate_summary(counts: dict[str, int], names: dict[str, str], week_label: str) -> str | None:
    if not counts:
        return None
    per_user: dict[str, Counter] = {}
    for field, n in counts.items():
        uid, _, reason = field.partition("|")
        per_user.setdefault(uid, Counter())[reason] += int(n)
    ordered = sorted(per_user.items(), key=lambda kv: -sum(kv[1].values()))
    lines = [f"🚧 <b>Qoidaga zid guruh javoblari ({week_label})</b> — o'chirilgan va volontyorga tushuntirilgan:"]
    for uid, reasons in ordered[:15]:
        name = html.escape(names.get(uid) or uid)
        detail = ", ".join(f"{GATE_REASONS.get(k, k)} — {v}" for k, v in reasons.most_common())
        lines.append(f'• <a href="tg://user?id={uid}">{name}</a>: {sum(reasons.values())} ta ({detail})')
    return "<br/>".join(lines)


async def send_weekly_gate_summary(bot: Bot, day_in_week: datetime) -> bool:
    try:
        r = _redis()
        raw = r.hgetall(GATE_KEY.format(week=_week_id(day_in_week)))
        names_raw = r.hgetall(GATE_NAMES_KEY)
    except Exception:
        return False
    dec = lambda v: v.decode() if isinstance(v, bytes) else v  # noqa: E731
    counts = {dec(k): int(dec(v)) for k, v in raw.items()}
    names = {dec(k): dec(v) for k, v in names_raw.items()}
    text = build_gate_summary(counts, names, _week_id(day_in_week))
    if not text:
        return False
    await notify_super_admins(bot, text)
    return True
