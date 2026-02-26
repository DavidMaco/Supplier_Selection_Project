import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


def sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(8192), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8-sig") as file:
        return json.load(file)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate reproducibility manifest for a candidate evaluation run.")
    parser.add_argument("--candidate", required=True, help="Path to candidate JSON")
    parser.add_argument("--schema", required=True, help="Path to schema JSON")
    parser.add_argument("--config", required=True, help="Path to validator config JSON")
    parser.add_argument("--validation", required=True, help="Path to validator output JSON")
    parser.add_argument("--output", required=True, help="Path to output manifest JSON")
    args = parser.parse_args()

    candidate_path = Path(args.candidate)
    schema_path = Path(args.schema)
    config_path = Path(args.config)
    validation_path = Path(args.validation)
    output_path = Path(args.output)

    validation = load_json(validation_path)

    manifest = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "artifacts": {
            "candidate_path": str(candidate_path),
            "candidate_sha256": sha256_file(candidate_path),
            "schema_path": str(schema_path),
            "schema_sha256": sha256_file(schema_path),
            "config_path": str(config_path),
            "config_sha256": sha256_file(config_path),
            "validation_path": str(validation_path),
            "validation_sha256": sha256_file(validation_path),
        },
        "validator": {
            "version": validation.get("validator_version", "unknown"),
            "config_path_reported": validation.get("config_path", ""),
            "rounding_policy": validation.get("rounding_policy", {}),
        },
        "result_summary": {
            "schema_valid": validation.get("schema_valid"),
            "score_math_valid": validation.get("score_math_valid"),
            "computed_weighted_score": validation.get("computed_weighted_score"),
            "declared_score": validation.get("declared_score"),
            "declared_status": validation.get("declared_status"),
            "expected_status": validation.get("expected_status"),
        },
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as file:
        json.dump(manifest, file, indent=2)


if __name__ == "__main__":
    main()
