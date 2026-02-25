"""
AEGIS — Adaptive Engine for Global Intelligent Sourcing
Configuration Module

Reads settings from (highest priority first):
  1. Streamlit Cloud secrets  (st.secrets["database"]["DB_HOST"], etc.)
  2. Environment variables     (DB_HOST, DB_PASSWORD, ...)
  3. Built-in defaults
"""
import os


def _secret(section: str, key: str, fallback: str = "") -> str:
    """Read a value from Streamlit secrets, env var, or fallback."""
    try:
        import streamlit as st
    except ImportError:
        return os.getenv(key, fallback)

    try:
        return str(st.secrets[section][key])
    except Exception:
        return os.getenv(key, fallback)


# ─── Database ────────────────────────────────────────────────────────
DB_HOST = _secret("database", "DB_HOST", "localhost")
DB_PORT = int(_secret("database", "DB_PORT", "3306"))
DB_USER = _secret("database", "DB_USER", "root")
DB_PASSWORD = _secret("database", "DB_PASSWORD", "")
DB_NAME = _secret("database", "DB_NAME", "aegis_procurement")
DB_SSL = _secret("database", "DB_SSL", "false").lower() in ("true", "1", "yes")

_base_url = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
if DB_SSL:
    _base_url += "?ssl_verify_cert=true&ssl_verify_identity=true"

DATABASE_URL = os.getenv("DATABASE_URL", _base_url)


def pymysql_ssl_context():
    """Return an ssl.SSLContext for raw pymysql connections, or None."""
    if not DB_SSL:
        return None
    import ssl
    return ssl.create_default_context()


# ─── FX API (3-tier failover) ───────────────────────────────────────
FX_API_PRIMARY = "https://open.er-api.com/v6/latest/USD"
FX_API_SECONDARY = "https://api.exchangerate-api.com/v4/latest/USD"
FX_API_TERTIARY = "https://api.frankfurter.dev/latest?base=USD"

# ─── Monte Carlo Defaults ───────────────────────────────────────────
MC_DEFAULT_PATHS = 10_000
MC_DEFAULT_HORIZON_DAYS = 90
MC_MAX_PATHS = 100_000
MC_MAX_HORIZON_DAYS = 365

# ─── FX Volatilities (annual σ) ─────────────────────────────────────
FX_VOLATILITIES = {
    "EUR": 0.08,
    "GBP": 0.10,
    "CNY": 0.06,
    "NGN": 0.40,
    "JPY": 0.12,
    "KRW": 0.10,
    "BRL": 0.18,
    "ZAR": 0.15,
    "TRY": 0.35,
}

# ─── FX Anchor Rates (live feed with static fallback) ───────────────
_FX_STATIC_RATES = {
    "EUR": 0.92, "GBP": 0.79, "CNY": 7.25, "NGN": 1580.0,
    "JPY": 149.5, "KRW": 1435.0, "BRL": 5.85, "ZAR": 18.4, "TRY": 36.2,
}


def _fetch_live_fx() -> dict:
    """3-tier failover: open.er-api → exchangerate-api → frankfurter."""
    import urllib.request, json as _json, logging as _log
    _apis = [FX_API_PRIMARY, FX_API_SECONDARY, FX_API_TERTIARY]
    for url in _apis:
        try:
            with urllib.request.urlopen(url, timeout=5) as resp:
                data = _json.loads(resp.read().decode())
            rates = data.get("rates", {})
            if rates:
                live = {c: float(rates[c]) for c in _FX_STATIC_RATES if c in rates}
                for c, r in _FX_STATIC_RATES.items():
                    live.setdefault(c, r)
                _log.getLogger(__name__).info("Live FX rates loaded from %s", url)
                return live
        except Exception as exc:
            _log.getLogger(__name__).debug("FX fetch failed (%s): %s", url, exc)
    return dict(_FX_STATIC_RATES)


FX_ANCHOR_RATES = _fetch_live_fx()

# ─── Risk Scoring Weights (sum = 1.00) ──────────────────────────────
RISK_WEIGHTS = {
    "lead_time_volatility": 0.15,
    "quality_failure": 0.20,
    "fx_exposure": 0.15,
    "geopolitical": 0.10,
    "concentration": 0.15,
    "financial_health": 0.10,
    "esg_compliance": 0.15,
}

# ─── AHP Default Weights (MCDA, sum = 1.00) ─────────────────────────
MCDA_DEFAULT_WEIGHTS = {
    "cost": 0.20,
    "quality": 0.18,
    "delivery": 0.15,
    "risk": 0.15,
    "esg": 0.12,
    "innovation": 0.10,
    "compliance": 0.10,
}

# ─── Emission Factors (kgCO2e per tonne-km, DEFRA 2025) ─────────────
EMISSION_FACTORS = {
    "Sea": 0.016,
    "Air": 0.602,
    "Rail": 0.028,
    "Road": 0.062,
}

# ─── Should-Cost Thresholds ─────────────────────────────────────────
COST_LEAKAGE_INVESTIGATE_PCT = 5.0
COST_LEAKAGE_ESCALATE_PCT = 15.0
COST_LEAKAGE_RED_FLAG_PCT = 25.0

# ─── HHI Thresholds ─────────────────────────────────────────────────
HHI_COMPETITIVE = 1500
HHI_MODERATE = 2500
HHI_CONCENTRATED = 5000

# ─── Data Generation Seed ───────────────────────────────────────────
RANDOM_SEED = 42

# ─── Feature Flags ──────────────────────────────────────────────────
ENABLE_LIVE_FX = os.getenv("ENABLE_LIVE_FX", "false").lower() == "true"
DEMO_MODE = os.getenv("DEMO_MODE", "true").lower() == "true"
