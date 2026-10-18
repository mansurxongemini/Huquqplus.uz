"""Admin panel. Bo'limlar alohida modullarda; barchasi bitta `admin_router` ga ulanadi.

Modullar asl tartibda import qilinadi — handlerlar shu tartibda ro'yxatdan o'tadi.
"""
from src.routes.aiogram.admin.common import (  # noqa: F401
    AdminReportCustomState,
    admin_router,
    get_admin_menu_keyboard,
)
from src.routes.aiogram.admin import (  # noqa: F401
    core,
    channels,
    blocking,
    staff,
    reports,
    lawyers,
    crm,
    broadcast,
    benefits,
    admins,
    ai_sections,
    assignments,
)

# boshqa modullar va testlar foydalanadigan nomlar
from src.routes.aiogram.admin.blocking import execute_block_user, execute_unblock_user  # noqa: F401,E402
from src.routes.aiogram.admin.admins import _parse_telegram_id, build_admins_page  # noqa: F401,E402
from src.routes.aiogram.admin.benefits import (  # noqa: F401,E402
    admin_benefit_save_field_value,
    build_admin_benefits_page,
    build_benefit_audience_menu,
    build_benefit_edit_menu,
    sync_benefits_to_json,
)
from src.routes.aiogram.admin.reports import (  # noqa: F401,E402
    admin_report_command,
    admin_report_custom_range_received,
    admin_report_menu_callback,
)
