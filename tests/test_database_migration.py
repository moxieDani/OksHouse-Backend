from datetime import date

import pytest
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.orm import Session

from app.db.database import Base
from app.db.migration import migrate_database
from app.models.admin import Admin
from app.models.fcm import FCMToken
from app.models.reservation import Reservation


def _engine(path):
    return create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})


def test_migrate_database_preserves_all_rows_and_primary_keys(tmp_path):
    source = _engine(tmp_path / "source.db")
    target = _engine(tmp_path / "target.db")
    Base.metadata.create_all(source)
    # The Fly SQLite database predates the persistent session table.
    with source.begin() as connection:
        connection.execute(text("DROP TABLE admin_sessions"))

    with Session(source) as session:
        session.add(Admin(admin_id=7, name="관리자", phone="010-0000-0000"))
        session.add(
            Reservation(
                id=42,
                name="예약자",
                phone="010-1111-1111",
                start_date=date(2027, 1, 2),
                end_date=date(2027, 1, 4),
                duration=2,
                password="encrypted-value",
                status="confirmed",
                confirmed_by="관리자",
            )
        )
        session.add(FCMToken(id=88, admin_id=7, fcm_token="test-token"))
        session.commit()

    result = migrate_database(source, target)

    assert result["admins"]["rows"] == 1
    assert result["reservations"]["rows"] == 1
    assert result["fcm_tokens"]["rows"] == 1
    assert result["admin_sessions"]["rows"] == 0
    assert all(len(table["sha256"]) == 64 for table in result.values())

    with Session(target) as session:
        reservation = session.scalar(select(Reservation).where(Reservation.id == 42))
        assert reservation is not None
        assert reservation.start_date == date(2027, 1, 2)
        assert reservation.password == "encrypted-value"
        assert session.get(Admin, 7).name == "관리자"
        assert session.get(FCMToken, 88).fcm_token == "test-token"
    assert "admin_sessions" in inspect(target).get_table_names()


def test_migrate_database_refuses_to_overwrite_nonempty_target(tmp_path):
    source = _engine(tmp_path / "source.db")
    target = _engine(tmp_path / "target.db")
    Base.metadata.create_all(source)
    Base.metadata.create_all(target)
    with Session(target) as session:
        session.add(Admin(admin_id=1, name="Existing target row"))
        session.commit()

    with pytest.raises(ValueError, match="not empty"):
        migrate_database(source, target)

    with Session(target) as session:
        assert session.scalar(select(Admin.admin_id)) == 1
