from app.db.database import database_engine_options, normalize_database_url


def test_sqlite_engine_options_keep_thread_check_disabled():
    assert database_engine_options("sqlite:///./data/reservations.db") == {
        "connect_args": {"check_same_thread": False}
    }


def test_postgres_engine_options_check_and_recycle_idle_connections():
    assert database_engine_options("postgresql+psycopg://user:pass@host/db") == {
        "pool_pre_ping": True,
        "pool_recycle": 240,
    }


def test_other_database_urls_have_no_engine_overrides():
    assert database_engine_options("mysql+pymysql://user:pass@host/db") == {}


def test_neon_postgres_url_selects_psycopg_three():
    assert normalize_database_url("postgresql://user:pass@host/db") == (
        "postgresql+psycopg://user:pass@host/db"
    )
