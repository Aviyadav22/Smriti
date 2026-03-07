"""Tests for Celery configuration."""

from app.worker import celery_app


class TestCeleryConfig:
    def test_celery_app_exists(self) -> None:
        assert celery_app is not None
        assert celery_app.main == "smriti"

    def test_celery_serializer_config(self) -> None:
        assert celery_app.conf.task_serializer == "json"
        assert celery_app.conf.result_serializer == "json"

    def test_celery_broker_configured(self) -> None:
        assert "redis://" in str(celery_app.conf.broker_url)

    def test_celery_task_acks_late(self) -> None:
        assert celery_app.conf.task_acks_late is True
