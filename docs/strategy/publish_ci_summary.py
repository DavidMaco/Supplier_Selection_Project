import argparse
import json
import os
from pathlib import Path


def _to_bool_string(value: bool) -> str:
    return str(bool(value)).lower()


def _build_summary(title: str, triggered: bool, report: dict | None, reason: str | None) -> list[str]:
    lines = [f"## {title}", "", f"- Triggered: `{_to_bool_string(triggered)}`"]

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
    args = parser.parse_args()

    triggered = args.triggered == "true"
    report = None

    if args.report:
        report = _read_json_with_fallback(Path(args.report))

    summary_lines = _build_summary(args.title, triggered, report, args.reason)
    summary_text = "\n".join(summary_lines) + "\n"

    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as file:
            file.write(summary_text)
    else:
        print(summary_text)


if __name__ == "__main__":
    main()
