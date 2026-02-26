import argparse
import json
import re
import sys
from pathlib import Path


def _load_json(path: Path):
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def _extract_source_types(payload: dict) -> set[str]:
    result = set()
    for row in payload.get("differentiation_strategy", {}).get("competitor_matrix", []):
        proof = str(row.get("proof", ""))
        match = re.search(r"SourceTag=([A-Za-z]+):[A-Za-z0-9\-]+", proof)
        if match:
            result.add(match.group(1))
    return result


def _extract_evidence_prefixes(payload: dict) -> set[str]:
    result = set()
    for row in payload.get("readiness_scorecard", {}).get("dimensions", []):
        evidence = str(row.get("evidence", ""))
        match = re.search(r"EvidenceID=([A-Z]{2})-\d{2}", evidence)
        if match:
            result.add(match.group(1))
    return result


def main():
    parser = argparse.ArgumentParser(description="Check traceability policy drift between candidate evidence tags and validator config.")
    parser.add_argument("--candidate", required=True, help="Path to candidate JSON")
    parser.add_argument("--config", required=True, help="Path to validator config JSON")
    args = parser.parse_args()

    payload = _load_json(Path(args.candidate))
    config = _load_json(Path(args.config))

    trace_cfg = config.get("traceability", {})

    allowed_source_types = set(trace_cfg.get("allowed_source_types", []))
    source_type_max_age_days = set(trace_cfg.get("source_type_max_age_days", {}).keys())

    allowed_evidence_prefixes = set(trace_cfg.get("allowed_evidence_prefixes", []))
    evidence_prefix_max_age_days = set(trace_cfg.get("evidence_prefix_max_age_days", {}).keys())

    candidate_source_types = _extract_source_types(payload)
    candidate_evidence_prefixes = _extract_evidence_prefixes(payload)

    violations = []

    missing_source_mapping = allowed_source_types - source_type_max_age_days
    if missing_source_mapping:
        violations.append(
            f"allowed_source_types missing max-age mapping: {', '.join(sorted(missing_source_mapping))}"
        )

    orphan_source_mapping = source_type_max_age_days - allowed_source_types
    if orphan_source_mapping:
        violations.append(
            f"source_type_max_age_days contains unmapped source types: {', '.join(sorted(orphan_source_mapping))}"
        )

    missing_evidence_mapping = allowed_evidence_prefixes - evidence_prefix_max_age_days
    if missing_evidence_mapping:
        violations.append(
            f"allowed_evidence_prefixes missing max-age mapping: {', '.join(sorted(missing_evidence_mapping))}"
        )

    orphan_evidence_mapping = evidence_prefix_max_age_days - allowed_evidence_prefixes
    if orphan_evidence_mapping:
        violations.append(
            f"evidence_prefix_max_age_days contains unmapped prefixes: {', '.join(sorted(orphan_evidence_mapping))}"
        )

    unknown_candidate_source_types = candidate_source_types - allowed_source_types
    if unknown_candidate_source_types:
        violations.append(
            f"candidate uses source types not in allowed_source_types: {', '.join(sorted(unknown_candidate_source_types))}"
        )

    unknown_candidate_evidence_prefixes = candidate_evidence_prefixes - allowed_evidence_prefixes
    if unknown_candidate_evidence_prefixes:
        violations.append(
            f"candidate uses evidence prefixes not in allowed_evidence_prefixes: {', '.join(sorted(unknown_candidate_evidence_prefixes))}"
        )

    result = {
        "drift_ok": len(violations) == 0,
        "violations": violations,
        "candidate_source_types": sorted(candidate_source_types),
        "candidate_evidence_prefixes": sorted(candidate_evidence_prefixes),
    }

    print(json.dumps(result, indent=2))

    if violations:
        sys.exit(1)


if __name__ == "__main__":
    main()
