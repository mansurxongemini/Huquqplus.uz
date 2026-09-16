from sqlmodel import create_engine
from src.config.settings import settings

engine = create_engine(
    settings.database_url + '?charset=utf8mb4',
    pool_size=20,
    max_overflow=20,
    pool_timeout=30,
    pool_recycle=1800,
    pool_pre_ping=True
)

local_engine = create_engine(f"mysql+pymysql://{settings.DB_USER}:{settings.DB_PASSWORD}@localhost:{settings.DB_PORT}/{settings.DB_NAME}")
