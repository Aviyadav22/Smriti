"""Tests for config.py security validation."""
import pytest


def test_app_debug_defaults_to_false():
    """app_debug should default to False to prevent accidental debug mode in prod."""
    from app.core.config import Settings
    # Verify the field default is False (not True) in the class definition
    field_info = Settings.model_fields["app_debug"]
    assert field_info.default is False, "app_debug must default to False"


def test_empty_jwt_secret_raises_in_production():
    """Empty JWT secrets must raise ValueError in production."""
    with pytest.raises(ValueError, match="jwt_secret_key"):
        from app.core.config import Settings
        Settings(app_env="production", jwt_secret_key="", jwt_refresh_secret_key="test" * 8)


def test_empty_refresh_secret_raises_in_production():
    with pytest.raises(ValueError, match="jwt_refresh_secret_key"):
        from app.core.config import Settings
        Settings(app_env="production", jwt_secret_key="test" * 8, jwt_refresh_secret_key="")


def test_short_jwt_secret_raises():
    """JWT secrets must be at least 32 characters."""
    with pytest.raises(ValueError, match="at least 32"):
        from app.core.config import Settings
        Settings(app_env="production", jwt_secret_key="short", jwt_refresh_secret_key="test" * 8)


def test_empty_encryption_key_raises_in_production():
    with pytest.raises(ValueError, match="encryption_key"):
        from app.core.config import Settings
        Settings(
            app_env="production",
            jwt_secret_key="a" * 32,
            jwt_refresh_secret_key="b" * 32,
            encryption_key="",
        )


def test_test_env_skips_validation():
    """Test environment should skip all critical validations."""
    from app.core.config import Settings
    s = Settings(app_env="test", jwt_secret_key="", jwt_refresh_secret_key="")
    assert s.jwt_secret_key == ""


def test_development_env_warns_but_allows_empty():
    """Development env should warn but not crash."""
    import warnings
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        from app.core.config import Settings
        Settings(app_env="development", jwt_secret_key="", jwt_refresh_secret_key="")
        assert any("insecure" in str(warning.message).lower() for warning in w)
