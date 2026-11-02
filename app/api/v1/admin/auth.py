from fastapi import APIRouter, Depends, HTTPException, Response, Request, Header
from datetime import datetime, timedelta, timezone
from fastapi.security import HTTPBearer
from sqlalchemy.orm import Session
from typing import Optional
from app.core.config import settings
from app.db.database import get_async_db
from app.schemas.auth import AdminPhoneRequest, TokenResponse, AdminInfo, RefreshTokenRequest
from app.services.auth_service import AuthService
from app.core.security import REFRESH_TOKEN_EXPIRE_SECONDS

router = APIRouter()
security = HTTPBearer(auto_error=False)


@router.post("/verify-phone", response_model=TokenResponse)
async def verify_admin_phone(
    phone_request: AdminPhoneRequest,
    response: Response,
    db: Session = Depends(get_async_db)
):
    """관리자 전화번호 인증 및 토큰 발급"""
    try:
        token_response, refresh_token = await AuthService.verify_admin_phone(db, phone_request)
        
        # HttpOnly 쿠키로 리프레시 토큰 설정 (1년 만료)
        expires = datetime.now(timezone.utc) + timedelta(seconds=REFRESH_TOKEN_EXPIRE_SECONDS)
        
        # 직접 Set-Cookie 헤더 설정 (환경에 따라 SameSite, Secure 속성 분기)
        expires_str = expires.strftime("%a, %d %b %Y %H:%M:%S GMT")
        
        if settings.environment == "production":
            samesite_and_secure = "SameSite=None; Secure"
        else:
            samesite_and_secure = "SameSite=Lax"

        cookie_header = (
            f"admin_refresh_token={refresh_token}; "
            f"Max-Age={REFRESH_TOKEN_EXPIRE_SECONDS}; "
            f"Expires={expires_str}; "
            f"Path=/; "
            f"HttpOnly; "
            f"{samesite_and_secure}"
        )
        
        # 다른 Set-Cookie 헤더와 충돌하지 않도록 append 방식 사용
        if "Set-Cookie" in response.headers:
            # 기존 Set-Cookie가 있으면 추가
            existing_cookies = response.headers["Set-Cookie"]
            response.headers["Set-Cookie"] = f"{existing_cookies}, {cookie_header}"
        else:
            response.headers["Set-Cookie"] = cookie_header
        
        
        return token_response
        
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        import traceback
        print("--- UNEXPECTED ERROR IN /verify-phone ---")
        traceback.print_exc()
        print("-----------------------------------------")
        raise HTTPException(status_code=500, detail="인증 처리 중 오류가 발생했습니다")


@router.post("/refresh", response_model=TokenResponse)
async def refresh_access_token(
    request: Request,
    response: Response,
    refresh_request: RefreshTokenRequest = None,
    db: Session = Depends(get_async_db)
):
    """리프레시 토큰으로 액세스 토큰 갱신"""
    try:
        # 쿠키에서 리프레시 토큰 추출
        refresh_token = request.cookies.get("admin_refresh_token")
        
        # 요청 본문에서도 확인 (fallback)
        if not refresh_token and refresh_request and refresh_request.refresh_token:
            refresh_token = refresh_request.refresh_token
            
        if not refresh_token:
            raise HTTPException(
                status_code=401, 
                detail="리프레시 토큰이 없습니다. 다시 로그인해주세요."
            )
        
        token_response, new_refresh_token = await AuthService.refresh_access_token(db, refresh_token)
        
        # 리프레시 토큰이 갱신된 경우에만 새 쿠키 설정
        if token_response.refresh_token_renewed:
            expires = datetime.now(timezone.utc) + timedelta(seconds=REFRESH_TOKEN_EXPIRE_SECONDS)
            
            # 직접 Set-Cookie 헤더 설정 (환경에 따라 SameSite, Secure 속성 분기)
            expires_str = expires.strftime("%a, %d %b %Y %H:%M:%S GMT")

            if settings.environment == "production":
                samesite_and_secure = "SameSite=None; Secure"
            else:
                samesite_and_secure = "SameSite=Lax"

            cookie_header = (
                f"admin_refresh_token={new_refresh_token}; "
                f"Max-Age={REFRESH_TOKEN_EXPIRE_SECONDS}; "
                f"Expires={expires_str}; "
                f"Path=/; "
                f"HttpOnly; "
                f"{samesite_and_secure}"
            )
            
            # 다른 Set-Cookie 헤더와 충돌하지 않도록 append 방식 사용
            if "Set-Cookie" in response.headers:
                # 기존 Set-Cookie가 있으면 추가
                existing_cookies = response.headers["Set-Cookie"]
                response.headers["Set-Cookie"] = f"{existing_cookies}, {cookie_header}"
            else:
                response.headers["Set-Cookie"] = cookie_header
        
        return token_response
        
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail="토큰 갱신 중 오류가 발생했습니다")


@router.get("/me", response_model=AdminInfo)
async def get_current_admin(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_async_db)
):
    """현재 인증된 관리자 정보 조회"""
    try:
        if not authorization:
            raise HTTPException(status_code=401, detail="액세스 토큰이 필요합니다")
        
        # Bearer 토큰 추출
        if not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Bearer 토큰 형식이 아닙니다")
        
        access_token = authorization.replace("Bearer ", "")
        
        admin_info = await AuthService.get_current_admin(db, access_token)
        return admin_info
        
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        import traceback
        print("--- UNEXPECTED ERROR IN /me ---")
        traceback.print_exc()
        print("-------------------------------")
        raise HTTPException(status_code=500, detail="관리자 정보 조회 중 오류가 발생했습니다")


@router.post("/logout")
async def logout_admin(
    response: Response,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_async_db),
):
    """관리자 로그아웃"""
    try:
        # 쿠키에서 리프레시 토큰 제거 (환경에 따라 SameSite, Secure 속성 분기)
        if settings.environment == "production":
            samesite_and_secure = "SameSite=None; Secure"
        else:
            samesite_and_secure = "SameSite=Lax"

        response.headers["Set-Cookie"] = (
            f"admin_refresh_token=; "
            f"Max-Age=0; "
            f"Expires=Thu, 01 Jan 1970 00:00:00 GMT; "
            f"Path=/; "
            f"HttpOnly; "
            f"{samesite_and_secure}"
        )
        
        # 액세스 토큰이 있다면 세션에서 제거
        if authorization and authorization.startswith("Bearer "):
            access_token = authorization.replace("Bearer ", "")
            try:
                from app.core.security import verify_token
                token_data = verify_token(access_token)
                if token_data["type"] == "access":
                    AuthService.logout_admin(db, token_data["admin_id"])
            except:
                pass  # 토큰 오류는 무시 (이미 로그아웃 중)
        
        return {"message": "로그아웃되었습니다"}
        
    except Exception:
        # 로그아웃은 실패해도 성공 응답
        return {"message": "로그아웃되었습니다"}
