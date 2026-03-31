"""测试工具系统"""

import os
import tempfile
from pathlib import Path

import pytest

from goaldriveclaude.tools.code_analysis import grep_search
from goaldriveclaude.tools.filesystem import (
    edit_file,
    find_files,
    list_directory,
    read_file,
    write_file,
)
from goaldriveclaude.tools.shell import run_bash
from goaldriveclaude.tools.verification import check_file_exists, compare_output


class TestFilesystem:
    """测试文件系统工具"""

    def test_write_and_read_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.txt"
            content = "Hello, World!"

            # 测试写入
            result = write_file(str(test_file), content)
            assert result["success"] is True
            assert test_file.exists()

            # 测试读取
            result = read_file(str(test_file))
            assert result["success"] is True
            assert content in result["output"]

    def test_read_file_not_found(self):
        result = read_file("/nonexistent/file.txt")
        assert result["success"] is False
        assert "不存在" in result["error"] or "not found" in result["error"].lower()

    def test_edit_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.txt"
            write_file(str(test_file), "Hello, World!")

            result = edit_file(str(test_file), "World", "Universe")
            assert result["success"] is True

            content = read_file(str(test_file))
            assert "Hello, Universe!" in content["output"]

    def test_list_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # 创建一些文件
            (Path(tmpdir) / "file1.txt").touch()
            (Path(tmpdir) / "file2.txt").touch()
            (Path(tmpdir) / "subdir").mkdir()

            result = list_directory(tmpdir)
            assert result["success"] is True
            assert "file1.txt" in result["output"]
            assert "file2.txt" in result["output"]
            assert "subdir" in result["output"]


class TestShell:
    """测试 Shell 工具"""

    def test_run_bash_success(self):
        result = run_bash("echo hello")
        assert result["success"] is True
        assert "hello" in result["output"]

    def test_run_bash_failure(self):
        result = run_bash("exit 1")
        assert result["success"] is False

    def test_run_bash_blocked(self):
        result = run_bash("rm -rf /")
        assert result["success"] is False
        assert "阻止" in result["error"] or "blocked" in result["error"].lower()


class TestCodeAnalysis:
    """测试代码分析工具"""

    def test_grep_search(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            write_file(str(test_file), "def hello():\n    return 'world'")

            result = grep_search("hello", tmpdir)
            assert result["success"] is True
            assert "hello" in result["output"]


class TestVerification:
    """测试验证工具"""

    def test_check_file_exists(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.txt"
            test_file.touch()

            result = check_file_exists(str(test_file))
            assert result["success"] is True

    def test_check_file_not_exists(self):
        result = check_file_exists("/nonexistent/file.txt")
        assert result["success"] is False

    def test_compare_output(self):
        result = compare_output("echo hello", ["hello"])
        assert result["success"] is True

    def test_compare_output_fail(self):
        result = compare_output("echo hello", ["world"])
        assert result["success"] is False
