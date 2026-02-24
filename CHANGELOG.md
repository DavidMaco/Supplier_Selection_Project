# Changelog

All notable changes to the AEGIS Procurement Intelligence Platform.

## [1.1.0] - 2025-02-24

### Added
- CSV upload widget in Settings page for browser-based data import (#4)
- Structured audit logging with file + database trail (#5)
- Dashboard authentication gate with password protection (#7)
- Extended test suite: 49 tests covering auth, logging, loader, math (#8)
- Data freshness tracking with pipeline_runs table and sidebar badge (#10)
- Live FX fetching with 3-tier API fallback (open.er-api/exchangerate/frankfurter) (#11)
- Auto-generation of supplier_material_catalog from PO line items (#12)
- Executive Excel report export with multi-sheet download (#13)
- CONTRIBUTING.md and API_REFERENCE.md (#14)

### Fixed
- Streamlit pages 07/08/10 column name mismatches with analytics engines (#1)
- 3 orphaned analytics engines (should-cost, working capital, scenario) now wired into pipeline (#2)
- FX rates and commodity prices seeded in external data mode (#3)
- GROUP BY clause for ONLY_FULL_GROUP_BY compatibility in working capital (#3)

### Security
- Docker-compose password replaced with environment variables (#6)
- .env.example provided for safe credential management (#6)

### Changed
- CI pipeline now deploys schema before running tests (#9)
- Lint job uses non-blocking black check (#9)

## [1.0.0] - 2025-02-23

### Added
- Initial release of AEGIS platform
- 40+ table normalized MySQL schema across 10 SQL migration files
- 8 analytics engines: MCDA, Risk, Monte Carlo, Concentration, Carbon, Should-Cost, Working Capital, Scenario Planner
- 12-page Streamlit dashboard with interactive visualizations
- External CSV data loader with validation
- Docker deployment (docker-compose + Dockerfile)
- 24 unit tests covering config and analytics math
- GitHub Actions CI/CD pipeline
