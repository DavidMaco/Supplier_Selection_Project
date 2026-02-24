# Contributing to AEGIS

Thank you for your interest in contributing to the AEGIS Procurement Intelligence Platform!

## Getting Started

1. **Fork** the repository
2. **Clone** your fork: `git clone https://github.com/<your-username>/Supplier_Selection_Project.git`
3. **Create a branch**: `git checkout -b feature/your-feature-name`
4. **Set up the environment**:
   ```bash
   cd aegis-procurement
   python -m venv .venv
   .venv\Scripts\activate   # Windows
   pip install -r requirements.txt
   ```
5. **Configure the database**: Copy `.env.example` to `.env` and set your MySQL password
6. **Run the pipeline**: `python run_aegis_pipeline.py`

## Development Workflow

### Running Tests
```bash
pytest tests/ -v --tb=short
```

### Code Style
- **Formatter**: `black` with default settings
- **Linter**: `flake8 --max-line-length=120`
- Line length: 120 characters max
- Use type hints for function signatures
- Docstrings: Google style

### Commit Messages
Follow [Conventional Commits](https://www.conventionalcommits.org/):
- `feat:` — new feature
- `fix:` — bug fix
- `test:` — test additions/changes
- `docs:` — documentation
- `ci:` — CI/CD changes
- `refactor:` — code restructuring
- `security:` — security improvements

### Pull Request Process
1. Ensure all tests pass (`pytest tests/ -v`)
2. Update documentation if needed
3. Add tests for new functionality
4. Keep PRs focused — one feature/fix per PR
5. Reference the issue number in the PR description

## Project Structure

```
aegis-procurement/
├── analytics/          # 8 analytics engines (MCDA, risk, Monte Carlo, etc.)
├── data_ingestion/     # Seed data, ETL, external loader, live FX
├── database/           # SQL schema files (01-10)
├── pages/              # Streamlit dashboard pages (01-12)
├── tests/              # pytest test suite
├── utils/              # Logging, auth, export, freshness
├── config.py           # All configuration constants
├── run_aegis_pipeline.py  # Master pipeline orchestrator
└── streamlit_app.py    # Main Streamlit entry point
```

## Analytics Engines

| Engine | Module | Purpose |
|--------|--------|---------|
| MCDA | `analytics/mcda_engine.py` | TOPSIS/PROMETHEE/WSM supplier ranking |
| Risk | `analytics/risk_scoring.py` | 7-dimension composite risk scores |
| Monte Carlo | `analytics/monte_carlo.py` | GBM simulation for FX, lead time, cost |
| Concentration | `analytics/concentration.py` | HHI across 5 dimensions |
| Carbon | `analytics/carbon_engine.py` | Scope 3 emissions with haversine |
| Should-Cost | `analytics/should_cost.py` | Bottom-up cost estimation |
| Working Capital | `analytics/working_capital.py` | DPO, aging, EPD analysis |
| Scenario Planner | `analytics/scenario_planner.py` | What-if supplier/FX/nearshore |

## Reporting Issues

- Use GitHub Issues with clear title and description
- Include steps to reproduce for bugs
- Label appropriately: `bug`, `enhancement`, `documentation`

## License

By contributing, you agree that your contributions will be licensed under the same license as the project.
