"""Authentication endpoints: register, login, refresh."""

import logging
import re
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.postgres import get_db
from app.security.audit import create_audit_log
from app.security.auth import (
    TokenPayload,
    create_access_token,
    create_refresh_token,
    hash_password,
    revoke_token,
    verify_password,
    verify_refresh_token,
)
from app.security.rate_limiter import rate_limit_dependency
from app.security.rbac import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# Refresh token cookie helpers
# ---------------------------------------------------------------------------

_REFRESH_COOKIE = "smriti_refresh"
_REFRESH_COOKIE_PATH = "/api/v1/auth"


def _set_refresh_cookie(response: Response, token: str) -> None:
    """Set refresh token as httpOnly cookie on the response."""
    is_prod = settings.app_env == "production"
    response.set_cookie(
        key=_REFRESH_COOKIE,
        value=token,
        httponly=True,
        secure=is_prod,
        samesite="lax",
        path=_REFRESH_COOKIE_PATH,
        max_age=settings.jwt_refresh_token_expire_days * 86400,
    )


def _clear_refresh_cookie(response: Response) -> None:
    """Clear refresh token cookie."""
    is_prod = settings.app_env == "production"
    response.delete_cookie(
        key=_REFRESH_COOKIE,
        httponly=True,
        secure=is_prod,
        samesite="lax",
        path=_REFRESH_COOKIE_PATH,
    )


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    name: str | None = None
    consent_given: bool  # Must be explicitly set — no default (DPDP compliance)
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
    """Legacy body-based refresh. Prefer reading from httpOnly cookie."""
    refresh_token: str | None = None


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def validate_new_password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"[a-z]", v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one digit")
        return v


class LogoutRequest(BaseModel):
    refresh_token: str | None = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    refresh_token: str  # Always included — dev proxy may not forward httpOnly cookies


@router.post("/register", status_code=201, dependencies=[Depends(rate_limit_dependency("5/minute"))])
async def register(
    body: RegisterRequest,
    response: Response,
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

    # Audit log for registration
    await create_audit_log(
        db=db,
        action="user.registered",
        user_id=user_id,
        resource_type="user",
        resource_id=user_id,
        metadata={"consent_version": body.consent_version},
    )

    # Auto-login: generate tokens just like the login endpoint
    access_token = create_access_token(user_id, "researcher")
    refresh_tok = create_refresh_token(user_id)
    _set_refresh_cookie(response, refresh_tok)

    return TokenResponse(
        access_token=access_token,
        expires_in=settings.jwt_access_token_expire_minutes * 60,
        refresh_token=refresh_tok,
    )


@router.post("/login", dependencies=[Depends(rate_limit_dependency("15/minute"))])
async def login(
    body: LoginRequest,
    request: Request,
    response: Response,
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
    now = datetime.now(timezone.utc)
    if user["locked_until"] and user["locked_until"] > now:
        remaining = (user["locked_until"] - now).seconds // 60 + 1
        raise HTTPException(
            status_code=423,
            detail=f"Account temporarily locked. Try again in {remaining} minute(s).",
        )

    if not user["is_active"]:
        raise HTTPException(status_code=403, detail="Account is deactivated")

    if not verify_password(body.password, user["password_hash"]):
        # Increment failed login count — lock after 10 failed attempts for 5 minutes
        new_count = (user["failed_login_count"] or 0) + 1
        lock_until = None
        if new_count >= 10:
            lock_until = datetime.now(timezone.utc) + timedelta(minutes=5)
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
        remaining = 10 - new_count
        detail = "Invalid email or password"
        if 0 < remaining <= 3:
            detail += f" ({remaining} attempt(s) remaining before temporary lock)"
        raise HTTPException(status_code=401, detail=detail)

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
    refresh_tok = create_refresh_token(str(user["id"]))
    _set_refresh_cookie(response, refresh_tok)

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
        expires_in=settings.jwt_access_token_expire_minutes * 60,
        refresh_token=refresh_tok,
    )


@router.post("/refresh", dependencies=[Depends(rate_limit_dependency("10/minute"))])
async def refresh_token(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    body: RefreshRequest | None = None,
    smriti_refresh: str | None = Cookie(default=None),
) -> TokenResponse:
    """Refresh access token using refresh token with rotation.

    Reads refresh token from httpOnly cookie (preferred) or legacy request body.
    """
    token = smriti_refresh or (body.refresh_token if body else None)
    if not token:
        raise HTTPException(status_code=401, detail="Missing refresh token")

    payload = await verify_refresh_token(token)

    # Fetch the user's actual role from the database (refresh token has role="refresh")
    result = await db.execute(
        text("SELECT role, is_active FROM users WHERE id = :id"),
        {"id": payload.sub},
    )
    user = result.mappings().one_or_none()
    if user is None or not user["is_active"]:
        _clear_refresh_cookie(response)
        raise HTTPException(status_code=401, detail="User not found or deactivated")

    access_token = create_access_token(payload.sub, user["role"])
    new_refresh_tok = create_refresh_token(payload.sub)
    _set_refresh_cookie(response, new_refresh_tok)

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
        expires_in=settings.jwt_access_token_expire_minutes * 60,
        refresh_token=new_refresh_tok,
    )


