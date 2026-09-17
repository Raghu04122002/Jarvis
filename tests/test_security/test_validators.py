"""Tests for security validators."""

import os
import tempfile

import pytest

from jarvis.security.validators import (
    PathTraversalError,
    ShellInjectionError,
    is_path_safe,
    sanitize_tool_args,
    validate_working_dir,
)


class TestValidateWorkingDir:
    def test_absolute_path_returned(self, tmp_path: object) -> None:
        path = str(tmp_path)
        result = validate_working_dir(path)
        assert os.path.isabs(result)

    def test_resolves_symlinks(self, tmp_path: object) -> None:
        real = str(tmp_path)
        result = validate_working_dir(real)
        assert result == os.path.realpath(real)

    def test_allowed_roots_valid(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            subdir = os.path.join(root, "sub")
            os.makedirs(subdir)
            result = validate_working_dir(subdir, allowed_roots=[root])
            assert result.startswith(os.path.realpath(root))

    def test_allowed_roots_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            with tempfile.TemporaryDirectory() as other:
                with pytest.raises(PathTraversalError):
                    validate_working_dir(other, allowed_roots=[root])

    def test_traversal_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            traversal = os.path.join(root, "..", "..", "etc")
            with pytest.raises(PathTraversalError):
                validate_working_dir(traversal, allowed_roots=[root])

    def test_no_roots_allows_any_abs_path(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            result = validate_working_dir(d)
            assert os.path.isabs(result)

    def test_multiple_allowed_roots(self) -> None:
        with tempfile.TemporaryDirectory() as root1:
            with tempfile.TemporaryDirectory() as root2:
                sub = os.path.join(root2, "inner")
                os.makedirs(sub)
                result = validate_working_dir(sub, allowed_roots=[root1, root2])
                assert os.path.isabs(result)


class TestIsPathSafe:
    def test_within_base(self, tmp_path: object) -> None:
        base = str(tmp_path)
        child = os.path.join(base, "sub", "file.txt")
        assert is_path_safe(child, base) is True

    def test_outside_base(self) -> None:
        assert is_path_safe("/etc/passwd", "/home/user") is False

    def test_traversal(self, tmp_path: object) -> None:
        base = str(tmp_path)
        escape = os.path.join(base, "..", "..", "etc", "passwd")
        assert is_path_safe(escape, base) is False

    def test_same_dir(self, tmp_path: object) -> None:
        base = str(tmp_path)
        assert is_path_safe(base, base) is True


class TestSanitizeToolArgs:
    def test_strips_whitespace(self) -> None:
        result = sanitize_tool_args({"msg": "  hello  "})
        assert result["msg"] == "hello"

    def test_passes_non_string(self) -> None:
        result = sanitize_tool_args({"count": 5})
        assert result["count"] == 5

    def test_semicolon_injection(self) -> None:
        with pytest.raises(ShellInjectionError):
            sanitize_tool_args({"cmd": "safe; rm -rf /"})

    def test_pipe_injection(self) -> None:
        with pytest.raises(ShellInjectionError):
            sanitize_tool_args({"cmd": "echo test| cat /etc/passwd"})

    def test_and_injection(self) -> None:
        with pytest.raises(ShellInjectionError):
            sanitize_tool_args({"cmd": "echo ok&& malicious"})

    def test_backtick_injection(self) -> None:
        with pytest.raises(ShellInjectionError):
            sanitize_tool_args({"cmd": "echo `whoami`"})

    def test_dollar_paren_injection(self) -> None:
        with pytest.raises(ShellInjectionError):
            sanitize_tool_args({"cmd": "echo $(whoami)"})

    def test_safe_values_pass(self) -> None:
        result = sanitize_tool_args({"branch": "feature/my-branch", "msg": "a commit message"})
        assert result["branch"] == "feature/my-branch"
        assert result["msg"] == "a commit message"

    def test_list_values_sanitized(self) -> None:
        result = sanitize_tool_args({"files": ["  a.py  ", "b.py"]})
        assert result["files"] == ["a.py", "b.py"]

    def test_list_with_injection(self) -> None:
        with pytest.raises(ShellInjectionError):
            sanitize_tool_args({"files": ["ok.py", "bad; rm -rf /"]})

    def test_or_injection(self) -> None:
        with pytest.raises(ShellInjectionError):
            sanitize_tool_args({"cmd": "false|| evil"})

    def test_empty_string_passes(self) -> None:
        result = sanitize_tool_args({"x": ""})
        assert result["x"] == ""

    def test_normal_pipe_char_in_text(self) -> None:
        # A lone pipe without trailing command is also caught
        # but pipe with space + word is injection
        with pytest.raises(ShellInjectionError):
            sanitize_tool_args({"cmd": "data| exploit"})
