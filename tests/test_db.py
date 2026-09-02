from app.models.base import _engine_kwargs


def test_sqlite_url_uses_check_same_thread() -> None:
    kwargs = _engine_kwargs("sqlite:///./data/db.sqlite")
    assert kwargs == {"connect_args": {"check_same_thread": False}}


def test_postgres_url_has_no_sqlite_connect_args() -> None:
    kwargs = _engine_kwargs("postgresql+psycopg://user:pass@host:5432/db")
    assert kwargs == {}


def test_postgres_url_has_no_check_same_thread() -> None:
    kwargs = _engine_kwargs("postgresql+psycopg://user:pass@host:5432/db")
    assert "check_same_thread" not in kwargs
