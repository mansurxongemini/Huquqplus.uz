import socket
from sqlmodel import create_engine
from src.config.settings import settings


def _get_database_url() -> str:
    host = settings.DB_HOST
    try:
        socket.gethostbyname(host)
    except (socket.gaierror, socket.herror):
        host = "127.0.0.1"
    return f"mysql+pymysql://{settings.DB_USER}:{settings.DB_PASSWORD}@{host}:{settings.DB_PORT}/{settings.DB_NAME}?charset=utf8mb4"


engine = create_engine(
    _get_database_url(),
    pool_size=20,
    max_overflow=20,
    pool_timeout=30,
    pool_recycle=1800,
    pool_pre_ping=True
)

local_engine = create_engine(f"mysql+pymysql://{settings.DB_USER}:{settings.DB_PASSWORD}@localhost:{settings.DB_PORT}/{settings.DB_NAME}")
