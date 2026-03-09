"""Celery task for audio digest generation."""

from __future__ import annotations

import logging
import os
import tempfile
import uuid

from sqlalchemy import text

from app.worker import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=2, default_retry_delay=60)
def generate_audio(self, case_id: str, language: str = "en") -> dict:
    """Generate audio digest for a case."""
    import asyncio
    return asyncio.run(_generate_audio_async(case_id, language))


async def _generate_audio_async(case_id: str, language: str) -> dict:
    """Async implementation of audio generation."""
    from app.core.legal.prompts import AUDIO_SUMMARY_SYSTEM, AUDIO_SUMMARY_USER
    from app.core.providers.llm.gemini import GeminiLLM
    from app.core.providers.storage.local_storage import LocalStorage
    from app.db.postgres import get_async_session

    digest_id: str | None = None

    async with get_async_session() as db:
        try:
            # Check if audio already exists
            existing = await db.execute(
                text(
                    "SELECT id, status FROM audio_digests "
                    "WHERE case_id = :case_id AND language = :lang"
                ),
                {"case_id": case_id, "lang": language},
            )
            row = existing.mappings().one_or_none()
            if row and row["status"] == "completed":
                return {"status": "already_exists", "case_id": case_id}

            # Get case data
            case_result = await db.execute(
                text(
                    "SELECT title, court, year, judge, full_text "
                    "FROM cases WHERE id = :id"
                ),
                {"id": case_id},
            )
            case = case_result.mappings().one_or_none()
            if not case:
                raise ValueError(f"Case not found: {case_id}")

            # Create or update audio_digests record
            digest_id = str(row["id"]) if row else str(uuid.uuid4())
            if not row:
                await db.execute(
                    text(
                        "INSERT INTO audio_digests (id, case_id, language, status) "
                        "VALUES (:id, :case_id, :lang, 'generating')"
                    ),
                    {"id": digest_id, "case_id": case_id, "lang": language},
                )
            else:
                await db.execute(
                    text("UPDATE audio_digests SET status = 'generating' WHERE id = :id"),
                    {"id": digest_id},
                )
            await db.commit()

            # Step 1: Generate summary text
            llm = GeminiLLM()
            judges = case["judge"] or []
            judges_str = ", ".join(judges) if isinstance(judges, list) else str(judges)

            prompt = AUDIO_SUMMARY_USER.format(
                title=case["title"] or "Unknown",
                court=case["court"] or "Unknown",
                year=case["year"] or "Unknown",
                judges=judges_str,
                judgment_text=(case["full_text"] or "")[:80000],
            )

            summary_text = await llm.generate(
                prompt,
                system=AUDIO_SUMMARY_SYSTEM,
                temperature=0.3,
                max_tokens=2048,
            )

            # Step 2: TTS
            from app.core.dependencies import get_tts
            tts = get_tts()
            audio_bytes = await tts.synthesize(summary_text, language=language)

            # Step 3: Store audio file
            storage = LocalStorage()
            audio_dir = f"audio/{case_id}"
            audio_filename = f"{language}.mp3"

            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
                tmp.write(audio_bytes)
                tmp_path = tmp.name

            storage_path = await storage.store(tmp_path, f"{audio_dir}/{audio_filename}")

            try:
                os.unlink(tmp_path)
            except OSError:
                pass

            # Estimate duration
            word_count = len(summary_text.split())
            duration_seconds = int(word_count / 150 * 60)

            # Step 4: Update record
            await db.execute(
                text(
                    "UPDATE audio_digests SET "
                    "summary_text = :summary, audio_storage_path = :path, "
                    "duration_seconds = :duration, status = 'completed', "
                    "updated_at = NOW() "
                    "WHERE id = :id"
                ),
                {
                    "id": digest_id,
                    "summary": summary_text,
                    "path": storage_path,
                    "duration": duration_seconds,
                },
            )
            await db.commit()

            return {
                "status": "completed",
                "case_id": case_id,
                "language": language,
                "duration_seconds": duration_seconds,
            }

        except Exception as exc:
            logger.exception("Audio generation failed for case %s", case_id)
            if digest_id:
                await db.execute(
                    text(
                        "UPDATE audio_digests SET status = 'failed', "
                        "error_message = :error, updated_at = NOW() "
                        "WHERE id = :id"
                    ),
                    {"id": digest_id, "error": str(exc)},
                )
                await db.commit()
            return {"status": "failed", "case_id": case_id, "error": str(exc)}


def _get_tts_provider():
    """Get the configured TTS provider.

    .. deprecated::
        Use ``app.core.dependencies.get_tts()`` instead.
    """
    from app.core.dependencies import get_tts

    return get_tts()
