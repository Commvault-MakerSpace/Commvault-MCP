import os

import pytest
from src.cv_mcp.config import ConfigError, Settings, load_env_file


class TestSettingsFromEnv:
    def test_minimal_env(self):
        env = {"CV_SERVER_URL": "https://cc.example/"}
        settings = Settings.from_env(env)
        assert settings.server_url == "https://cc.example"
        assert settings.ssl_verify is True
        assert settings.allow_writes is False
        assert settings.log_level == "INFO"
        assert settings.timeout == 60.0
        assert settings.access_token is None
        assert settings.refresh_token is None
        assert settings.token_file is None
        assert settings.verify is True

    def test_missing_server_url(self):
        with pytest.raises(ConfigError, match="required"):
            Settings.from_env({})

    def test_server_url_no_scheme(self):
        with pytest.raises(ConfigError, match="must start with"):
            Settings.from_env({"CV_SERVER_URL": "cc.example"})

    @pytest.mark.parametrize(
        "value, expected",
        [
            ("false", False),
            ("0", False),
            ("No", False),
            ("TRUE", True),
            ("1", True),
            ("yes", True),
        ],
    )
    def test_ssl_verify_values(self, value, expected):
        env = {"CV_SERVER_URL": "https://example.com", "CV_SSL_VERIFY": value}
        settings = Settings.from_env(env)
        assert settings.ssl_verify is expected

    def test_ssl_verify_invalid(self):
        env = {"CV_SERVER_URL": "https://example.com", "CV_SSL_VERIFY": "maybe"}
        with pytest.raises(ConfigError, match="Invalid boolean"):
            Settings.from_env(env)

    def test_ca_bundle_sets_verify_path(self):
        env = {
            "CV_SERVER_URL": "https://example.com",
            "CV_SSL_VERIFY": "false",
            "CV_CA_BUNDLE": "/path/to/ca.pem",
        }
        settings = Settings.from_env(env)
        assert settings.verify == "/path/to/ca.pem"

    def test_empty_strings_count_as_unset(self):
        env = {
            "CV_SERVER_URL": "https://example.com",
            "CV_ACCESS_TOKEN": "",
            "CV_TOKEN_FILE": "  ",
        }
        settings = Settings.from_env(env)
        assert settings.access_token is None
        assert settings.token_file is None

    def test_log_level_debug(self):
        env = {"CV_SERVER_URL": "https://example.com", "CV_LOG_LEVEL": "debug"}
        settings = Settings.from_env(env)
        assert settings.log_level == "DEBUG"

    def test_timeout_invalid(self):
        env = {"CV_SERVER_URL": "https://example.com", "CV_TIMEOUT": "abc"}
        with pytest.raises(ConfigError, match="must be a number"):
            Settings.from_env(env)

    def test_timeout_valid(self):
        env = {"CV_SERVER_URL": "https://example.com", "CV_TIMEOUT": "15"}
        settings = Settings.from_env(env)
        assert settings.timeout == 15.0

    def test_allow_writes_true(self):
        env = {"CV_SERVER_URL": "https://example.com", "CV_MCP_ALLOW_WRITES": "true"}
        settings = Settings.from_env(env)
        assert settings.allow_writes is True


class TestLoadEnvFile:
    def test_none_is_noop(self, monkeypatch):
        # Should not raise
        load_env_file(None)

    def test_missing_path_raises(self):
        with pytest.raises(ConfigError, match="not found"):
            load_env_file("/nonexistent/path/.env")

    def test_load_sets_env_var(self, tmp_path, monkeypatch):
        env_file = tmp_path / ".env"
        env_file.write_text("CV_FOO=bar\n")

        # Ensure it's not already set
        monkeypatch.delenv("CV_FOO", raising=False)

        load_env_file(str(env_file))

        assert os.environ.get("CV_FOO") == "bar"

        # Cleanup
        del os.environ["CV_FOO"]
