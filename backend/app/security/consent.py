"""User consent management for privacy compliance.

Provides functions to record, check, and revoke user consent for various
data processing purposes (e.g., analytics, marketing, data retention).
"""

from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def record_consent(
    db: AsyncSession,
    user_id: str,
    consent_type: str,
    granted: bool,
    version: str,
) -> None:
    """Record a user's consent decision.

    Inserts a new consent record or updates the existing one for the given
    user and consent type.

    Args:
        db: Async SQLAlchemy session.
        user_id: The unique identifier of the user.
        consent_type: The type of consent (e.g., ``"analytics"``,
            ``"marketing"``, ``"data_retention"``, ``"terms_of_service"``).
        granted: Whether the user granted (True) or denied (False) consent.
        version: The version of the consent policy (e.g., ``"1.0"``,
            ``"2024-01-15"``).
    """
    now = datetime.now(timezone.utc)

    await db.execute(
        text(
            """
            INSERT INTO user_consents (
                user_id,
                consent_type,
                granted,
                version,
                created_at,
                updated_at
            ) VALUES (
                :user_id,
                :consent_type,
                :granted,
                :version,
                :created_at,
                :updated_at
            )
            ON CONFLICT (user_id, consent_type)
            DO UPDATE SET
                granted = :granted,
                version = :version,
                updated_at = :updated_at
            """
        ),
        {
            "user_id": user_id,
            "consent_type": consent_type,
            "granted": granted,
            "version": version,
            "created_at": now,
            "updated_at": now,
        },
    )
    await db.commit()


async def check_consent(
    db: AsyncSession,
    user_id: str,
    consent_type: str,
) -> bool:
    """Check whether a user has granted a specific type of consent.

    Args:
        db: Async SQLAlchemy session.
        user_id: The unique identifier of the user.
        consent_type: The type of consent to check.

    Returns:
        True if the user has an active grant for the specified consent type,
        False otherwise (including if no consent record exists).
    """
    result = await db.execute(
        text(
            """
            SELECT granted
            FROM user_consents
            WHERE user_id = :user_id
              AND consent_type = :consent_type
            """
        ),
        {
            "user_id": user_id,
            "consent_type": consent_type,
        },
    )
    row = result.fetchone()
    if row is None:
        return False
    return bool(row[0])


async def revoke_consent(
    db: AsyncSession,
    user_id: str,
    consent_type: str,
) -> None:
    """Revoke a user's previously granted consent.

    Sets the ``granted`` flag to False and updates the timestamp. If no
    consent record exists, this is a no-op.

    Args:
        db: Async SQLAlchemy session.
        user_id: The unique identifier of the user.
        consent_type: The type of consent to revoke.
    """
    now = datetime.now(timezone.utc)

    await db.execute(
        text(
            """
            UPDATE user_consents
            SET granted = FALSE,
                updated_at = :updated_at
            WHERE user_id = :user_id
              AND consent_type = :consent_type
            """
        ),
        {
            "user_id": user_id,
            "consent_type": consent_type,
            "updated_at": now,
        },
    )
    await db.commit()
