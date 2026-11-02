import asyncio
from typing import Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.models.admin import Admin
from app.models.admin_session import AdminSession
from app.schemas.auth import AdminPhoneRequest, TokenResponse, AdminInfo
from app.core.security import (
    create_access_token, 
    create_refresh_token,
    verify_token,
)


class AuthService:
    """관리자 인증 서비스"""

    @staticmethod
    async def verify_admin_phone(db: Session, phone_request: AdminPhoneRequest) -> TokenResponse:
        """관리자 전화번호 인증 및 토큰 발급"""
        loop = asyncio.get_event_loop()
        
        def sync_verify_phone():
            # 전화번호로 관리자 조회
            admin = db.query(Admin).filter(Admin.phone == phone_request.phone).first()
            
            if not admin:
                raise HTTPException(
                    status_code=401, 
                    detail="등록되지 않은 관리자 전화번호입니다"
                )
            
            # 세션에 관리자 추가
            AuthService.add_admin_session(db, admin.admin_id)
            
            # 토큰 생성
            access_token = create_access_token(admin.admin_id, admin.name)
            refresh_token = create_refresh_token(admin.admin_id, admin.name)
            
            return {
                "admin": admin,
                "access_token": access_token,
                "refresh_token": refresh_token
            }
        
        result = await loop.run_in_executor(None, sync_verify_phone)
        
        # 리프레시 토큰 만료까지 남은 시간 (새로 생성된 토큰이므로 전체 기간)
        from app.core.security import REFRESH_TOKEN_EXPIRE_SECONDS
        
        return TokenResponse(
            access_token=result["access_token"],
            admin_id=result["admin"].admin_id,
            admin_name=result["admin"].name,
            refresh_token_renewed=True,
            refresh_token_expires_in=REFRESH_TOKEN_EXPIRE_SECONDS
        ), result["refresh_token"]

    @staticmethod
    async def refresh_access_token(db: Session, refresh_token: str) -> TokenResponse:
        """리프레시 토큰으로 액세스 토큰 갱신"""
        loop = asyncio.get_event_loop()
        
        def sync_refresh_token():
            import time
            from app.core.security import REFRESH_TOKEN_EXPIRE_SECONDS
            
            # 리프레시 토큰 검증
            token_data = verify_token(refresh_token)
            
            if token_data["type"] != "refresh":
                raise HTTPException(status_code=401, detail="리프레시 토큰이 아닙니다")
            
            admin_id = token_data["admin_id"]
            admin_name = token_data["admin_name"]
            
            # 세션 유효성 확인
            if not AuthService.is_admin_session_valid(db, admin_id):
                raise HTTPException(status_code=401, detail="관리자 세션이 만료되었습니다")
            
            # 관리자 존재 확인
            admin = db.query(Admin).filter(Admin.admin_id == admin_id).first()
            if not admin:
                raise HTTPException(status_code=401, detail="존재하지 않는 관리자입니다")
            
            # 리프레시 토큰 만료 시간 체크
            exp_timestamp = token_data.get("exp", 0)
            current_timestamp = int(time.time())
            time_until_expiration = exp_timestamp - current_timestamp
            
            # 24시간(86400초) 내에 만료되는 경우 새 리프레시 토큰 발급
            should_renew_refresh = time_until_expiration <= (24 * 60 * 60)
            
            # 새 액세스 토큰 생성 (항상)
            new_access_token = create_access_token(admin_id, admin_name)
            
            # 조건에 따라 새 리프레시 토큰 생성
            if should_renew_refresh:
                new_refresh_token = create_refresh_token(admin_id, admin_name)
                refresh_token_expires_in = REFRESH_TOKEN_EXPIRE_SECONDS
            else:
                new_refresh_token = refresh_token  # 기존 리프레시 토큰 유지
                refresh_token_expires_in = time_until_expiration
            
            return {
                "access_token": new_access_token,
                "refresh_token": new_refresh_token,
                "admin_id": admin_id,
                "admin_name": admin_name,
                "refresh_token_renewed": should_renew_refresh,
                "refresh_token_expires_in": refresh_token_expires_in
            }
        
        result = await loop.run_in_executor(None, sync_refresh_token)
        
        return TokenResponse(
            access_token=result["access_token"],
            admin_id=result["admin_id"], 
            admin_name=result["admin_name"],
            refresh_token_renewed=result["refresh_token_renewed"],
            refresh_token_expires_in=result["refresh_token_expires_in"]
        ), result["refresh_token"]

    @staticmethod
    async def get_current_admin(db: Session, access_token: str) -> AdminInfo:
        """현재 인증된 관리자 정보 조회"""
        loop = asyncio.get_event_loop()
        
        def sync_get_admin():
            # 액세스 토큰 검증
            token_data = verify_token(access_token)
            
            if token_data["type"] != "access":
                raise HTTPException(status_code=401, detail="액세스 토큰이 아닙니다")
            
            admin_id = token_data["admin_id"]
            
            # 세션 유효성 확인
            if not AuthService.is_admin_session_valid(db, admin_id):
                raise HTTPException(status_code=401, detail="관리자 세션이 만료되었습니다")
            
            # 관리자 정보 조회
            admin = db.query(Admin).filter(Admin.admin_id == admin_id).first()
            if not admin:
                raise HTTPException(status_code=401, detail="존재하지 않는 관리자입니다")
            
            return admin
        
        admin = await loop.run_in_executor(None, sync_get_admin)
        
        return AdminInfo(
            admin_id=admin.admin_id,
            name=admin.name,
            phone=admin.phone
        )

    @staticmethod
    def add_admin_session(db: Session, admin_id: int):
        """Persist an authenticated administrator session."""
        session = db.get(AdminSession, admin_id)
        if session is None:
            db.add(AdminSession(admin_id=admin_id))
        db.commit()

    @staticmethod
    def is_admin_session_valid(db: Session, admin_id: int) -> bool:
        """Check the shared database for an authenticated administrator."""
        return db.get(AdminSession, admin_id) is not None

    @staticmethod
    def logout_admin(db: Session, admin_id: int):
        """관리자 로그아웃 (세션 제거)"""
        session = db.get(AdminSession, admin_id)
        if session is not None:
            db.delete(session)
            db.commit()
