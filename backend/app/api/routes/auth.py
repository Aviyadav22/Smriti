"""Authentication endpoints: register, login, refresh."""

import re
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from app.security.rate_limiter import rate_limit_dependency
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.postgres import get_db
from app.security.auth import (
    create_access_token,
    create_refresh_token,
    hash_password,
    revoke_token,
    verify_password,
    verify_refresh_token,
)
from app.security.audit import create_audit_log
from app.security.rbac import get_current_user
from app.security.auth import TokenPayload

router = APIRouter()


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    name: str | None = None
    consent_given: bool = True
    consent_version: str = "1.0"

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"[a-z]", v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one digit")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str | None = None


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


@router.post("/register", status_code=201, dependencies=[Depends(rate_limit_dependency("5/minute"))])
async def register(
    body: RegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Register a new user with consent and return JWT tokens (auto-login)."""
    if not body.consent_given:
        raise HTTPException(status_code=400, detail="Consent is required for registration")

    # Check if email exists
    result = await db.execute(
        text("SELECT id FROM users WHERE email = :email"),
        {"email": body.email},
    )
    if result.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="Email already registered")

    user_id = str(uuid.uuid4())
    password_hash = hash_password(body.password)

    await db.execute(
        text(
            "INSERT INTO users (id, email, password_hash, name, role) "
            "VALUES (:id, :email, :password_hash, :name, :role)"
        ),
        {
            "id": user_id,
            "email": body.email,
            "password_hash": password_hash,
            "name": body.name,
            "role": "researcher",
        },
    )

    # Record consent
    await db.execute(
        text(
            "INSERT INTO consents (id, user_id, consent_type, granted, version) "
            "VALUES (:id, :user_id, :consent_type, :granted, :version)"
        ),
        {
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "consent_type": "data_processing",
            "granted": True,
            "version": body.consent_version,
        },
    )

    await db.commit()

    # Auto-login: generate tokens just like the login endpoint
    access_token = create_access_token(user_id, "researcher")
    refresh_token = create_refresh_token(user_id)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.jwt_access_token_expire_minutes * 60,
    )


@router.post("/login", dependencies=[Depends(rate_limit_dependency("5/minute"))])
async def login(
    body: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Authenticate and return JWT token pair."""
    result = await db.execute(
        text(
            "SELECT id, password_hash, role, is_active, failed_login_count, locked_until "
            "FROM users WHERE email = :email"
        ),
        {"email": body.email},
    )
    user = result.mappings().one_or_none()

    if user is None:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    # Check account lock
    if user["locked_until"] and user["locked_until"] > datetime.now(timezone.utc):
        raise HTTPException(status_code=423, detail="Account temporarily locked")

    if not user["is_active"]:
        raise HTTPException(status_code=403, detail="Account is deactivated")

    if not verify_password(body.password, user["password_hash"]):
        # Increment failed login count
        new_count = (user["failed_login_count"] or 0) + 1
        lock_until = None
        if new_count >= 5:
            lock_until = datetime.now(timezone.utc) + timedelta(minutes=15)
        await db.execute(
            text(
                "UPDATE users SET failed_login_count = :count, locked_until = :lock "
                "WHERE id = :id"
            ),
            {"count": new_count, "lock": lock_until, "id": str(user["id"])},
        )
        await db.commit()
        await create_audit_log(
            db=db,
            action="login.failure",
            user_id=str(user["id"]),
            resource_type="auth",
            resource_id=None,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            metadata={"reason": "invalid_password", "attempt": new_count},
        )
        raise HTTPException(status_code=401, detail="Invalid email or password")

    # Reset failed count, update last login
    await db.execute(
        text(
            "UPDATE users SET failed_login_count = 0, locked_until = NULL, "
            "last_login_at = :now WHERE id = :id"
        ),
        {"now": datetime.now(timezone.utc), "id": str(user["id"])},
    )
    await db.commit()

    access_token = create_access_token(str(user["id"]), user["role"])
    refresh_token = create_refresh_token(str(user["id"]))

    await create_audit_log(
        db=db,
        action="login.success",
        user_id=str(user["id"]),
        resource_type="auth",
        resource_id=None,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.jwt_access_token_expire_minutes * 60,
    )


@router.post("/refresh", dependencies=[Depends(rate_limit_dependency("10/minute"))])
async def refresh_token(
    body: RefreshRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Refresh access token using refresh token with rotation."""
    payload = await verify_refresh_token(body.refresh_token)

    # Fetch the user's actual role from the database (refresh token has role="refresh")
    result = await db.execute(
        text("SELECT role, is_active FROM users WHERE id = :id"),
        {"id": payload.sub},
    )
    user = result.mappings().one_or_none()
    if user is None or not user["is_active"]:
        raise HTTPException(status_code=401, detail="User not found or deactivated")

    access_token = create_access_token(payload.sub, user["role"])
    new_refresh_token = create_refresh_token(payload.sub)

    # Revoke the old refresh token (rotation)
    await revoke_token(payload.jti, int(payload.exp.timestamp()))

    await create_audit_log(
        db=db,
        action="token.refresh",
        user_id=payload.sub,
        resource_type="auth",
        resource_id=None,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh_token,
        expires_in=settings.jwt_access_token_expire_minutes * 60,
    )


@router.post("/logout", status_code=200)
async def logout(
    body: LogoutRequest | None = None,
    current_user: TokenPayload = Depends(get_current_user),
) -> dict[str, str]:
    """Revoke the current access token and optional refresh token (logout).

    Adds the token JTIs to the Redis revocation list so they can no longer
    be used for authentication.
    """
    await revoke_token(current_user.jti, int(current_user.exp.timestamp()))
    if body and body.refresh_token:
        try:
            refresh_payload = await verify_refresh_token(body.refresh_token)
            await revoke_token(refresh_payload.jti, int(refresh_payload.exp.timestamp()))
        except Exception:
            pass
    return {"detail": "Successfully logged out"}
