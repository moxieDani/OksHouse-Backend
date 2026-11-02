from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.database import Base
from app.models.admin import Admin
from app.services.auth_service import AuthService


def test_admin_session_is_shared_between_database_sessions(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'sessions.db'}")
    Base.metadata.create_all(engine)

    with Session(engine) as login_session:
        login_session.add(Admin(admin_id=17, name="Migration Test", phone="010-0000-0000"))
        login_session.commit()
        AuthService.add_admin_session(login_session, 17)

    with Session(engine) as request_session:
        assert AuthService.is_admin_session_valid(request_session, 17)

    with Session(engine) as logout_session:
        AuthService.logout_admin(logout_session, 17)

    with Session(engine) as next_request_session:
        assert not AuthService.is_admin_session_valid(next_request_session, 17)
