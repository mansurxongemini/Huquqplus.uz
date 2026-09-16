import asyncio
import logging
from datetime import datetime
from aiogram.exceptions import TelegramRetryAfter, TelegramForbiddenError, TelegramBadRequest, TelegramAPIError
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from sqlmodel import Session, select, func
from sulguk import SULGUK_PARSE_MODE

from src.config.bot import bot
from src.config.celery_app import celery_app
from src.database.mysql import engine
from src.database.redisdb import get_redis
from src.models.broadcast import Broadcast, BroadcastStatus
from src.models.user import User
from src.tasks.utils import async_celery_task

logger = logging.getLogger(__name__)

BATCH_SIZE = 500
RATE_LIMIT_DELAY = 0.035  # ~28 messages per second to safely stay under Telegram's 30/s limit


@async_celery_task(celery_app, name="execute_broadcast")
async def execute_broadcast(broadcast_id: int):
    """
    High-throughput, safe, paginated mass-broadcaster for 100,000+ users.
    Runs asynchronously in Celery background without blocking the bot.
    """
    redis_client = get_redis(is_async=True)

    admin_id = None
    started_at = None
    total_target = 0
    sent_count = 0
    blocked_count = 0
    failed_count = 0

    try:
        with Session(engine) as session:
            broadcast = session.get(Broadcast, broadcast_id)
            if not broadcast or broadcast.status in [BroadcastStatus.completed, BroadcastStatus.cancelled]:
                logger.warning("Broadcast %s already finished or not found.", broadcast_id)
                return

            broadcast.status = BroadcastStatus.running
            broadcast.started_at = datetime.now()
            session.add(broadcast)
            session.commit()
            session.refresh(broadcast)

            # Extract all needed values into local primitive variables while in session
            from_chat_id = broadcast.from_chat_id
            message_id = broadcast.message_id
            button_text = broadcast.button_text
            button_url = broadcast.button_url
            admin_id = broadcast.admin_id
            started_at = broadcast.started_at
            f = broadcast.target_filter

            # 1. Build query filters
            query = select(User.user_id).where(User.is_blocked == False)

            if f == "lang_uz":
                query = query.where(User.language == "uz")
            elif f == "lang_ru":
                query = query.where(User.language == "ru")
            elif f and f.startswith("region:"):
                region_name = f.split(":", 1)[1]
                query = query.where(User.region == region_name)
            elif f and f.startswith("disability:"):
                disability_type = f.split(":", 1)[1]
                query = query.where(User.disability_type == disability_type)

            # Count total recipients
            count_query = select(func.count(User.id)).where(User.is_blocked == False)
            if f == "lang_uz":
                count_query = count_query.where(User.language == "uz")
            elif f == "lang_ru":
                count_query = count_query.where(User.language == "ru")
            elif f and f.startswith("region:"):
                region_name = f.split(":", 1)[1]
                count_query = count_query.where(User.region == region_name)
            elif f and f.startswith("disability:"):
                disability_type = f.split(":", 1)[1]
                count_query = count_query.where(User.disability_type == disability_type)

            total_target = session.exec(count_query).one()
            broadcast.total_target = total_target
            session.add(broadcast)
            session.commit()

        # 2. Build inline reply markup if button provided
        reply_markup = None
        if button_text and button_url:
            reply_markup = InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text=button_text, url=button_url)]]
            )

        # 3. Process recipients in batches
        offset = 0
        is_cancelled = False

        logger.info("Starting broadcast %s to %s users...", broadcast_id, total_target)

        # Initial live stats
        try:
            await redis_client.hset(
                f"broadcast:{broadcast_id}:live",
                mapping={
                    "sent": 0,
                    "blocked": 0,
                    "failed": 0,
                    "total": total_target,
                    "processed": 0
                }
            )
        except Exception:
            pass

        while True:
            # Check cancellation signal in Redis
            try:
                cancel_val = await redis_client.get(f"broadcast:{broadcast_id}:cancel")
                if cancel_val:
                    is_cancelled = True
                    logger.info("Broadcast %s was cancelled by admin.", broadcast_id)
                    break
            except Exception:
                pass

            with Session(engine) as session:
                batch_users = session.exec(query.offset(offset).limit(BATCH_SIZE)).all()

            if not batch_users:
                break

            for user_id in batch_users:
                # Check cancellation periodically
                if (sent_count + blocked_count + failed_count) % 50 == 0:
                    try:
                        if await redis_client.get(f"broadcast:{broadcast_id}:cancel"):
                            is_cancelled = True
                            break
                    except Exception:
                        pass

                sent_ok = False
                for retry in range(3):
                    try:
                        await bot.copy_message(
                            chat_id=user_id,
                            from_chat_id=from_chat_id,
                            message_id=message_id,
                            reply_markup=reply_markup
                        )
                        sent_ok = True
                        sent_count += 1
                        break
                    except TelegramRetryAfter as e:
                        logger.warning("Telegram flood limit! Sleeping for %s seconds", e.retry_after)
                        await asyncio.sleep(e.retry_after + 0.5)
                    except TelegramForbiddenError:
                        # User blocked the bot
                        blocked_count += 1
                        # Mark user as blocked in DB
                        try:
                            with Session(engine) as update_session:
                                u = update_session.exec(select(User).where(User.user_id == user_id)).first()
                                if u:
                                    u.is_blocked = True
                                    u.block_reason = "Botni bloklagan (Broadcast orqali aniqlandi)"
                                    update_session.add(u)
                                    update_session.commit()
                        except Exception:
                            pass
                        break
                    except TelegramBadRequest as e:
                        logger.debug("Bad request for user %s: %s", user_id, e)
                        failed_count += 1
                        break
                    except TelegramAPIError as e:
                        logger.error("API error for user %s: %s", user_id, e)
                        failed_count += 1
                        break
                    except Exception as e:
                        logger.error("Unexpected error for user %s: %s", user_id, e)
                        failed_count += 1
                        break

                # Rate limit delay (~28 msg/sec)
                await asyncio.sleep(RATE_LIMIT_DELAY)

                # Update live stats in Redis
                total_processed = sent_count + blocked_count + failed_count
                if total_processed % 50 == 0 or total_processed == total_target:
                    try:
                        await redis_client.hset(
                            f"broadcast:{broadcast_id}:live",
                            mapping={
                                "sent": sent_count,
                                "blocked": blocked_count,
                                "failed": failed_count,
                                "total": total_target,
                                "processed": total_processed
                            }
                        )
                    except Exception:
                        pass

            if is_cancelled:
                break

            offset += BATCH_SIZE

        # 4. Finalize broadcast in database
        end_time = datetime.now()
        final_status = BroadcastStatus.cancelled if is_cancelled else BroadcastStatus.completed

        with Session(engine) as session:
            b_final = session.get(Broadcast, broadcast_id)
            if b_final:
                b_final.status = final_status
                b_final.sent_count = sent_count
                b_final.blocked_count = blocked_count
                b_final.failed_count = failed_count
                b_final.completed_at = end_time
                session.add(b_final)
                session.commit()

        # Clear Redis live key
        try:
            await redis_client.delete(f"broadcast:{broadcast_id}:live")
            await redis_client.delete(f"broadcast:{broadcast_id}:cancel")
        except Exception:
            pass

        # 5. Send completion report to the admin
        if admin_id:
            duration = end_time - (started_at or end_time)
            minutes = int(duration.total_seconds() // 60)
            seconds = int(duration.total_seconds() % 60)
            duration_str = f"{minutes} daqiqa {seconds} soniya"

            status_word = "bekor qilindi" if is_cancelled else "yakunlandi"
            report_text = f"""
🏁 <b>Ommaviy xabar (Broadcast) {status_word}!</b>
━━━━━━━━━━━━━━━━━━━━━
📊 Jami mo'ljallangan: <b>{total_target}</b> ta
✅ Muvaffaqiyatli yetkazildi: <b>{sent_count}</b> ta
🚫 Botni bloklaganlar: <b>{blocked_count}</b> ta
⚠️ Xatolik bilan yetkazilmadi: <b>{failed_count}</b> ta
⏱ Sarflangan vaqt: <b>{duration_str}</b>
━━━━━━━━━━━━━━━━━━━━━
"""
            try:
                await bot.send_message(
                    chat_id=admin_id,
                    text=report_text,
                    parse_mode=SULGUK_PARSE_MODE
                )
            except Exception as e:
                logger.error("Failed to send broadcast report to admin: %s", e)

    except Exception as exc:
        logger.error("Critical error in broadcast %s: %s", broadcast_id, exc, exc_info=True)
        try:
            with Session(engine) as session:
                b_err = session.get(Broadcast, broadcast_id)
                if b_err:
                    b_err.status = BroadcastStatus.cancelled
                    b_err.completed_at = datetime.now()
                    session.add(b_err)
                    session.commit()
        except Exception:
            pass

        if admin_id:
            try:
                await bot.send_message(
                    chat_id=admin_id,
                    text=f"❌ <b>Broadcast №{broadcast_id} da xatolik yuz berdi:</b><br/><code>{exc}</code>",
                    parse_mode=SULGUK_PARSE_MODE
                )
            except Exception:
                pass
        raise
