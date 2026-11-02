import os
from typing import AsyncGenerator
import asyncio
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from app.core.config import settings

# Base class for models
Base = declarative_base()

# Import all models here so that Base has them registered
from app.models.admin import Admin
from app.models.reservation import Reservation
from app.models.fcm import FCMToken
from app.models.admin_session import AdminSession

# Database directory setup for local SQLite
if settings.database_url.startswith("sqlite"):
    # URL에서 경로 부분 추출 (e.g., sqlite:///./data/reservations.db -> ./data/reservations.db)
    db_path = settings.database_url.split(":///")[1]
    # 경로에서 디렉토리 부분 추출
    db_dir = os.path.dirname(db_path)
    # 디렉토리가 존재하지 않으면 생성
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)


def database_engine_options(database_url: str) -> dict:
    """Return connection options for the configured database backend."""
    if database_url.startswith("sqlite"):
        return {"connect_args": {"check_same_thread": False}}
    if database_url.startswith("postgresql"):
        # Neon suspends idle computes; validate pooled connections and recycle
        # them before its default five-minute scale-to-zero interval.
        return {"pool_pre_ping": True, "pool_recycle": 240}
    return {}


def normalize_database_url(database_url: str) -> str:
    """Use the installed psycopg 3 driver for standard Neon PostgreSQL URLs."""
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    return database_url


# Database engine
engine = create_engine(
    normalize_database_url(settings.database_url),
    **database_engine_options(settings.database_url),
)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


async def get_async_db() -> AsyncGenerator[Session, None]:
    """Async database dependency using asyncio"""
    loop = asyncio.get_event_loop()
    
    def get_sync_db():
        db = SessionLocal()
        try:
            return db
        except Exception as e:
            db.close()
            raise e
    
    # Run sync database operations in thread pool
    db = await loop.run_in_executor(None, get_sync_db)
    try:
        yield db
    finally:
        await loop.run_in_executor(None, db.close)


async def create_tables():
    """Create all tables asynchronously"""
    loop = asyncio.get_event_loop()
    
    def sync_create_tables():
        Base.metadata.create_all(bind=engine)
    
    await loop.run_in_executor(None, sync_create_tables)


async def init_admin_data():
    """Initialize admin data if not exists"""
    loop = asyncio.get_event_loop()
    
    def sync_init_admin_data():
        from app.models.admin import Admin
        
        db = SessionLocal()
        try:
            # 관리자 데이터가 이미 존재하는지 확인
            existing_admins = db.query(Admin).first()
            if existing_admins:
                return  # 이미 데이터가 있으면 초기화하지 않음
            
            # 초기 관리자 데이터 삽입
            initial_admins = [
                Admin(admin_id=1, name="최분옥", phone="010-7102-2552"),
                Admin(admin_id=2, name="최창환", phone="010-4872-3713"),
                Admin(admin_id=3, name="박서은", phone="010-2060-2552"),
                Admin(admin_id=4, name="박지영", phone="010-4022-2552"),
                Admin(admin_id=5, name="박태현", phone="010-3794-3420"),
            ]
            
            for admin in initial_admins:
                db.add(admin)
            
            db.commit()
        except Exception as e:
            db.rollback()
            raise e
        finally:
            db.close()
    
    await loop.run_in_executor(None, sync_init_admin_data)
