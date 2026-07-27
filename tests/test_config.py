from python_template_uv.config import get_settings


def test_settings_load() -> None:
    settings = get_settings()
    assert settings.environment == "testing"