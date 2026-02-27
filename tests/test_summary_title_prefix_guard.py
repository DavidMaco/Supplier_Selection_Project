import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GUARD_PATH = ROOT / "docs" / "strategy" / "check_summary_title_prefix.py"


def _make_workspace_temp_dir() -> Path:
    tests_dir = ROOT / "tests"
    path_str = tempfile.mkdtemp(prefix="summary_title_guard_", dir=str(tests_dir))
    return Path(path_str)


def _write_workflow(path: Path, title: str) -> None:
    content = """
jobs:
  demo:
    steps:
      - name: Publish
        run: |
          python docs/strategy/publish_ci_summary.py \\
            --title \"%s\" \\
            --triggered true
""" % title
    path.write_text(content, encoding="utf-8")


def _run_guard(workflow_path: Path, prefix: str = "Strategy CI |") -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            sys.executable,
            str(GUARD_PATH),
            "--workflow",
            str(workflow_path),
            "--prefix",
            prefix,
        ],
        capture_output=True,
        text=True,
        check=False,
    )


def test_summary_title_prefix_guard_passes_for_valid_prefix():
    work_dir = _make_workspace_temp_dir()
    workflow_path = work_dir / "ci.yml"
    _write_workflow(workflow_path, "Strategy CI | Fast Governance")

    try:
        result = _run_guard(workflow_path)
        assert result.returncode == 0
        payload = json.loads(result.stdout)
        assert payload["title_prefix_ok"] is True
        assert payload["violations"] == []
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


def test_summary_title_prefix_guard_fails_for_invalid_prefix():
    work_dir = _make_workspace_temp_dir()
    workflow_path = work_dir / "ci.yml"
    _write_workflow(workflow_path, "Strategy Validation Summary")

    try:
        result = _run_guard(workflow_path)
        assert result.returncode == 1
        payload = json.loads(result.stdout)
        assert payload["title_prefix_ok"] is False
        assert payload["violations"] == ["Strategy Validation Summary"]
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)
