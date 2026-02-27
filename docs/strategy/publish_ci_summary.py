import argparse
import json
import os
from pathlib import Path


def _to_bool_string(value: bool) -> str:
    return str(bool(value)).lower()


def _build_summary(
    title: str,
    triggered: bool,
    report: dict | None,
    reason: str | None,
    path_filter_name: str | None,
    path_filter_matched: bool | None,
    path_filter_matched_count: int | None,
) -> list[str]:
    lines = [f"## {title}", "", f"- Triggered: `{_to_bool_string(triggered)}`"]

    if path_filter_name:
        lines.append(f"- Path Filter: `{path_filter_name}`")
    if path_filter_matched is not None:
        lines.append(f"- Path Filter Matched: `{_to_bool_string(path_filter_matched)}`")
    if path_filter_matched_count is not None:
        lines.append(f"- Path Filter Matched Count: `{path_filter_matched_count}`")

    if reason:
        lines.append(f"- Reason: {reason}")

    if report is None:
        return lines

    lines.extend(
        [
            f"- all_checks_valid: `{_to_bool_string(report.get('all_checks_valid', False))}`",
            f"- schema_valid: `{_to_bool_string(report.get('schema_valid', False))}`",
            f"- score_math_valid: `{_to_bool_string(report.get('score_math_valid', False))}`",
            f"- traceability_ok: `{_to_bool_string(report.get('traceability_ok', False))}`",
            f"- freshness_ok: `{_to_bool_string(report.get('freshness_ok', False))}`",
            f"- freshness_warnings: `{len(report.get('freshness_warnings', []))}`",
            f"- freshness_violations: `{len(report.get('freshness_violations', []))}`",
            f"- validator_version: `{report.get('validator_version', 'unknown')}`",
        ]
    )

    return lines


def _read_json_with_fallback(path: Path) -> dict:
    encodings = ["utf-8", "utf-8-sig", "utf-16"]
    last_error = None
    for encoding in encodings:
        try:
            return json.loads(path.read_text(encoding=encoding))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            last_error = exc
    raise ValueError(f"Unable to parse JSON report at {path}: {last_error}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Publish strategy CI summary to GITHUB_STEP_SUMMARY.")
    parser.add_argument("--title", required=True, help="Summary title")
    parser.add_argument("--triggered", required=True, choices=["true", "false"], help="Whether checks were triggered")
    parser.add_argument("--report", required=False, help="Path to validator JSON report")
    parser.add_argument("--reason", required=False, help="Optional reason for skip or context")
    parser.add_argument("--path-filter-name", required=False, help="Optional path-filter key name")
    parser.add_argument(
        "--path-filter-matched",
        required=False,
        choices=["true", "false"],
        help="Optional path-filter match result",
    )
    parser.add_argument(
        "--path-filter-matched-count",
        required=False,
        type=int,
        help="Optional path-filter matched file count",
    )
    args = parser.parse_args()

    triggered = args.triggered == "true"
    path_filter_matched = None
    if args.path_filter_matched is not None:
        path_filter_matched = args.path_filter_matched == "true"
    report = None

    if args.report:
        report = _read_json_with_fallback(Path(args.report))

    summary_lines = _build_summary(
        args.title,
        triggered,
        report,
        args.reason,
        args.path_filter_name,
        path_filter_matched,
        args.path_filter_matched_count,
    )
    summary_text = "\n".join(summary_lines) + "\n"

    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as file:
            file.write(summary_text)
    else:
        print(summary_text)


if __name__ == "__main__":
    main()
