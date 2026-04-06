"""User preferences endpoints: get, update, auto-refresh from search history."""

import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.postgres import get_db
from app.security.auth import TokenPayload
from app.security.rate_limiter import rate_limit_dependency
from app.security.rbac import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter()


class UpdatePreferencesRequest(BaseModel):
    """Validated request body for preference updates."""

    # Research preferences
    preferred_jurisdictions: list[str] | None = None
    common_case_types: list[str] | None = None
    preferred_courts: list[str] | None = None
    frequent_acts: list[str] | None = None
    output_preference: str | None = None
    search_mode: str | None = None  # semantic | keyword | hybrid
    citation_format: str | None = None  # standard | oscola | bluebook
    results_per_page: int | None = None  # 10 | 20 | 50

    # Appearance
    theme: str | None = None  # light | dark | system
    language: str | None = None  # en | hi
    font_size: str | None = None  # small | medium | large

    # Notifications & AI
    email_alerts: bool | None = None
    agent_verbosity: str | None = None  # concise | detailed | comprehensive
    tts_voice: str | None = None  # male | female
    tts_language: str | None = None  # en | hi
    response_language: str | None = None  # en | hi


async def _compute_preferences(db: AsyncSession, user_id: str) -> dict:
    """Analyze search history to build user preferences."""
    uid = uuid.UUID(user_id)

    # Search history analysis
    result = await db.execute(
        text(
            "SELECT query, filters FROM search_history "
            "WHERE user_id = :uid AND created_at > NOW() - INTERVAL '30 days' "
            "ORDER BY created_at DESC LIMIT 200"
        ),
        {"uid": uid},
    )
    rows = result.mappings().all()

    jurisdictions: dict[str, int] = {}
    case_types: dict[str, int] = {}
    courts: dict[str, int] = {}
    acts: dict[str, int] = {}

    for row in rows:
        filters = row["filters"] or {}
        if isinstance(filters, dict):
            if filters.get("jurisdiction"):
                j = filters["jurisdiction"]
                jurisdictions[j] = jurisdictions.get(j, 0) + 1
            if filters.get("case_type"):
                ct = filters["case_type"]
                case_types[ct] = case_types.get(ct, 0) + 1
            if filters.get("court"):
                c = filters["court"]
                courts[c] = courts.get(c, 0) + 1
            if filters.get("act"):
                a = filters["act"]
                acts[a] = acts.get(a, 0) + 1

    # Sort and take top entries
    def top_n(counter: dict[str, int], n: int = 5) -> list[str]:
        return sorted(counter, key=lambda k: counter[k], reverse=True)[:n]

    return {
        "preferred_jurisdictions": top_n(jurisdictions),
        "common_case_types": top_n(case_types),
        "preferred_courts": top_n(courts),
        "frequent_acts": top_n(acts, 10),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get(
    "/users/me/preferences",
    dependencies=[Depends(rate_limit_dependency("60/minute"))],
)
async def get_preferences(
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return the authenticated user's preferences."""
    uid = uuid.UUID(current_user.sub)
    result = await db.execute(
        text("SELECT preferences FROM users WHERE id = :uid"),
        {"uid": uid},
    )
    row = result.mappings().one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="User not found")
    return row["preferences"] or {}


@router.put(
    "/users/me/preferences",
    dependencies=[Depends(rate_limit_dependency("20/minute"))],
)
async def update_preferences(
    body: UpdatePreferencesRequest,
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Merge partial update into the user's preferences JSONB."""
    uid = uuid.UUID(current_user.sub)

    # Only include non-None fields so we don't overwrite with nulls
    new_prefs = {k: v for k, v in body.model_dump().items() if v is not None}
    if not new_prefs:
        raise HTTPException(status_code=422, detail="No preference fields provided")

    await db.execute(
        text("UPDATE users SET preferences = preferences || :new_prefs WHERE id = :uid"),
        {"new_prefs": new_prefs, "uid": uid},
    )
    await db.commit()

    # Return the updated preferences
    result = await db.execute(
        text("SELECT preferences FROM users WHERE id = :uid"),
        {"uid": uid},
    )
    row = result.mappings().one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="User not found")
    return row["preferences"] or {}


@router.post(
    "/users/me/preferences/refresh",
    dependencies=[Depends(rate_limit_dependency("5/minute"))],
)
async def refresh_preferences(
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Analyze recent search history to auto-populate preferences."""
    computed = await _compute_preferences(db, current_user.sub)

    uid = uuid.UUID(current_user.sub)
    await db.execute(
        text("UPDATE users SET preferences = preferences || :new_prefs WHERE id = :uid"),
        {"new_prefs": computed, "uid": uid},
    )
    await db.commit()

    # Return the full updated preferences
    result = await db.execute(
        text("SELECT preferences FROM users WHERE id = :uid"),
        {"uid": uid},
    )
    row = result.mappings().one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="User not found")
    return row["preferences"] or {}
