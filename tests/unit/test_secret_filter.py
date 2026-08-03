"""Unit tests for secret exclusion and redaction."""

from __future__ import annotations

from repolens.security.secret_filter import filter_secret_paths, is_secret_path, redact_secrets


def test_secret_filename_patterns_are_excluded() -> None:
    assert is_secret_path(".env") is True
    assert is_secret_path("config/.env.local") is True
    assert is_secret_path("keys/service.pem") is True
    assert is_secret_path("deploy/id_rsa_prod") is True
    assert is_secret_path("src/app.py") is False


def test_filter_secret_paths_preserves_safe_order() -> None:
    safe, excluded = filter_secret_paths(["README.md", ".env", "src/app.py"])

    assert safe == ["README.md", "src/app.py"]
    assert excluded == [".env"]


def test_redact_common_secret_values() -> None:
    aws_key = "AKIA" + "1234567890ABCDEF"
    content = f"api_key = 'secret-value'\naws={aws_key}\n"

    redacted = redact_secrets(content)

    assert "secret-value" not in redacted
    assert aws_key not in redacted
    assert "[REDACTED]" in redacted


def test_redact_private_key_block() -> None:
    marker = "PRIVATE" + " KEY"
    content = f"-----BEGIN {marker}-----\nabc\n-----END {marker}-----"

    assert redact_secrets(content) == "[REDACTED]"