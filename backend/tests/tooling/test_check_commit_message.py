import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).parents[2] / "scripts" / "check_commit_message.py"


def test_accepts_a_conventional_commit_message(tmp_path: Path) -> None:
    message_file = tmp_path / "COMMIT_EDITMSG"
    message_file.write_text("feat: add event search\n", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(message_file)],
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode == 0


def test_accepts_an_optional_scope(tmp_path: Path) -> None:
    message_file = tmp_path / "COMMIT_EDITMSG"
    message_file.write_text(
        "feat(events): add event search\n", encoding="utf-8"
    )

    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(message_file)],
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode == 0


def test_accepts_a_breaking_change_marker(tmp_path: Path) -> None:
    message_file = tmp_path / "COMMIT_EDITMSG"
    message_file.write_text(
        "feat(api)!: remove legacy endpoint\n", encoding="utf-8"
    )

    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(message_file)],
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode == 0


def test_rejects_a_nonconforming_header_with_guidance(tmp_path: Path) -> None:
    message_file = tmp_path / "COMMIT_EDITMSG"
    message_file.write_text("Add event search\n", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(message_file)],
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode == 1
    assert "<type>[optional scope][optional !]: <description>" in result.stderr
