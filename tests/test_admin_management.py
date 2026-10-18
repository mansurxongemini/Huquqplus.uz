from src.app import admin_registry
from src.config.settings import settings
from src.routes.aiogram.admin import _parse_telegram_id


def test_parse_telegram_id():
    assert _parse_telegram_id("123456789") == 123456789
    assert _parse_telegram_id(" 8954778334 ") == 8954778334
    for bad in ("", "abc", "-100123456", "12", "12.5", "1" * 16, "0000000"):
        assert _parse_telegram_id(bad) is None


def test_is_admin_combines_env_and_db(monkeypatch):
    monkeypatch.setattr(settings, "ADMIN_IDS", "111,222")
    monkeypatch.setattr(admin_registry, "get_db_admin_ids", lambda: frozenset({333}))
    assert settings.is_admin(111) and settings.is_admin(333)
    assert not settings.is_admin(444)
    # faqat .env dagilar asosiy admin
    assert settings.is_super_admin(222)
    assert not settings.is_super_admin(333)
    assert settings.admin_ids_list == [111, 222, 333]


def test_db_failure_falls_back_to_env_only(monkeypatch):
    monkeypatch.setattr(settings, "ADMIN_IDS", "111")
    monkeypatch.setattr(admin_registry, "_cache", {"ids": frozenset(), "expires": 0.0})

    import src.database.mysql as mysql

    class Boom:
        def __enter__(self):
            raise RuntimeError("db down")

        def __exit__(self, *a):
            return False

    monkeypatch.setattr("sqlmodel.Session", lambda engine: Boom())
    assert admin_registry.get_db_admin_ids() == frozenset()
    assert settings.is_admin(111)
    assert not settings.is_admin(999)
