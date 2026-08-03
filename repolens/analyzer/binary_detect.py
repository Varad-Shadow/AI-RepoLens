"""Binary detection and safe text encoding handling."""

from __future__ import annotations

from dataclasses import dataclass

# Extensions treated as binary without reading content.
BINARY_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".webp",
        ".ico",
        ".bmp",
        ".svgz",
        ".pdf",
        ".zip",
        ".gz",
        ".bz2",
        ".xz",
        ".7z",
        ".rar",
        ".tar",
        ".tgz",
        ".jar",
        ".war",
        ".ear",
        ".exe",
        ".dll",
        ".so",
        ".dylib",
        ".bin",
        ".dat",
        ".wasm",
        ".mp3",
        ".mp4",
        ".avi",
        ".mov",
        ".woff",
        ".woff2",
        ".ttf",
        ".eot",
        ".otf",
        ".class",
        ".pyc",
        ".pyo",
        ".sqlite",
        ".db",
        ".pickle",
        ".pkl",
        ".npy",
        ".npz",
        ".parquet",
        ".avro",
        ".ico",
        ".heic",
        ".heif",
    }
)

# Asset-like extensions: non-source media, not analyzed as text.
ASSET_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".webp",
        ".ico",
        ".bmp",
        ".mp3",
        ".mp4",
        ".wav",
        ".avi",
        ".mov",
        ".woff",
        ".woff2",
        ".ttf",
        ".eot",
        ".otf",
    }
)

DEFAULT_SAMPLE_SIZE = 8192


@dataclass(frozen=True)
class ContentInspection:
    """Result of inspecting a bounded content sample."""

    is_binary: bool
    encoding: str | None
    decoded_preview: str | None
    truncated: bool = False


def extension_of(path: str) -> str:
    """Return lowercase file extension including the dot."""
    name = path.rsplit("/", 1)[-1]
    dot = name.rfind(".")
    if dot <= 0:
        return ""
    return name[dot:].lower()


def is_binary_extension(path: str) -> bool:
    """Heuristic binary detection from file extension only."""
    return extension_of(path) in BINARY_EXTENSIONS


def is_asset_extension(path: str) -> bool:
    """Return True for common non-text asset extensions."""
    return extension_of(path) in ASSET_EXTENSIONS


def is_binary_content(sample: bytes) -> bool:
    """Detect binary content from a bounded byte sample."""
    if not sample:
        return False
    if b"\x00" in sample:
        return True

    if sample.startswith((b"\xef\xbb\xbf", b"\xff\xfe", b"\xfe\xff")):
        return False

    if len(sample) < 4:
        return False

    text_bytes = bytes(range(32, 127)) + b"\n\r\t"
    non_text = sum(1 for byte in sample if byte not in text_bytes)
    return (non_text / len(sample)) > 0.30


def _decode_utf8(sample: bytes) -> str | None:
    try:
        return sample.decode("utf-8")
    except UnicodeDecodeError:
        return None


def _decode_with_bom(sample: bytes) -> tuple[str | None, str | None]:
    if sample.startswith(b"\xef\xbb\xbf"):
        text = _decode_utf8(sample[3:])
        return text, "utf-8-sig" if text is not None else None
    if sample.startswith(b"\xff\xfe"):
        try:
            return sample[2:].decode("utf-16-le"), "utf-16-le"
        except UnicodeDecodeError:
            return None, None
    if sample.startswith(b"\xfe\xff"):
        try:
            return sample[2:].decode("utf-16-be"), "utf-16-be"
        except UnicodeDecodeError:
            return None, None
    return None, None


def inspect_content(
    content: bytes,
    *,
    max_sample_size: int = DEFAULT_SAMPLE_SIZE,
) -> ContentInspection:
    """Inspect at most max_sample_size bytes without loading more into memory."""
    if not content:
        return ContentInspection(is_binary=False, encoding="utf-8", decoded_preview="")

    truncated = len(content) > max_sample_size
    sample = content[:max_sample_size]

    if is_binary_content(sample):
        return ContentInspection(
            is_binary=True,
            encoding=None,
            decoded_preview=None,
            truncated=truncated,
        )

    bom_text, bom_encoding = _decode_with_bom(sample)
    if bom_text is not None:
        return ContentInspection(
            is_binary=False,
            encoding=bom_encoding,
            decoded_preview=bom_text,
            truncated=truncated,
        )

    utf8_text = _decode_utf8(sample)
    if utf8_text is not None:
        return ContentInspection(
            is_binary=False,
            encoding="utf-8",
            decoded_preview=utf8_text,
            truncated=truncated,
        )

    # Last-resort readable decode; replacement chars indicate unusual encoding.
    fallback = sample.decode("latin-1", errors="replace")
    return ContentInspection(
        is_binary=False,
        encoding="latin-1",
        decoded_preview=fallback,
        truncated=truncated,
    )


def is_binary_path(path: str, content_sample: bytes | None = None) -> bool:
    """Determine whether a path should be treated as binary."""
    if is_binary_extension(path):
        return True
    if content_sample is not None and is_binary_content(content_sample[:DEFAULT_SAMPLE_SIZE]):
        return True
    return False
