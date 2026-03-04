"""Authentication endpoints: register, login, refresh."""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.postgres import get_db
from app.security.auth import (
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
    verify_refresh_token,
)

router = APIRouter()


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    name: str | None = None
    consent_given: bool = True
    consent_version: str = "1.0"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


@router.post("/register", status_code=201)
async def register(
    body: RegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Register a new user with consent."""
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
            "INSERT INTO consent_records (id, user_id, consent_type, granted, version) "
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

    return {"id": user_id, "email": body.email, "role": "researcher"}


@router.post("/login")
async def login(
    body: LoginRequest,
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
            lock_until = datetime.now(timezone.utc).replace(
                minute=datetime.now(timezone.utc).minute + 15
            )
        await db.execute(
            text(
                "UPDATE users SET failed_login_count = :count, locked_until = :lock "
                "WHERE id = :id"
            ),
            {"count": new_count, "lock": lock_until, "id": str(user["id"])},
        )
        await db.commit()
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

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=900,  # 15 minutes
    )


@router.post("/refresh")
async def refresh_token(body: RefreshRequest) -> TokenResponse:
    """Refresh access token using refresh token."""
    payload = verify_refresh_token(body.refresh_token)

    access_token = create_access_token(payload.sub, payload.role)
    new_refresh_token = create_refresh_token(payload.sub)

    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh_token,
        expires_in=900,
    )
