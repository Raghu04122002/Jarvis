"""Tests for secret filtering utilities."""

from jarvis.security.secrets import contains_secrets, filter_secrets


class TestContainsSecrets:
    def test_api_key_detected(self) -> None:
        assert contains_secrets("api_key=sk-1234567890") is True

    def test_bearer_token_detected(self) -> None:
        assert contains_secrets("Authorization: Bearer eyJhbGciOiJ") is True

    def test_aws_access_key_detected(self) -> None:
        assert contains_secrets("AKIAIOSFODNN7EXAMPLE") is True

    def test_github_token_detected(self) -> None:
        assert contains_secrets("ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmn") is True

    def test_password_detected(self) -> None:
        assert contains_secrets("password=mysecretpass123") is True

    def test_private_key_detected(self) -> None:
        assert contains_secrets("-----BEGIN RSA PRIVATE KEY-----") is True

    def test_clean_text(self) -> None:
        assert contains_secrets("Hello, this is normal text.") is False

    def test_empty_string(self) -> None:
        assert contains_secrets("") is False

    def test_slack_token_detected(self) -> None:
        assert contains_secrets("xoxb-1234-5678-abcdef") is True

    def test_secret_key_value(self) -> None:
        assert contains_secrets("secret=my_super_secret_value") is True


class TestFilterSecrets:
    def test_replaces_api_key(self) -> None:
        result = filter_secrets("my api_key=sk-1234567890 is here")
        assert "sk-1234567890" not in result
        assert "[REDACTED]" in result

    def test_replaces_bearer(self) -> None:
        result = filter_secrets("Bearer eyJhbGciOiJ is the token")
        assert "eyJhbGciOiJ" not in result
        assert "[REDACTED]" in result

    def test_replaces_password(self) -> None:
        result = filter_secrets("password=hunter2")
        assert "hunter2" not in result

    def test_clean_text_unchanged(self) -> None:
        text = "This is perfectly safe text."
        assert filter_secrets(text) == text

    def test_multiple_secrets_replaced(self) -> None:
        text = "api_key=abc123 and password=secret"
        result = filter_secrets(text)
        assert "abc123" not in result
        assert "secret" not in result

    def test_github_pat_replaced(self) -> None:
        result = filter_secrets("github_pat_ABCDEFGHIJKLMNOPQRSTUV12")
        assert "github_pat_" not in result
