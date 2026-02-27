import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest


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


def _write_text(path: Path, content: str, encoding: str) -> None:
    path.write_text(content, encoding=encoding)


def _assert_guard_summary_fields(summary_text: str, expected_fields: dict[str, str]) -> None:
    for field, value in expected_fields.items():
        assert f"{field}: `{value}`" in summary_text


def _assert_summary_title(summary_text: str, title: str) -> None:
    assert f"## {title}" in summary_text


def _assert_path_filter_fields(
    summary_text: str,
    name: str,
    matched: str,
    matched_count: str,
) -> None:
    assert f"Path Filter: `{name}`" in summary_text
    assert f"Path Filter Matched: `{matched}`" in summary_text
    assert f"Path Filter Matched Count: `{matched_count}`" in summary_text


EXPECTED_GUARD_FIELDS_DETAIL = {
    "title_prefix_ok": "false",
    "required_prefix": "Strategy CI |",
    "titles_checked_count": "2",
    "violations_count": "1",
    "guard_exit_code": "1",
    "guard_consistency_ok": "true",
    "violations": "Strategy Validation Summary",
}

EXPECTED_GUARD_FIELDS_MISMATCH = {
    "guard_consistency_ok": "false",
    "required_prefix": "Strategy CI |",
    "titles_checked_count": "1",
    "violations_count": "0",
    "guard_exit_code": "1",
}

EXPECTED_GUARD_FIELDS_POSITIVE = {
    "guard_consistency_ok": "true",
    "required_prefix": "Strategy CI |",
    "titles_checked_count": "1",
    "violations_count": "0",
    "guard_exit_code": "0",
}

EXPECTED_PATH_FILTER_FIELDS_SKIPPED = {
    "name": "strategy",
    "matched": "false",
    "matched_count": "0",
}

EXPECTED_PATH_FILTER_FIELDS_POSITIVE = {
    "name": "strategy",
    "matched": "true",
    "matched_count": "3",
}

EXPECTED_PATH_FILTER_FIELDS_MISMATCH = {
    "name": "summary",
    "matched": "false",
    "matched_count": "0",
}

SUMMARY_TEXT_PATH_FILTER_POSITIVE = (
    "- Path Filter: `strategy`\n"
    "- Path Filter Matched: `true`\n"
    "- Path Filter Matched Count: `3`\n"
)


def test_build_summary_includes_reason_when_report_missing():
    lines, guard_consistency_ok = publish_ci_summary._build_summary(
        title="Strategy Governance Fast Summary",
        triggered=False,
        report=None,
        guard_report=None,
        guard_exit_code=None,
        reason="no matching strategy governance paths changed",
        path_filter_name="strategy",
        path_filter_matched=False,
        path_filter_matched_count=0,
    )
    text = "\n".join(lines)
    assert "Triggered: `false`" in text
    _assert_path_filter_fields(text, **EXPECTED_PATH_FILTER_FIELDS_SKIPPED)
    assert "Reason: no matching strategy governance paths changed" in text
    assert guard_consistency_ok is None


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


@pytest.mark.parametrize(
    ("title", "should_raise"),
    [
        ("Strategy CI | Fast Governance", True),
        ("Strategy CI | Validation", False),
    ],
)
def test_assert_summary_title(title: str, should_raise: bool):
    summary_text = "## Strategy CI | Validation\n"
    if should_raise:
        with pytest.raises(AssertionError):
            _assert_summary_title(summary_text, title)
        return
    _assert_summary_title(summary_text, title)


@pytest.mark.parametrize(
    ("expected_fields", "should_raise"),
    [
        (EXPECTED_PATH_FILTER_FIELDS_MISMATCH, True),
        (EXPECTED_PATH_FILTER_FIELDS_POSITIVE, False),
    ],
)
def test_assert_path_filter_fields(expected_fields: dict[str, str], should_raise: bool):
    summary_text = SUMMARY_TEXT_PATH_FILTER_POSITIVE
    if should_raise:
        with pytest.raises(AssertionError):
            _assert_path_filter_fields(summary_text, **expected_fields)
        return
    _assert_path_filter_fields(summary_text, **expected_fields)


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
                "--path-filter-name",
                "strategy",
                "--path-filter-matched",
                "true",
                "--path-filter-matched-count",
                "3",
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
        _assert_summary_title(summary_text, "Strategy Validation Summary")
        _assert_path_filter_fields(summary_text, **EXPECTED_PATH_FILTER_FIELDS_POSITIVE)
        assert "all_checks_valid: `true`" in summary_text
        assert "validator_version: `1.7.0`" in summary_text
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


