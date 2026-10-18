# Barcha modellar ro'yxati: alembic/env.py shu moduldan `import *` qiladi. Importlarni o'chirmang.
from src.models.base import BaseModel
from src.models.user import User
from src.models.inquiry import Inquiry
from src.models.lawyer import OfficialLawyer
from src.models.appointment import Appointment
from src.models.broadcast import Broadcast
from src.models.volunteer import Volunteer
from src.models.required_channel import RequiredChannel
from src.models.benefit import Benefit
from src.models.assignment import VolunteerSection, InquiryAssignment, ReviewAttempt
from src.models.bot_admin import BotAdmin
from src.models.ai_answer import AiAnswer, AiSectionSetting

__all__ = [
    "BaseModel", "User", "Inquiry", "OfficialLawyer", "Appointment", "Broadcast", "Volunteer",
    "RequiredChannel", "Benefit", "VolunteerSection", "InquiryAssignment", "ReviewAttempt", "BotAdmin", "AiAnswer", "AiSectionSetting",
]
