"""Admin panel: umumiy router, FSM holatlari va bosh menyu klaviaturasi."""
import logging
from aiogram import Router

logger = logging.getLogger(__name__)
from aiogram.fsm.state import StatesGroup, State
from aiogram.utils.keyboard import InlineKeyboardBuilder
try:
    from sulguk import SULGUK_PARSE_MODE
except ImportError:
    SULGUK_PARSE_MODE = "sulguk"


admin_router = Router(name="admin")

PAGE_SIZE = 5


class AdminBlockState(StatesGroup):
    waiting_for_user_id = State()
    waiting_for_reason = State()

class AdminAddLawyerState(StatesGroup):
    waiting_for_user_id = State()
    waiting_for_name = State()
    waiting_for_details = State()

class AdminCrmState(StatesGroup):
    waiting_for_link = State()
    waiting_for_cancel_reason = State()

class AdminBroadcastState(StatesGroup):
    waiting_for_message = State()
    waiting_for_button_text = State()
    waiting_for_button_url = State()

class AdminAddChannelState(StatesGroup):
    waiting_for_channel = State()
    waiting_for_language = State()

class AdminAddBenefitState(StatesGroup):
    waiting_for_category = State()
    waiting_for_group = State()
    waiting_for_title = State()
    waiting_for_desc = State()
    waiting_for_legal = State()
    waiting_for_org = State()

class AdminEditBenefitState(StatesGroup):
    waiting_for_value = State()

class AdminManageState(StatesGroup):
    waiting_for_admin_id = State()

class AdminReportCustomState(StatesGroup):
    waiting_for_date_range = State()

def get_admin_menu_keyboard(blocked_count: int = 0, channels_count: int = 0, benefits_count: int = 0):
    builder = InlineKeyboardBuilder()
    builder.button(
        text="📊 Tahliliy hisobot (.xlsx)",
        callback_data="admin:report_menu"
    )
    builder.button(
        text=f"Imtiyozlar boshqaruvi ({benefits_count})",
        callback_data="admin:benefits_page:1"
    )
    builder.button(
        text=f"📢 Kanallar ({channels_count})",
        callback_data="admin:channels_menu"
    )
    builder.button(
        text="📢 Broadcast",
        callback_data="admin:broadcast_menu"
    )
    builder.button(
        text="📅 Qabullar CRM va Taqvimi",
        callback_data="admin:crm_appointments"
    )
    builder.button(
        text="📊 Mutaxassislar statistikasi & KPI",
        callback_data="admin:staff_stats"
    )
    builder.button(
        text="👨‍⚖️ Yurist boshqaruvi",
        callback_data="admin:lawyers_list"
    )
    builder.button(
        text="👥 Adminlar boshqaruvi",
        callback_data="admin:admins_list"
    )
    builder.button(
        text="📋 Biriktirishlar paneli",
        callback_data="admin:asg_panel"
    )
    builder.button(
        text="🤖 Avtomatik javob sohalari",
        callback_data="admin:ai_sections"
    )
    builder.button(
        text=f"🚫 Bloklanganlar ro'yxati ({blocked_count})",
        callback_data="admin:blocked_page:1"
    )
    builder.button(
        text="➕ Foydalanuvchini bloklash (ID orqali)",
        callback_data="admin:block_start"
    )
    builder.adjust(1)
    return builder.as_markup()