def test_build_summary_includes_guard_report_details():
    lines, guard_consistency_ok = publish_ci_summary._build_summary(
        title="Strategy CI | Summary Title Guard",
        triggered=True,
        report=None,
        guard_report={
            "title_prefix_ok": False,
            "required_prefix": "Strategy CI |",
            "titles_checked": ["Strategy CI | Fast Governance", "Strategy Validation Summary"],
            "violations": ["Strategy Validation Summary"],
        },
        guard_exit_code=1,
        reason="summary title prefix governance check",
        path_filter_name="summary",
        path_filter_matched=True,
        path_filter_matched_count=2,
    )

    text = "\n".join(lines)
    _assert_guard_summary_fields(text, EXPECTED_GUARD_FIELDS_DETAIL)
    assert guard_consistency_ok is True


def test_script_enforces_guard_consistency_and_exits_nonzero_on_mismatch():
    work_dir = _make_workspace_temp_dir()
    guard_report_path = work_dir / "guard-report.json"
    summary_path = work_dir / "summary.md"

    try:
        _write_json(
            guard_report_path,
            {
                "title_prefix_ok": True,
                "required_prefix": "Strategy CI |",
                "titles_checked": ["Strategy CI | Validation"],
                "violations": [],
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
                "Strategy CI | Summary Title Guard",
                "--triggered",
                "true",
                "--guard-report",
                str(guard_report_path),
                "--guard-exit-code",
                "1",
                "--enforce-guard-consistency",
                "true",
            ],
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )

        assert result.returncode != 0
        assert "Guard consistency check failed" in result.stderr

        summary_text = summary_path.read_text(encoding="utf-8")
        _assert_summary_title(summary_text, "Strategy CI | Summary Title Guard")
        _assert_guard_summary_fields(summary_text, EXPECTED_GUARD_FIELDS_MISMATCH)
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


def test_script_enforces_guard_consistency_and_succeeds_on_match():
    work_dir = _make_workspace_temp_dir()
    guard_report_path = work_dir / "guard-report.json"
    summary_path = work_dir / "summary.md"

    try:
        _write_json(
            guard_report_path,
            {
                "title_prefix_ok": True,
                "required_prefix": "Strategy CI |",
                "titles_checked": ["Strategy CI | Validation"],
                "violations": [],
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
                "Strategy CI | Summary Title Guard",
                "--triggered",
                "true",
                "--guard-report",
                str(guard_report_path),
                "--guard-exit-code",
                "0",
                "--enforce-guard-consistency",
                "true",
            ],
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )

        assert result.returncode == 0

        summary_text = summary_path.read_text(encoding="utf-8")
        _assert_summary_title(summary_text, "Strategy CI | Summary Title Guard")
        _assert_guard_summary_fields(summary_text, EXPECTED_GUARD_FIELDS_POSITIVE)
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


def test_read_json_with_fallback_raises_on_invalid_json():
    work_dir = _make_workspace_temp_dir()
    invalid_path = work_dir / "invalid.json"

    try:
        _write_text(invalid_path, "not valid json", "utf-8")
        try:
            publish_ci_summary._read_json_with_fallback(invalid_path)
            assert False, "Expected ValueError for invalid JSON"
        except ValueError as exc:
            assert "Unable to parse JSON report" in str(exc)
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


def test_script_exits_nonzero_on_invalid_report_json():
    work_dir = _make_workspace_temp_dir()
    invalid_path = work_dir / "invalid.json"

    try:
        _write_text(invalid_path, "{invalid_json", "utf-8")

        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT_PATH),
                "--title",
                "Strategy Validation Summary",
                "--triggered",
                "true",
                "--report",
                str(invalid_path),
            ],
            capture_output=True,
            text=True,
            check=False,
        )

        assert result.returncode != 0
        assert "Unable to parse JSON report" in result.stderr
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)
