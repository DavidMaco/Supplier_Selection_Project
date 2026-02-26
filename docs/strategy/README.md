# Strategy Toolkit (Implementation v1)

This folder contains an end-to-end prompt engineering and evaluation toolkit for the Procurement Intelligence Platform planning phase.

## Files
- `PIP_GOLD_PROMPT_V1.md` — master narrative prompt for LLM generation.
- `pip-gold-v1.schema.json` — strict JSON schema contract.
- `pip-gold-v1.template.json` — starter output template.
- `PIP_EVALUATOR_PROMPT.md` — evaluator prompt for independent review.
- `validate_pip_output.py` — local schema and score consistency validator.

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

5. Use `PIP_EVALUATOR_PROMPT.md` with your preferred LLM for qualitative and investment-readiness review.

## Notes
- The schema requires complete section coverage and explicit assumptions/data gaps.
- The validator checks schema compliance and scorecard math/status consistency.
- Investability thresholds are read from the candidate JSON scorecard, not hard-coded.
- The starter file `pip-gold-v1.template.json` is a scaffold; it is expected to fail schema quality checks until filled.
