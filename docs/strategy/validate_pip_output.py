import argparse
import json
from pathlib import Path

VALIDATOR_VERSION = "1.2.0"


def _load_json(path: Path):
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def _round_half_up(value: float, decimals: int) -> float:
    multiplier = 10 ** decimals
    return int(value * multiplier + 0.5) / multiplier


def _status_from_score(score: float, investable: float, red_flag: float) -> str:
    if score >= investable:
        return "Investable"
    if score <= red_flag:
        return "Red Flag"
    return "Borderline"


def validate_scorecard(payload: dict, config: dict) -> dict:
    scorecard = payload.get("readiness_scorecard", {})
    dimensions = scorecard.get("dimensions", [])

    rounding_cfg = config.get("rounding", {})
    computed_decimals = int(rounding_cfg.get("computed_decimals", 2))
    declared_decimals = int(rounding_cfg.get("declared_decimals", 1))
    score_tolerance = float(rounding_cfg.get("score_tolerance", 0.5))

    total_weight = sum(item.get("weight", 0) for item in dimensions)
    weighted_sum = sum((item.get("weight", 0) * item.get("score", 0)) for item in dimensions)
    computed_score = (weighted_sum / total_weight) if total_weight else 0
    computed_score_rounded = _round_half_up(computed_score, computed_decimals)

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
        "computed_weighted_score": computed_score_rounded,
        "declared_score": _round_half_up(float(declared_score), declared_decimals),
        "score_close": abs(computed_score - declared_score) <= score_tolerance,
        "declared_status": declared_status,
        "expected_status": expected_status,
        "status_matches": declared_status == expected_status,
        "rounding_policy": {
            "computed_decimals": computed_decimals,
            "declared_decimals": declared_decimals,
            "score_tolerance": score_tolerance,
        },
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
    parser.add_argument("--config", required=False, help="Path to validator config JSON")
    args = parser.parse_args()

    input_path = Path(args.input)
    schema_path = Path(args.schema)

    payload = _load_json(input_path)
    schema = _load_json(schema_path)

    if args.config:
        config_path = Path(args.config)
    else:
        config_path = Path(__file__).parent / "validator-config.json"

    if config_path.exists():
        config = _load_json(config_path)
    else:
        config = {}

    schema_valid, schema_errors = validate_schema(payload, schema)
    score_results = validate_scorecard(payload, config)

    score_math_valid = score_results["total_weight_matches"] and score_results["score_close"] and score_results["status_matches"]

    result = {
        "schema_valid": schema_valid,
        "schema_errors": schema_errors,
        "score_math_valid": score_math_valid,
        "validator_version": VALIDATOR_VERSION,
        "config_path": str(config_path),
        **score_results,
    }

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
