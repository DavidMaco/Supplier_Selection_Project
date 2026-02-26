# Validator Output Changelog

## v1.7.0
- Added strict enum governance result fields:
  - `source_type_ok`
  - `evidence_prefix_ok`
  - `source_type_violations`
  - `evidence_prefix_violations`
- Retained existing contract fields for schema, score, traceability, freshness, warnings, and diagnostics.

## v1.6.0
- Added warning/diagnostic output fields:
  - `freshness_warnings`
  - `freshness_diagnostics`

## v1.5.0
- Added source-specific and evidence-prefix-specific freshness policy behavior.

## v1.4.0
- Added freshness checks:
  - `freshness_ok`
  - `freshness_violations`

## v1.3.0
- Added traceability aggregation:
  - `traceability_ok`
  - `all_checks_valid`
