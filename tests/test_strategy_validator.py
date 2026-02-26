import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = ROOT / "docs" / "strategy" / "validate_pip_output.py"

spec = importlib.util.spec_from_file_location("strategy_validator", VALIDATOR_PATH)
strategy_validator = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(strategy_validator)


def _base_payload(proof: str, evidence: str, date_context: str = "2026-02-26") -> dict:
    return {
        "meta": {"date_context": date_context},
        "differentiation_strategy": {
            "competitor_matrix": [{"proof": proof}]
        },
        "readiness_scorecard": {
            "dimensions": [{"evidence": evidence}]
        },
        "risk_register": [{"risk": "R1: test risk"}],
        "next_actions": [{"expected_outcome": "Action linked [RiskIDs=R1]"}],
    }


def _base_traceability_config() -> dict:
    return {
        "strict_source_tags": True,
        "strict_evidence_ids": True,
        "strict_risk_linkage": True,
        "strict_freshness": True,
        "max_age_days": 300,
        "freshness_warning_window_days": 30,
        "source_type_max_age_days": {
            "FinanceSignoff": 120,
            "ThirdPartyBenchmark": 270,
        },
        "evidence_prefix_max_age_days": {
            "OR": 90,
            "BI": 120,
        },
        "source_tag_pattern": r"SourceTag=[A-Za-z]+:[A-Za-z0-9\-]+",
        "evidence_id_pattern": r"EvidenceID=[A-Z]{2}-\d{2}",
        "data_as_of_pattern": r"DataAsOf=\d{4}-\d{2}-\d{2}",
    }


def _run_traceability(payload: dict, trace_cfg: dict) -> dict:
    return strategy_validator.validate_traceability(payload, {"traceability": trace_cfg})


def test_source_type_specific_threshold_is_applied():
    payload = _base_payload(
        proof="SourceTag=FinanceSignoff:NEG-1|DataAsOf=2025-07-01",
        evidence="EvidenceID=BI-01; DataAsOf=2026-01-31",
    )
    result = _run_traceability(payload, _base_traceability_config())
    assert result["freshness_ok"] is False
    assert any("competitor_matrix[1].proof DataAsOf exceeds max age" in v for v in result["freshness_violations"])


def test_unknown_source_type_uses_fallback_threshold():
    payload = _base_payload(
        proof="SourceTag=UnknownSource:U-1|DataAsOf=2025-07-01",
        evidence="EvidenceID=BI-01; DataAsOf=2026-01-31",
    )
    result = _run_traceability(payload, _base_traceability_config())
    assert result["freshness_ok"] is True


def test_evidence_prefix_specific_threshold_is_applied():
    payload = _base_payload(
        proof="SourceTag=ThirdPartyBenchmark:TB-1|DataAsOf=2026-01-31",
        evidence="EvidenceID=OR-05; DataAsOf=2025-09-01",
    )
    result = _run_traceability(payload, _base_traceability_config())
    assert result["freshness_ok"] is False
    assert any("readiness_scorecard.dimensions[1].evidence DataAsOf exceeds max age" in v for v in result["freshness_violations"])


def test_unknown_evidence_prefix_uses_fallback_threshold():
    payload = _base_payload(
        proof="SourceTag=ThirdPartyBenchmark:TB-1|DataAsOf=2026-01-31",
        evidence="EvidenceID=ZZ-01; DataAsOf=2025-07-01",
    )
    result = _run_traceability(payload, _base_traceability_config())
    assert result["freshness_ok"] is True


def test_missing_data_as_of_fails_when_strict_freshness_enabled():
    payload = _base_payload(
        proof="SourceTag=FinanceSignoff:NEG-1",
        evidence="EvidenceID=BI-01; Baseline=41%; Current=63%",
    )
    result = _run_traceability(payload, _base_traceability_config())
    assert result["traceability_ok"] is False
    assert result["freshness_ok"] is False
    assert any("competitor_matrix[1].proof missing DataAsOf" in v for v in result["freshness_violations"])
    assert any("readiness_scorecard.dimensions[1].evidence missing DataAsOf" in v for v in result["freshness_violations"])


def test_warning_and_diagnostics_present_near_threshold():
    payload = _base_payload(
        proof="SourceTag=FinanceSignoff:NEG-1|DataAsOf=2025-11-08",
        evidence="EvidenceID=BI-01; DataAsOf=2025-11-08",
    )
    result = _run_traceability(payload, _base_traceability_config())
    assert result["freshness_ok"] is True
    assert len(result["freshness_warnings"]) >= 1
    assert len(result["freshness_diagnostics"]) == 2
    first = result["freshness_diagnostics"][0]
    assert "field" in first
    assert "policy_type" in first
    assert "max_age_days" in first
    assert "age_days" in first
