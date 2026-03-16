"""Unit tests for attachment filename sanitization."""

import pytest

from taskmeagents.history.attachments import _sanitize_filename


def test_sanitize_normal_filename():
    assert _sanitize_filename("report.pdf") == "report.pdf"
    assert _sanitize_filename("my file (1).docx") == "my file (1).docx"


def test_sanitize_path_traversal():
    # os.path.basename strips directory components, so traversal paths yield safe names
    assert _sanitize_filename("../../etc/passwd") == "passwd"
    assert _sanitize_filename("subdir/file.txt") == "file.txt"
    # Empty basename after stripping should raise
    with pytest.raises(ValueError):
        _sanitize_filename("../../")
    with pytest.raises(ValueError):
        _sanitize_filename("")


def test_sanitize_dotfile():
    with pytest.raises(ValueError):
        _sanitize_filename(".hidden")
    with pytest.raises(ValueError):
        _sanitize_filename(".env")
