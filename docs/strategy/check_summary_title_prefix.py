import argparse
import re
import sys
from pathlib import Path


TITLE_PATTERN = re.compile(r'--title\s+"([^"]+)"')


def _extract_publish_title_lines(ci_yaml_text: str) -> list[str]:
    lines = ci_yaml_text.splitlines()
    publish_titles: list[str] = []
    in_publish_block = False

    for raw_line in lines:
        line = raw_line.strip()

        if line.startswith("python docs/strategy/publish_ci_summary.py"):
            in_publish_block = True
            continue

        if in_publish_block:
            if line.startswith("--"):
                match = TITLE_PATTERN.search(line)
                if match:
                    publish_titles.append(match.group(1))
            else:
                in_publish_block = False

    return publish_titles


def _check_title_prefix(titles: list[str], required_prefix: str) -> list[str]:
    violations = []
    for title in titles:
        if not title.startswith(required_prefix):
            violations.append(title)
    return violations


def main() -> None:
    parser = argparse.ArgumentParser(description="Check publish_ci_summary.py title prefixes in workflow.")
    parser.add_argument("--workflow", required=True, help="Path to workflow YAML file")
    parser.add_argument("--prefix", default="Strategy CI |", help="Required title prefix")
    args = parser.parse_args()

    workflow_path = Path(args.workflow)
    content = workflow_path.read_text(encoding="utf-8")
    titles = _extract_publish_title_lines(content)
    violations = _check_title_prefix(titles, args.prefix)

    result = {
        "title_prefix_ok": len(violations) == 0,
        "required_prefix": args.prefix,
        "titles_checked": titles,
        "violations": violations,
    }

    import json

    print(json.dumps(result, indent=2))

    if violations:
        sys.exit(1)


if __name__ == "__main__":
    main()
