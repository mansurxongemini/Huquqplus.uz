import logging
from datetime import datetime
from sulguk import SULGUK_PARSE_MODE

from src.config.bot import bot
from src.config.celery_app import celery_app
from src.config.settings import settings
from src.app.volunteer_analytics import get_month_date_range, calculate_volunteer_stats, get_top_volunteers_with_ties
from src.tasks.utils import async_celery_task

logger = logging.getLogger(__name__)


@async_celery_task(celery_app, name="post_weekly_volunteer_leaderboard")
async def post_weekly_volunteer_leaderboard():
    """
    Weekly Celery task running every Sunday at 16:00 (Tashkent time).
    Posts the Top 5 volunteers (with ties included) for the current month
    to the designated volunteer Telegram group (VOLUNTEER_GROUP_ID).
    """
    group_id = settings.VOLUNTEER_GROUP_ID
    if not group_id:
        logger.warning("VOLUNTEER_GROUP_ID is not configured. Skipping weekly leaderboard.")
        return

    now = datetime.now()
    start_date, _ = get_month_date_range(now)
    date_range = (start_date, now)

    # Calculate statistics for registered volunteers in the current month
    vol_stats = calculate_volunteer_stats(date_range=date_range, volunteers_only=True)

    # Filter out those with 0 answers in this month
    active_in_month = [v for v in vol_stats if v["inquiries_count"] > 0]
    top_volunteers = get_top_volunteers_with_ties(active_in_month, top_limit=5)

    month_names = {
        1: "Yanvar", 2: "Fevral", 3: "Mart", 4: "Aprel",
        5: "May", 6: "Iyun", 7: "Iyul", 8: "Avgust",
        9: "Sentabr", 10: "Oktabr", 11: "Noyabr", 12: "Dekabr"
    }
    month_title = month_names.get(now.month, "")

    header = f"""
🏆 <b>HAFTALIK VOLONTYORLAR REYTINGI ({month_title.upper()} OYI)</b>
📅 <b>Davr:</b> 01.{now.month:02d}.{now.year} — {now.day:02d}.{now.month:02d}.{now.year}
━━━━━━━━━━━━━━━━━━━━━
"""

    if not top_volunteers:
        body = "<i>Joriy oyda hozircha volontyorlar tomonidan javoblar qayd etilmagan.</i>\n"
    else:
        rank_emojis = {1: "🥇", 2: "🥈", 3: "🥉", 4: "🎖", 5: "🎖"}
        lines = []
        for v in top_volunteers:
            rank_num = v.get("rank", 1)
            emoji = rank_emojis.get(rank_num, "🎖")
            rating_str = f"⭐ {v['avg_rating']}" if v['avg_rating'] > 0 else "baho yo'q"

            block = (
                f"{emoji} <b>{rank_num}-o'rin: {v['name']}</b>\n"
                f"• 🎯 <b>KPI Ball:</b> <b>{v['kpi_score']}</b> ball\n"
                f"• 📩 <b>Javob berilgan savollar:</b> {v['inquiries_count']} ta\n"
                f"• ⭐️ <b>O'rtacha baho:</b> {rating_str}\n"
                f"• ⚡️ <b>O'rtacha javob tezligi:</b> {v['avg_response_str']}\n"
            )
            lines.append(block)
        body = "\n".join(lines)

    footer = """
━━━━━━━━━━━━━━━━━━━━━
👏 <i>Fuqarolarimizga beminnat huquqiy yordam ko'rsatayotgan barcha volontyorlarimizga samimiy minnatdorchilik bildiramiz!</i>
"""

    full_message = f"{header}\n{body}\n{footer}".strip()

    try:
        await bot.send_message(
            chat_id=group_id,
            text=full_message,
            parse_mode=SULGUK_PARSE_MODE
        )
        logger.info("Weekly volunteer leaderboard successfully sent to group %s", group_id)
    except Exception as e:
        logger.error("Failed to post weekly volunteer leaderboard to group %s: %s", group_id, e)