@router.post(
    "/logout",
    status_code=200,
    dependencies=[Depends(rate_limit_dependency("20/minute"))],
)
async def logout(
    response: Response,
    current_user: TokenPayload = Depends(get_current_user),
    body: LogoutRequest | None = None,
    smriti_refresh: str | None = Cookie(default=None),
) -> dict[str, str]:
    """Revoke the current access token and optional refresh token (logout).

    Reads refresh token from httpOnly cookie (preferred) or legacy request body.
    Clears the refresh cookie on the response.
    """
    await revoke_token(current_user.jti, int(current_user.exp.timestamp()))

    # Revoke refresh token from cookie or body
    refresh_tok = smriti_refresh or (body.refresh_token if body else None)
    if refresh_tok:
        try:
            refresh_payload = await verify_refresh_token(refresh_tok)
            await revoke_token(refresh_payload.jti, int(refresh_payload.exp.timestamp()))
        except (HTTPException, ValueError, RuntimeError) as exc:
            logger.warning(
                "Failed to revoke refresh token during logout: %s", exc
            )

    _clear_refresh_cookie(response)
    return {"detail": "Successfully logged out"}


@router.post(
    "/change-password",
    status_code=200,
    dependencies=[Depends(rate_limit_dependency("5/minute"))],
)
async def change_password(
    body: ChangePasswordRequest,
    request: Request,
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Change the authenticated user's password."""
    uid = uuid.UUID(current_user.sub)

    result = await db.execute(
        text("SELECT password_hash FROM users WHERE id = :uid AND is_active = true"),
        {"uid": uid},
    )
    row = result.mappings().one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="User not found")

    if not verify_password(body.current_password, row["password_hash"]):
        await create_audit_log(
            db=db,
            action="password.change_failed",
            user_id=current_user.sub,
            resource_type="auth",
            resource_id=None,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            metadata={"reason": "invalid_current_password"},
        )
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    new_hash = hash_password(body.new_password)
    await db.execute(
        text("UPDATE users SET password_hash = :hash, updated_at = NOW() WHERE id = :uid"),
        {"hash": new_hash, "uid": uid},
    )
    await db.commit()

    await create_audit_log(
        db=db,
        action="password.changed",
        user_id=current_user.sub,
        resource_type="auth",
        resource_id=None,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

    return {"detail": "Password changed successfully"}


@router.delete("/me", status_code=200, dependencies=[Depends(rate_limit_dependency("3/hour"))])
async def delete_account(
    request: Request,
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Delete user account and all personal data (DPDP Act Section 12).

    Cascade deletes: agent executions, chat messages, chat sessions,
    documents, audio digests, consents, then deactivates user.
    """
    uid = current_user.sub

    # Delete agent executions
    await db.execute(
        text("DELETE FROM agent_executions WHERE user_id = :uid"),
        {"uid": uid},
    )

    # Delete chat messages via sessions
    await db.execute(
        text("""
            DELETE FROM chat_messages WHERE session_id IN
            (SELECT id FROM chat_sessions WHERE user_id = :uid)
        """),
        {"uid": uid},
    )
    await db.execute(
        text("DELETE FROM chat_sessions WHERE user_id = :uid"),
        {"uid": uid},
    )

    # Delete documents — clean up storage files first (DPDP compliance)
    try:
        doc_rows = await db.execute(
            text("SELECT storage_path FROM documents WHERE user_id = :uid"),
            {"uid": uid},
        )
        from app.core.dependencies import get_storage as _get_storage
        _storage = _get_storage()
        for row in doc_rows.mappings().all():
            if row.get("storage_path"):
                try:
                    await _storage.delete(row["storage_path"])
                except OSError as e:
                    logger.error("Failed to delete storage file %s: %s", row["storage_path"], e)
    except Exception as e:
        logger.warning("Storage file cleanup during account deletion failed: %s", e)

    await db.execute(
        text("DELETE FROM documents WHERE user_id = :uid"),
        {"uid": uid},
    )

    # Delete consents
    await db.execute(
        text("DELETE FROM consents WHERE user_id = :uid"),
        {"uid": uid},
    )

    # Log erasure in DPDP audit (retained for compliance)
    await db.execute(
        text("""
            INSERT INTO dpdp_audit_log (action, user_id, details)
            VALUES ('account_deleted', :uid, '{"initiated_by": "user"}'::jsonb)
        """),
        {"uid": uid},
    )

    # Deactivate user account (don't hard delete — keep for audit trail)
    await db.execute(
        text("UPDATE users SET is_active = false, email = :anon_email WHERE id = :uid"),
        {"uid": uid, "anon_email": f"deleted_{uid[:8]}@deleted.local"},
    )

    await db.commit()

    # Revoke current token
    await revoke_token(current_user.jti, int(current_user.exp.timestamp()))

    # Best-effort cleanup of external stores (Pinecone vectors, Neo4j nodes, Redis cache)
    try:
        from app.core.dependencies import get_vector_store, get_graph_store
        vector_store = get_vector_store()
        if vector_store and hasattr(vector_store, "delete_by_metadata"):
            await vector_store.delete_by_metadata({"user_id": uid})
    except Exception as e:
        logger.warning("Failed to clean Pinecone vectors for deleted user %s: %s", uid[:8], e)

    try:
        graph_store = get_graph_store()
        if graph_store and hasattr(graph_store, "delete_user_data"):
            await graph_store.delete_user_data(uid)
    except Exception as e:
        logger.warning("Failed to clean Neo4j data for deleted user %s: %s", uid[:8], e)

    try:
        from app.db.redis_client import get_redis
        redis_client = await get_redis()
        if redis_client:
            # Scan and delete user-specific cache keys
            async for key in redis_client.scan_iter(match=f"user:{uid}:*", count=100):
                await redis_client.delete(key)
    except Exception as e:
        logger.warning("Failed to clean Redis cache for deleted user %s: %s", uid[:8], e)

    await create_audit_log(
        db=db,
        action="account.deleted",
        user_id=uid,
        resource_type="auth",
        resource_id=None,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

    return {"detail": "Account and all personal data deleted."}
