import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "docs" / "strategy" / "publish_ci_summary.py"

spec = importlib.util.spec_from_file_location("publish_ci_summary", SCRIPT_PATH)
publish_ci_summary = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(publish_ci_summary)


def _make_workspace_temp_dir() -> Path:
    tests_dir = ROOT / "tests"
    path_str = tempfile.mkdtemp(prefix="summary_script_", dir=str(tests_dir))
    return Path(path_str)


def _write_json(path: Path, payload: dict, encoding: str) -> None:
    path.write_text(json.dumps(payload), encoding=encoding)


def test_build_summary_includes_reason_when_report_missing():
    lines = publish_ci_summary._build_summary(
        title="Strategy Governance Fast Summary",
        triggered=False,
        report=None,
        reason="no matching strategy governance paths changed",
    )
    text = "\n".join(lines)
    assert "Triggered: `false`" in text
    assert "Reason: no matching strategy governance paths changed" in text


def test_read_json_with_fallback_supports_utf8_sig_and_utf16():
    work_dir = _make_workspace_temp_dir()
    payload = {"all_checks_valid": True, "validator_version": "1.7.0"}
    utf8sig_path = work_dir / "report_utf8sig.json"
    utf16_path = work_dir / "report_utf16.json"

    try:
        _write_json(utf8sig_path, payload, "utf-8-sig")
        _write_json(utf16_path, payload, "utf-16")

        parsed_utf8sig = publish_ci_summary._read_json_with_fallback(utf8sig_path)
        parsed_utf16 = publish_ci_summary._read_json_with_fallback(utf16_path)

        assert parsed_utf8sig["all_checks_valid"] is True
        assert parsed_utf16["validator_version"] == "1.7.0"
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


def test_script_writes_to_github_step_summary_file():
    work_dir = _make_workspace_temp_dir()
    report_path = work_dir / "report.json"
    summary_path = work_dir / "summary.md"

    try:
        _write_json(
            report_path,
            {
                "all_checks_valid": True,
                "schema_valid": True,
                "score_math_valid": True,
                "traceability_ok": True,
                "freshness_ok": True,
                "freshness_warnings": [],
                "freshness_violations": [],
                "validator_version": "1.7.0",
            },
            "utf-8",
        )

        env = os.environ.copy()
        env["GITHUB_STEP_SUMMARY"] = str(summary_path)

        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT_PATH),
                "--title",
                "Strategy Validation Summary",
                "--triggered",
                "true",
                "--report",
                str(report_path),
            ],
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )

        assert result.returncode == 0
        summary_text = summary_path.read_text(encoding="utf-8")
        assert "## Strategy Validation Summary" in summary_text
        assert "all_checks_valid: `true`" in summary_text
        assert "validator_version: `1.7.0`" in summary_text
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)
