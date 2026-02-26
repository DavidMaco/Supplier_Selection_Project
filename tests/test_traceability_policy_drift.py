import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CHECKER_PATH = ROOT / "docs" / "strategy" / "check_traceability_policy_drift.py"


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _base_candidate() -> dict:
    return {
        "differentiation_strategy": {
            "competitor_matrix": [
                {"proof": "SourceTag=FinanceSignoff:NEG-1|DataAsOf=2026-01-31"},
                {"proof": "SourceTag=InternalAudit:AUD-1|DataAsOf=2026-01-31"},
            ]
        },
        "readiness_scorecard": {
            "dimensions": [
                {"evidence": "EvidenceID=BI-01; DataAsOf=2026-01-31"},
                {"evidence": "EvidenceID=OR-05; DataAsOf=2026-01-31"},
            ]
        },
    }


def _base_config() -> dict:
    return {
        "traceability": {
            "allowed_source_types": ["FinanceSignoff", "InternalAudit"],
            "source_type_max_age_days": {
                "FinanceSignoff": 120,
                "InternalAudit": 180,
            },
            "allowed_evidence_prefixes": ["BI", "OR"],
            "evidence_prefix_max_age_days": {
                "BI": 120,
                "OR": 90,
            },
        }
    }


def _run_checker(candidate_path: Path, config_path: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            sys.executable,
            str(CHECKER_PATH),
            "--candidate",
            str(candidate_path),
            "--config",
            str(config_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )


def _make_workspace_temp_dir() -> Path:
    tests_dir = ROOT / "tests"
    path_str = tempfile.mkdtemp(prefix="policy_drift_", dir=str(tests_dir))
    return Path(path_str)


def test_policy_drift_checker_passes_when_aligned():
    work_dir = _make_workspace_temp_dir()
    candidate_path = work_dir / "candidate.json"
    config_path = work_dir / "config.json"
    _write_json(candidate_path, _base_candidate())
    _write_json(config_path, _base_config())

    try:
        result = _run_checker(candidate_path, config_path)

        assert result.returncode == 0
        payload = json.loads(result.stdout)
        assert payload["drift_ok"] is True
        assert payload["violations"] == []
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


def test_policy_drift_checker_fails_on_unknown_candidate_tags():
    candidate = _base_candidate()
    candidate["differentiation_strategy"]["competitor_matrix"].append(
        {"proof": "SourceTag=UnknownSource:U-1|DataAsOf=2026-01-31"}
    )
    candidate["readiness_scorecard"]["dimensions"].append(
        {"evidence": "EvidenceID=ZZ-01; DataAsOf=2026-01-31"}
    )

    work_dir = _make_workspace_temp_dir()
    candidate_path = work_dir / "candidate.json"
    config_path = work_dir / "config.json"
    _write_json(candidate_path, candidate)
    _write_json(config_path, _base_config())

    try:
        result = _run_checker(candidate_path, config_path)

        assert result.returncode == 1
        payload = json.loads(result.stdout)
        assert payload["drift_ok"] is False
        assert any("candidate uses source types" in item for item in payload["violations"])
        assert any("candidate uses evidence prefixes" in item for item in payload["violations"])
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


def test_policy_drift_checker_fails_on_mapping_mismatch():
    config = _base_config()
    config["traceability"]["allowed_source_types"].append("PMOReport")
    config["traceability"]["evidence_prefix_max_age_days"]["AX"] = 120

    work_dir = _make_workspace_temp_dir()
    candidate_path = work_dir / "candidate.json"
    config_path = work_dir / "config.json"
    _write_json(candidate_path, _base_candidate())
    _write_json(config_path, config)

    try:
        result = _run_checker(candidate_path, config_path)

        assert result.returncode == 1
        payload = json.loads(result.stdout)
        assert payload["drift_ok"] is False
        assert any("allowed_source_types missing max-age mapping" in item for item in payload["violations"])
        assert any("evidence_prefix_max_age_days contains unmapped prefixes" in item for item in payload["violations"])
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)
