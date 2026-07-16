from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.modules.auth.models import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer_scheme = HTTPBearer(auto_error=False)
settings = get_settings()

ALGORITHM = "HS256"


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def get_password_hash(plain: str) -> str:
    return pwd_context.hash(plain)


def create_access_token(user_id: str, tenant_id: str, role: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": user_id,
        "tenant_id": tenant_id,
        "role": role,
        "exp": expire,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])


class AuthContext:
    def __init__(self, user_id: uuid.UUID, tenant_id: uuid.UUID, role: str):
        self.user_id = user_id
        self.tenant_id = tenant_id
        self.role = role


async def get_auth_context(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> AuthContext | None:
    if not settings.has_secure_secret and settings.is_dev:
        return AuthContext(
            user_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
            tenant_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
            role="admin",
        )
    if not credentials:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing authorization header")
    try:
        payload = decode_access_token(credentials.credentials)
        user_id = uuid.UUID(payload["sub"])
        tenant_id = uuid.UUID(payload["tenant_id"])
        role = payload.get("role", "analyst")
        result = await db.execute(select(User).where(User.id == user_id, User.is_active == True))
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found or inactive")
        return AuthContext(user_id=user_id, tenant_id=tenant_id, role=role)
    except JWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")


class AuthContextRequired:
    def __init__(self, required_roles: list[str] | None = None):
        self.required_roles = required_roles

    async def __call__(
        self,
        auth: AuthContext | None = Depends(get_auth_context),
    ) -> AuthContext:
        if not auth:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Authentication required")
        if self.required_roles and auth.role not in self.required_roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient permissions")
        return auth
