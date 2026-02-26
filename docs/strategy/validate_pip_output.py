import argparse
import json
from pathlib import Path


def _load_json(path: Path):
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def _status_from_score(score: float, investable: float, red_flag: float) -> str:
    if score >= investable:
        return "Investable"
    if score <= red_flag:
        return "Red Flag"
    return "Borderline"


def validate_scorecard(payload: dict) -> dict:
    scorecard = payload.get("readiness_scorecard", {})
    dimensions = scorecard.get("dimensions", [])

    total_weight = sum(item.get("weight", 0) for item in dimensions)
    weighted_sum = sum((item.get("weight", 0) * item.get("score", 0)) for item in dimensions)
    computed_score = (weighted_sum / total_weight) if total_weight else 0

    declared_total_weight = scorecard.get("total_weight", 0)
    declared_score = scorecard.get("current_score", 0)
    investable_threshold = scorecard.get("investable_threshold", 80)
    red_flag_threshold = scorecard.get("red_flag_threshold", 60)
    declared_status = scorecard.get("status", "Borderline")
    expected_status = _status_from_score(computed_score, investable_threshold, red_flag_threshold)

    return {
        "total_weight_matches": abs(total_weight - declared_total_weight) < 1e-9,
        "computed_total_weight": total_weight,
        "declared_total_weight": declared_total_weight,
        "computed_weighted_score": round(computed_score, 4),
        "declared_score": declared_score,
        "score_close": abs(computed_score - declared_score) <= 0.5,
        "declared_status": declared_status,
        "expected_status": expected_status,
        "status_matches": declared_status == expected_status,
    }


def validate_schema(payload: dict, schema: dict) -> tuple[bool, list[str]]:
    try:
        import jsonschema
    except ImportError:
        return False, ["Missing dependency: jsonschema. Install with 'pip install jsonschema'."]

    validator = jsonschema.Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(payload), key=lambda error: list(error.path))
    if not errors:
        return True, []

    schema_errors = []
    for error in errors:
        location = ".".join(str(part) for part in error.path)
        schema_errors.append(f"{location}: {error.message}" if location else error.message)
    return False, schema_errors


def main():
    parser = argparse.ArgumentParser(description="Validate PIP Gold output against schema and scorecard logic.")
    parser.add_argument("--input", required=True, help="Path to candidate output JSON")
    parser.add_argument("--schema", required=True, help="Path to schema JSON")
    args = parser.parse_args()

    input_path = Path(args.input)
    schema_path = Path(args.schema)

    payload = _load_json(input_path)
    schema = _load_json(schema_path)

    schema_valid, schema_errors = validate_schema(payload, schema)
    score_results = validate_scorecard(payload)

    score_math_valid = score_results["total_weight_matches"] and score_results["score_close"] and score_results["status_matches"]

    result = {
        "schema_valid": schema_valid,
        "schema_errors": schema_errors,
        "score_math_valid": score_math_valid,
        **score_results,
    }

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
