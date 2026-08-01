"""Unit tests for binary detection and encoding safety."""

import pytest

from repolens.analyzer.binary_detect import (
    inspect_content,
    is_binary_content,
    is_binary_extension,
    is_binary_path,
)


def test_binary_extension_detection() -> None:
    assert is_binary_extension("assets/logo.png") is True
    assert is_binary_extension("src/app.py") is False


def test_null_byte_sample_is_binary() -> None:
    assert is_binary_content(b"hello\x00world") is True


def test_utf8_text_sample_is_not_binary() -> None:
    assert is_binary_content(b"def hello():\n    return 'world'\n") is False


def test_inspect_empty_content() -> None:
    result = inspect_content(b"")
    assert result.is_binary is False
    assert result.encoding == "utf-8"
    assert result.decoded_preview == ""


def test_inspect_utf8_content() -> None:
    result = inspect_content("print('hi')".encode())
    assert result.is_binary is False
    assert result.encoding == "utf-8"
    assert "print" in (result.decoded_preview or "")


def test_inspect_utf8_bom() -> None:
    content = b"\xef\xbb\xbfhello"
    result = inspect_content(content)
    assert result.is_binary is False
    assert result.encoding == "utf-8-sig"
    assert result.decoded_preview == "hello"


def test_inspect_binary_content_not_decoded_as_utf8() -> None:
    binary = bytes(range(256))[:200]
    result = inspect_content(binary)
    assert result.is_binary is True
    assert result.decoded_preview is None


def test_inspect_latin1_fallback_for_unusual_encoding() -> None:
    # bytes that are valid latin-1 but invalid utf-8
    content = b"\xe9\xe8\xe0"
    result = inspect_content(content)
    assert result.is_binary is False
    assert result.encoding == "latin-1"
    assert result.decoded_preview is not None


def test_inspect_truncates_large_content_sample() -> None:
    large = b"a" * 20_000
    result = inspect_content(large, max_sample_size=1024)
    assert result.truncated is True
    assert result.is_binary is False
    assert len(result.decoded_preview or "") == 1024


def test_is_binary_path_without_content_uses_extension() -> None:
    assert is_binary_path("image.ico") is True
    assert is_binary_path("main.py") is False


def test_is_binary_path_with_content_sample() -> None:
    assert is_binary_path("data.bin", b"\x00\x01\x02") is True
    assert is_binary_path("data.txt", b"plain text") is False


def test_never_decodes_png_as_text() -> None:
    png_header = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
    result = inspect_content(png_header)
    assert result.is_binary is True
