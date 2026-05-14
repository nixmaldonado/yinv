"""Tests for `yinv skill install`.

Guards the install command's contract: default destination, --dest behaviors
(file vs directory), --print to stdout, overwrite protection with --force, and
that the bundled SKILL.md is reachable via importlib.resources (catches
wheel-packaging regressions where src/yinv/skill/ is excluded).
"""

from __future__ import annotations

from importlib import resources
from pathlib import Path

import pytest

from yinv.cli import main


@pytest.fixture
def home(tmp_path, monkeypatch):
    """Isolate HOME so we never touch the user's real ~/.claude."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    return home


class TestBundleReachable:
    """The skill file must be packaged inside the yinv wheel."""

    def test_skill_md_reachable_via_importlib_resources(self):
        ref = resources.files("yinv").joinpath("skill", "SKILL.md")
        # If the wheel ever stops bundling this file, .read_text() raises.
        content = ref.read_text(encoding="utf-8")
        assert "name: yinv-invoicing" in content
        assert content.startswith("---\n")


class TestDefaultInstall:
    def test_writes_to_claude_skills_dir(self, home, capsys):
        exit_code = main(["skill", "install"])

        assert exit_code == 0
        expected = home / ".claude" / "skills" / "yinv" / "SKILL.md"
        assert expected.exists()
        assert "name: yinv-invoicing" in expected.read_text(encoding="utf-8")

    def test_prints_destination_path(self, home, capsys):
        main(["skill", "install"])
        out = capsys.readouterr().out
        expected = home / ".claude" / "skills" / "yinv" / "SKILL.md"
        assert str(expected) in out

    def test_creates_parent_directories(self, home):
        # ~/.claude/skills/yinv/ does not exist beforehand.
        assert not (home / ".claude").exists()

        main(["skill", "install"])

        assert (home / ".claude" / "skills" / "yinv" / "SKILL.md").exists()


class TestDest:
    def test_dest_directory_writes_skill_md_inside(self, home, tmp_path):
        dest_dir = tmp_path / "custom"
        dest_dir.mkdir()

        exit_code = main(["skill", "install", "--dest", str(dest_dir)])

        assert exit_code == 0
        assert (dest_dir / "SKILL.md").exists()

    def test_dest_md_file_writes_to_exact_path(self, home, tmp_path):
        dest_file = tmp_path / "weird-name.md"

        exit_code = main(["skill", "install", "--dest", str(dest_file)])

        assert exit_code == 0
        assert dest_file.exists()
        assert "name: yinv-invoicing" in dest_file.read_text(encoding="utf-8")

    def test_dest_creates_missing_parent_dirs(self, home, tmp_path):
        dest = tmp_path / "deep" / "nested" / "path" / "SKILL.md"
        assert not dest.parent.exists()

        exit_code = main(["skill", "install", "--dest", str(dest)])

        assert exit_code == 0
        assert dest.exists()

    def test_dest_directory_when_path_does_not_exist(self, home, tmp_path):
        # Path without .md suffix is treated as a directory even if it doesn't
        # exist yet — parents are created.
        dest = tmp_path / "future-dir"

        exit_code = main(["skill", "install", "--dest", str(dest)])

        assert exit_code == 0
        assert (dest / "SKILL.md").exists()


class TestPrint:
    def test_print_writes_content_to_stdout(self, home, capsys):
        exit_code = main(["skill", "install", "--print"])

        assert exit_code == 0
        out = capsys.readouterr().out
        assert "name: yinv-invoicing" in out
        assert out.startswith("---\n")

    def test_print_does_not_write_any_file(self, home):
        main(["skill", "install", "--print"])
        # Default destination must NOT exist.
        assert not (home / ".claude").exists()

    def test_print_ignores_dest(self, home, tmp_path, capsys):
        dest = tmp_path / "should-not-be-written.md"

        main(["skill", "install", "--print", "--dest", str(dest)])

        assert not dest.exists()
        assert "name: yinv-invoicing" in capsys.readouterr().out


class TestOverwriteProtection:
    def test_refuses_to_overwrite_without_force(self, home, capsys):
        # Pre-create the file.
        dest = home / ".claude" / "skills" / "yinv" / "SKILL.md"
        dest.parent.mkdir(parents=True)
        dest.write_text("EXISTING", encoding="utf-8")

        exit_code = main(["skill", "install"])

        assert exit_code == 1
        err = capsys.readouterr().err
        assert "already exists" in err
        # File contents must be preserved.
        assert dest.read_text(encoding="utf-8") == "EXISTING"

    def test_force_overwrites_existing(self, home):
        dest = home / ".claude" / "skills" / "yinv" / "SKILL.md"
        dest.parent.mkdir(parents=True)
        dest.write_text("EXISTING", encoding="utf-8")

        exit_code = main(["skill", "install", "--force"])

        assert exit_code == 0
        assert dest.read_text(encoding="utf-8") != "EXISTING"
        assert "name: yinv-invoicing" in dest.read_text(encoding="utf-8")

    def test_dest_file_respects_overwrite_protection(self, home, tmp_path, capsys):
        dest = tmp_path / "preexisting.md"
        dest.write_text("KEEP ME", encoding="utf-8")

        exit_code = main(["skill", "install", "--dest", str(dest)])

        assert exit_code == 1
        assert "already exists" in capsys.readouterr().err
        assert dest.read_text(encoding="utf-8") == "KEEP ME"
