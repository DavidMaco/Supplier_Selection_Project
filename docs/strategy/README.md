# Strategy Toolkit (Implementation v1)

This folder contains an end-to-end prompt engineering and evaluation toolkit for the Procurement Intelligence Platform planning phase.

## Files
- `PIP_GOLD_PROMPT_V1.md` — master narrative prompt for LLM generation.
- `pip-gold-v1.schema.json` — strict JSON schema contract.
- `pip-gold-v1.template.json` — starter output template.
- `PIP_EVALUATOR_PROMPT.md` — evaluator prompt for independent review.
- `validate_pip_output.py` — local schema and score consistency validator.
- `validator-config.json` — single-source rounding and status-mapping rules for validator reproducibility.
- `generate_evaluation_manifest.py` — reproducibility manifest generator (hashes + validator metadata).
- `check_traceability_policy_drift.py` — detects drift between candidate tag usage and configured traceability policy maps/enums.
- `validator-output.contract.schema.json` — contract schema for validator JSON output.
- `VALIDATOR_OUTPUT_CHANGELOG.md` — versioned notes for validator output field evolution.
- `publish_ci_summary.py` — reusable workflow-summary writer for strategy CI jobs.

## Quick Start
1. Generate a candidate JSON using `PIP_GOLD_PROMPT_V1.md`.
2. Ensure output is valid JSON and save it (example: `candidate-output.json`).
3. Install validator dependency:

```powershell
pip install jsonschema
```

4. Run local validation:

```powershell
python docs/strategy/validate_pip_output.py --input docs/strategy/candidate-output.json --schema docs/strategy/pip-gold-v1.schema.json
```

Optional explicit config path:

```powershell
python docs/strategy/validate_pip_output.py --input docs/strategy/candidate-output.json --schema docs/strategy/pip-gold-v1.schema.json --config docs/strategy/validator-config.json
```

5. Use `PIP_EVALUATOR_PROMPT.md` with your preferred LLM for qualitative and investment-readiness review.
6. Generate reproducibility manifest:

```powershell
python docs/strategy/generate_evaluation_manifest.py --candidate docs/strategy/candidate-output.json --schema docs/strategy/pip-gold-v1.schema.json --config docs/strategy/validator-config.json --validation docs/strategy/candidate-validation.json --output docs/strategy/candidate-manifest.json
```

## Notes
- The schema requires complete section coverage and explicit assumptions/data gaps.
- The schema now enforces traceability regex patterns for `SourceTag`, `EvidenceID`, `risk` IDs (`R#:`), and `next_actions.expected_outcome` RiskIDs tags.
- The validator enforces evidence freshness using `DataAsOf=YYYY-MM-DD` markers and max-age policy from `validator-config.json`.
- Freshness policy supports source-specific (`SourceTag` type) and scorecard evidence-prefix-specific (`EvidenceID` prefix) max-age thresholds.
- Validator output includes `freshness_warnings` (near-expiry) and `freshness_diagnostics` (applied policy metadata per checked field).
- Validator can enforce strict allowed enums for `SourceTag` types and `EvidenceID` prefixes via `validator-config.json`.
- The validator checks schema compliance and scorecard math/status consistency using `validator-config.json`.
- Investability thresholds are read from the candidate JSON scorecard, not hard-coded.
- The starter file `pip-gold-v1.template.json` is a scaffold; it is expected to fail schema quality checks until filled.
- The reproducibility manifest captures SHA-256 hashes for candidate/schema/config/validation artifacts and validator version.

## CI Gate
- `.github/workflows/ci.yml` includes a `strategy-governance-fast` job for quick non-scheduled checks (tests + drift + validator gate).
- `strategy-governance-fast` uses path filtering and runs heavy checks only when strategy-governance files/tests change.
- `strategy-governance-fast` publishes a workflow summary showing triggered/skipped state and key validation metrics.
- `.github/workflows/ci.yml` includes a `strategy-validation` job.
- The job runs `validate_pip_output.py` against `pip-gold-v1.candidate.json` and fails if `all_checks_valid` is not `true`.
- The workflow also includes `strategy-policy-tests`, which executes `tests/test_strategy_validator.py`.
- A monthly `strategy-governance-scheduled` job runs on cron (`0 6 1 * *`) and fails if any `freshness_warnings` are present.
- Strategy and scheduled jobs now enforce traceability policy drift checks and validator output contract validation.
- Fast, validation, and scheduled strategy jobs all publish comparable workflow summaries for reporting parity.
- Summary publishing is centralized via `publish_ci_summary.py` to keep formatting consistent across jobs.

## Tests
- Validator policy tests are in `tests/test_strategy_validator.py` and cover fallback behavior plus strict freshness failure modes.
- Drift-checker tests are in `tests/test_traceability_policy_drift.py` and cover pass/fail exit-code behavior for taxonomy/mapping drift.
