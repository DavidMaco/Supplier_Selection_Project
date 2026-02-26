import argparse
import json
import re
from datetime import date
from pathlib import Path

VALIDATOR_VERSION = "1.7.0"


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


def _extract_risk_ids(payload: dict) -> set[str]:
    risk_ids = set()
    for row in payload.get("risk_register", []):
        risk_text = str(row.get("risk", ""))
        match = re.match(r"(R\d+):", risk_text)
        if match:
            risk_ids.add(match.group(1))
    return risk_ids


def _max_age_for_source_type(trace_cfg: dict, source_type: str, default_max_age: int) -> int:
    mapping = trace_cfg.get("source_type_max_age_days", {})
    value = mapping.get(source_type)
    try:
        return int(value) if value is not None else default_max_age
    except (TypeError, ValueError):
        return default_max_age


def _max_age_for_evidence_prefix(trace_cfg: dict, prefix: str, default_max_age: int) -> int:
    mapping = trace_cfg.get("evidence_prefix_max_age_days", {})
    value = mapping.get(prefix)
    try:
        return int(value) if value is not None else default_max_age
    except (TypeError, ValueError):
        return default_max_age


def validate_traceability(payload: dict, config: dict) -> dict:
    trace_cfg = config.get("traceability", {})
    source_tag_pattern = re.compile(trace_cfg.get("source_tag_pattern", r"SourceTag=[A-Za-z]+:[A-Za-z0-9\-]+"))
    evidence_id_pattern = re.compile(trace_cfg.get("evidence_id_pattern", r"EvidenceID=[A-Z]{2}-\d{2}"))
    data_as_of_pattern = re.compile(trace_cfg.get("data_as_of_pattern", r"DataAsOf=\d{4}-\d{2}-\d{2}"))

    strict_source_tags = bool(trace_cfg.get("strict_source_tags", False))
    strict_evidence_ids = bool(trace_cfg.get("strict_evidence_ids", False))
    strict_risk_linkage = bool(trace_cfg.get("strict_risk_linkage", False))
    strict_freshness = bool(trace_cfg.get("strict_freshness", False))
    strict_source_type_enum = bool(trace_cfg.get("strict_source_type_enum", False))
    strict_evidence_prefix_enum = bool(trace_cfg.get("strict_evidence_prefix_enum", False))
    max_age_days = int(trace_cfg.get("max_age_days", 365))
    warning_window_days = int(trace_cfg.get("freshness_warning_window_days", 30))
    allowed_source_types = set(trace_cfg.get("allowed_source_types", []))
    allowed_evidence_prefixes = set(trace_cfg.get("allowed_evidence_prefixes", []))

    source_tag_violations = []
    source_type_violations = []
    evidence_id_violations = []
    evidence_prefix_violations = []
    risk_linkage_violations = []
    freshness_violations = []
    freshness_warnings = []
    freshness_diagnostics = []

    context_date_raw = str(payload.get("meta", {}).get("date_context", ""))
    try:
        context_date = date.fromisoformat(context_date_raw)
    except ValueError:
        context_date = None
        freshness_violations.append("meta.date_context is missing/invalid for freshness checks")

    for idx, row in enumerate(payload.get("differentiation_strategy", {}).get("competitor_matrix", []), start=1):
        proof = str(row.get("proof", ""))
        if not source_tag_pattern.search(proof):
            source_tag_violations.append(f"competitor_matrix[{idx}].proof missing/invalid SourceTag")

        source_type = ""
        source_match = re.search(r"SourceTag=([A-Za-z]+):[A-Za-z0-9\-]+", proof)
        if source_match:
            source_type = source_match.group(1)
        if source_type and strict_source_type_enum and source_type not in allowed_source_types:
            source_type_violations.append(
                f"competitor_matrix[{idx}].proof SourceTag type not allowed: {source_type}"
            )
        max_age_for_item = _max_age_for_source_type(trace_cfg, source_type, max_age_days)

        data_as_of_match = data_as_of_pattern.search(proof)
        if not data_as_of_match:
            freshness_violations.append(f"competitor_matrix[{idx}].proof missing DataAsOf")
        elif context_date is not None:
            data_as_of_raw = data_as_of_match.group(0).split("=", 1)[1]
            try:
                data_as_of_date = date.fromisoformat(data_as_of_raw)
                age_days = (context_date - data_as_of_date).days
                freshness_diagnostics.append({
                    "field": f"competitor_matrix[{idx}].proof",
                    "policy_type": "source_type" if source_type else "fallback",
                    "policy_key": source_type if source_type else "global",
                    "max_age_days": max_age_for_item,
                    "age_days": age_days,
                })
                if age_days < 0:
                    freshness_violations.append(
                        f"competitor_matrix[{idx}].proof DataAsOf is in the future"
                    )
                elif age_days > max_age_for_item:
                    freshness_violations.append(
                        f"competitor_matrix[{idx}].proof DataAsOf exceeds max age ({age_days}>{max_age_for_item} days)"
                    )
                elif age_days >= max(0, max_age_for_item - warning_window_days):
                    freshness_warnings.append(
                        f"competitor_matrix[{idx}].proof DataAsOf nearing max age ({age_days}/{max_age_for_item} days)"
                    )
            except ValueError:
                freshness_violations.append(f"competitor_matrix[{idx}].proof has invalid DataAsOf date")

    for idx, row in enumerate(payload.get("readiness_scorecard", {}).get("dimensions", []), start=1):
        evidence = str(row.get("evidence", ""))
        if not evidence_id_pattern.search(evidence):
            evidence_id_violations.append(f"readiness_scorecard.dimensions[{idx}].evidence missing/invalid EvidenceID")

        evidence_prefix = ""
        evidence_match = re.search(r"EvidenceID=([A-Z]{2})-\d{2}", evidence)
        if evidence_match:
            evidence_prefix = evidence_match.group(1)
        if evidence_prefix and strict_evidence_prefix_enum and evidence_prefix not in allowed_evidence_prefixes:
            evidence_prefix_violations.append(
                f"readiness_scorecard.dimensions[{idx}].evidence prefix not allowed: {evidence_prefix}"
            )
        max_age_for_item = _max_age_for_evidence_prefix(trace_cfg, evidence_prefix, max_age_days)

        data_as_of_match = data_as_of_pattern.search(evidence)
        if not data_as_of_match:
            freshness_violations.append(f"readiness_scorecard.dimensions[{idx}].evidence missing DataAsOf")
        elif context_date is not None:
            data_as_of_raw = data_as_of_match.group(0).split("=", 1)[1]
            try:
                data_as_of_date = date.fromisoformat(data_as_of_raw)
                age_days = (context_date - data_as_of_date).days
                freshness_diagnostics.append({
                    "field": f"readiness_scorecard.dimensions[{idx}].evidence",
                    "policy_type": "evidence_prefix" if evidence_prefix else "fallback",
                    "policy_key": evidence_prefix if evidence_prefix else "global",
                    "max_age_days": max_age_for_item,
                    "age_days": age_days,
                })
                if age_days < 0:
                    freshness_violations.append(
                        f"readiness_scorecard.dimensions[{idx}].evidence DataAsOf is in the future"
                    )
                elif age_days > max_age_for_item:
                    freshness_violations.append(
                        f"readiness_scorecard.dimensions[{idx}].evidence DataAsOf exceeds max age ({age_days}>{max_age_for_item} days)"
                    )
                elif age_days >= max(0, max_age_for_item - warning_window_days):
                    freshness_warnings.append(
                        f"readiness_scorecard.dimensions[{idx}].evidence DataAsOf nearing max age ({age_days}/{max_age_for_item} days)"
                    )
            except ValueError:
                freshness_violations.append(
                    f"readiness_scorecard.dimensions[{idx}].evidence has invalid DataAsOf date"
                )

    valid_risk_ids = _extract_risk_ids(payload)
    riskids_pattern = re.compile(r"\[RiskIDs=([A-Z0-9,]+)\]")
    for idx, row in enumerate(payload.get("next_actions", []), start=1):
        expected_outcome = str(row.get("expected_outcome", ""))
        match = riskids_pattern.search(expected_outcome)
        if not match:
            risk_linkage_violations.append(f"next_actions[{idx}] missing RiskIDs tag")
            continue
        listed_ids = [item.strip() for item in match.group(1).split(",") if item.strip()]
        unknown_ids = [item for item in listed_ids if item not in valid_risk_ids]
        if unknown_ids:
            risk_linkage_violations.append(
                f"next_actions[{idx}] contains unknown RiskIDs: {', '.join(unknown_ids)}"
            )

    source_tag_ok = len(source_tag_violations) == 0
    source_type_ok = len(source_type_violations) == 0
    evidence_id_ok = len(evidence_id_violations) == 0
    evidence_prefix_ok = len(evidence_prefix_violations) == 0
    risk_linkage_ok = len(risk_linkage_violations) == 0
    freshness_ok = len(freshness_violations) == 0

    traceability_ok = True
    if strict_source_tags and not source_tag_ok:
        traceability_ok = False
    if strict_source_type_enum and not source_type_ok:
        traceability_ok = False
    if strict_evidence_ids and not evidence_id_ok:
        traceability_ok = False
    if strict_evidence_prefix_enum and not evidence_prefix_ok:
        traceability_ok = False
    if strict_risk_linkage and not risk_linkage_ok:
        traceability_ok = False
    if strict_freshness and not freshness_ok:
        traceability_ok = False

    return {
        "traceability_ok": traceability_ok,
        "source_tag_ok": source_tag_ok,
        "source_type_ok": source_type_ok,
        "evidence_id_ok": evidence_id_ok,
        "evidence_prefix_ok": evidence_prefix_ok,
        "risk_linkage_ok": risk_linkage_ok,
        "freshness_ok": freshness_ok,
        "source_tag_violations": source_tag_violations,
        "source_type_violations": source_type_violations,
        "evidence_id_violations": evidence_id_violations,
        "evidence_prefix_violations": evidence_prefix_violations,
        "risk_linkage_violations": risk_linkage_violations,
        "freshness_violations": freshness_violations,
        "freshness_warnings": freshness_warnings,
        "freshness_diagnostics": freshness_diagnostics,
    }


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
    traceability_results = validate_traceability(payload, config)

    score_math_valid = score_results["total_weight_matches"] and score_results["score_close"] and score_results["status_matches"]
    all_checks_valid = schema_valid and score_math_valid and traceability_results["traceability_ok"]

    result = {
        "schema_valid": schema_valid,
        "schema_errors": schema_errors,
        "score_math_valid": score_math_valid,
        "all_checks_valid": all_checks_valid,
        "validator_version": VALIDATOR_VERSION,
        "config_path": str(config_path),
        **score_results,
        **traceability_results,
    }

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
