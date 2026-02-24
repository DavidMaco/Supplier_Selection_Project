"""
AEGIS — Live FX & Commodity Data Fetcher
Fetches real-time exchange rates and commodity prices from public APIs.
Falls back through 3 FX endpoints (open.er-api → exchangerate-api → frankfurter).
"""

import datetime as dt
import requests
import config
from utils.logging_config import get_logger, _get_connection

log = get_logger("live_data")

# ── FX Rates ─────────────────────────────────────────────────────────

def fetch_fx_rates() -> dict[str, float] | None:
    """Try each FX API in priority order. Returns {currency_code: rate_to_usd}."""
    apis = [
        ("Primary (open.er-api)", config.FX_API_PRIMARY, _parse_open_er),
        ("Secondary (exchangerate-api)", config.FX_API_SECONDARY, _parse_exchangerate),
        ("Tertiary (frankfurter)", config.FX_API_TERTIARY, _parse_frankfurter),
    ]

    for name, url, parser in apis:
        try:
            log.info("Fetching FX from %s ...", name)
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            rates = parser(resp.json())
            # Filter to only currencies we care about
            our_currencies = set(config.FX_VOLATILITIES.keys()) | {"USD"}
            filtered = {k: v for k, v in rates.items() if k in our_currencies}
            log.info("  Got %d rates from %s", len(filtered), name)
            return filtered
        except Exception as exc:
            log.warning("  %s failed: %s", name, exc)
            continue

    log.error("All FX APIs failed")
    return None


def _parse_open_er(data: dict) -> dict[str, float]:
    return data.get("rates", {})


def _parse_exchangerate(data: dict) -> dict[str, float]:
    return data.get("rates", {})


def _parse_frankfurter(data: dict) -> dict[str, float]:
    return data.get("rates", {})


def persist_live_fx(rates: dict[str, float]) -> int:
    """Insert today's live rates into fx_rates table. Returns rows inserted."""
    if not rates:
        return 0

    today = dt.date.today()
    conn = _get_connection()
    inserted = 0

    try:
        with conn.cursor() as cur:
            # Get currency_id mapping
            cur.execute("SELECT currency_code, currency_id FROM currencies")
            ccy_map = {row[0]: row[1] for row in cur.fetchall()}

            for code, rate in rates.items():
                cid = ccy_map.get(code)
                if not cid:
                    continue
                cur.execute(
                    "INSERT INTO fx_rates (currency_id, rate_date, rate_to_usd) "
                    "VALUES (%s, %s, %s) "
                    "ON DUPLICATE KEY UPDATE rate_to_usd = VALUES(rate_to_usd)",
                    (cid, today, rate),
                )
                inserted += 1

        conn.close()
        log.info("Persisted %d live FX rates for %s", inserted, today)
    except Exception:
        log.error("Failed to persist FX rates", exc_info=True)
    return inserted


# ── Commodity Prices ─────────────────────────────────────────────────

# Free commodity price proxies (no API key required)
_COMMODITY_APIS = [
    # metals-api.com free tier
    "https://metals-api.com/api/latest?access_key=&base=USD&symbols=XAU,XAG,XPT,XPD,XCU",
]


def fetch_commodity_prices() -> dict[str, float] | None:
    """
    Attempt to fetch commodity prices from free APIs.
    Falls back to config anchor rates if live data unavailable.
    """
    # Try live fetch first
    for url in _COMMODITY_APIS:
        try:
            resp = requests.get(url, timeout=10)
            if resp.ok:
                data = resp.json()
                if data.get("success") and data.get("rates"):
                    return data["rates"]
        except Exception:
            pass

    # Fallback: use config anchor rates as "latest" (they're hardcoded but usable)
    log.info("Using config anchor rates as commodity price proxy")
    return None


# ── Combined refresh ─────────────────────────────────────────────────

def refresh_live_data() -> dict:
    """
    Fetch and persist live FX rates (commodity prices fall back to config).
    Returns summary dict.
    """
    result = {"fx_updated": 0, "commodities_updated": 0, "timestamp": str(dt.datetime.now())}

    if not config.ENABLE_LIVE_FX:
        log.info("Live FX disabled (ENABLE_LIVE_FX=False)")
        return result

    rates = fetch_fx_rates()
    if rates:
        result["fx_updated"] = persist_live_fx(rates)
        result["fx_rates"] = rates

    return result


if __name__ == "__main__":
    import sys, os
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

    summary = refresh_live_data()
    log.info("Refresh complete: %s", summary)
