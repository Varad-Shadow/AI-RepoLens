"""Unit tests for path-component filtering."""

import pytest

from repolens.analyzer.filters import EXCLUDED_DIRS, filter_paths, is_ignored


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("src/app.py", False),
        ("tests/test_app.py", False),
        ("test/unit/test_app.py", False),
        ("contest/main.py", False),
        ("latest/app.py", False),
        ("testing-utils/helper.py", False),
        ("src/config/settings.py", False),
        ("app/server/client/lib/config/routes.py", False),
        ("node_modules/pkg/index.js", True),
        ("vendor/rails/foo.rb", True),
        ("src/__pycache__/mod.pyc", True),
        (".venv/lib/python3/site.py", True),
        ("dist/bundle.js", True),
        ("build/output.js", True),
        (".next/static/chunk.js", True),
    ],
)
def test_is_ignored_path_components(path: str, expected: bool) -> None:
    assert is_ignored(path) is expected


def test_filter_paths_preserves_order() -> None:
    paths = ["README.md", "node_modules/x.js", "src/main.py", "vendor/y.js"]
    kept, ignored = filter_paths(paths)
    assert kept == ["README.md", "src/main.py"]
    assert ignored == ["node_modules/x.js", "vendor/y.js"]


def test_test_not_in_default_excluded_dirs() -> None:
    assert "test" not in EXCLUDED_DIRS
    assert "tests" not in EXCLUDED_DIRS
    assert "src" not in EXCLUDED_DIRS
