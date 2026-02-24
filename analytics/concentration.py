"""
AEGIS — Concentration Analysis Engine
HHI calculation, single-source detection, geographic diversification.
"""

import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

ENGINE = create_engine(config.DATABASE_URL, echo=False)


def compute_hhi(shares) -> float:
    """Herfindahl-Hirschman Index from market share percentages."""
    shares = np.asarray(shares, dtype=float)
    return float(np.sum(shares ** 2))


def categorize_hhi(hhi: float) -> str:
    if hhi < config.HHI_COMPETITIVE:
        return "Low"
    elif hhi < config.HHI_MODERATE:
        return "Moderate"
    elif hhi < config.HHI_CONCENTRATED:
        return "High"
    return "High"


def analyze_concentration(dimension: str = "Supplier",
                          year: int = 2024) -> pd.DataFrame:
    """
    Compute spend concentration along a dimension.
    Dimensions: Supplier, Country, Currency, Material, Port
    """
    dim_configs = {
        "Supplier": {
            "group_col": "s.supplier_name",
            "join": "JOIN suppliers s ON po.supplier_id = s.supplier_id",
        },
        "Country": {
            "group_col": "c.country_name",
            "join": """JOIN suppliers s ON po.supplier_id = s.supplier_id
                       JOIN countries c ON s.country_id = c.country_id""",
        },
        "Currency": {
            "group_col": "cur.currency_code",
            "join": """JOIN currencies cur ON po.currency_id = cur.currency_id""",
        },
        "Material": {
            "group_col": "m.commodity_group",
            "join": """JOIN po_line_items li ON po.po_id = li.po_id
                       JOIN materials m ON li.material_id = m.material_id""",
        },
        "Port": {
            "group_col": "p.port_name",
            "join": """JOIN shipments sh ON po.po_id = sh.po_id
                       JOIN ports p ON sh.destination_port_id = p.port_id""",
        },
    }

    cfg = dim_configs.get(dimension)
    if not cfg:
        raise ValueError(f"Invalid dimension: {dimension}")

    with ENGINE.connect() as conn:
        if dimension == "Material":
            sql = f"""
                SELECT
                    {cfg['group_col']} AS dimension_value,
                    SUM(li.line_total) AS spend_usd
                FROM purchase_orders po
                {cfg['join']}
                WHERE YEAR(po.order_date) = :year
                  AND po.status != 'Cancelled'
                GROUP BY {cfg['group_col']}
                ORDER BY spend_usd DESC
            """
        else:
            # Use COALESCE chain: landed_cost_usd (if populated) -> total_amount
            sql = f"""
                SELECT
                    {cfg['group_col']} AS dimension_value,
                    COALESCE(SUM(COALESCE(po.landed_cost_usd, po.total_amount)), 0) AS spend_usd
                FROM purchase_orders po
                {cfg['join']}
                WHERE YEAR(po.order_date) = :year
                  AND po.status != 'Cancelled'
                GROUP BY {cfg['group_col']}
                ORDER BY spend_usd DESC
            """

        df = pd.read_sql(text(sql), conn, params={"year": year})

    if df.empty:
        return df

    total = df["spend_usd"].sum()
    if total == 0:
        df["spend_share_pct"] = 0.0
    else:
        df["spend_share_pct"] = np.round(df["spend_usd"] / total * 100, 4)

    # HHI (on percentage scale)
    hhi = compute_hhi(df["spend_share_pct"].values)
    hhi_cat = categorize_hhi(hhi)

    # Top-3 share
    top3 = df["spend_share_pct"].head(3).sum()

    df["hhi_index"] = hhi
    df["hhi_category"] = hhi_cat
    df["top_n_share_pct"] = top3
    df["dimension"] = dimension

    # Recommendations
    def recommend(row):
        if row["spend_share_pct"] > 40:
            return f"CRITICAL: {row['dimension_value']} holds {row['spend_share_pct']:.1f}% — diversify urgently"
        elif row["spend_share_pct"] > 25:
            return f"WARNING: {row['dimension_value']} holds {row['spend_share_pct']:.1f}% — develop alternatives"
        return None

    df["recommendation"] = df.apply(recommend, axis=1)

    return df


def run_full_concentration_analysis(year: int = 2024) -> dict:
    """Run concentration analysis across all 5 dimensions."""
    results = {}
    for dim in ["Supplier", "Country", "Currency", "Material", "Port"]:
        try:
            df = analyze_concentration(dim, year)
            if not df.empty:
                results[dim] = {
                    "data": df,
                    "hhi": df["hhi_index"].iloc[0] if len(df) > 0 else 0,
                    "hhi_category": df["hhi_category"].iloc[0] if len(df) > 0 else "N/A",
                    "top3_share": df["top_n_share_pct"].iloc[0] if len(df) > 0 else 0,
                }
        except Exception as e:
            print(f"  Warning: {dim} analysis failed: {e}")
            results[dim] = {"data": pd.DataFrame(), "hhi": 0,
                           "hhi_category": "Error", "top3_share": 0}

    return results


def persist_concentration(results: dict, year: int = 2024):
    """Save concentration results to database."""
    records = []
    analysis_date = pd.Timestamp.now().date()

    for dim, info in results.items():
        df = info["data"]
        if df.empty:
            continue
        for _, row in df.iterrows():
            records.append({
                "analysis_date": analysis_date,
                "dimension": dim,
                "dimension_value": str(row["dimension_value"]),
                "spend_usd": float(row["spend_usd"]),
                "spend_share_pct": float(row["spend_share_pct"]),
                "hhi_index": float(row["hhi_index"]),
                "hhi_category": str(row["hhi_category"]),
                "top_n_share_pct": float(row["top_n_share_pct"]),
                "recommendation": row.get("recommendation"),
            })

    # Sanitize NaN/Inf values that MySQL cannot handle
    import math
    for rec in records:
        for key in ("spend_usd", "spend_share_pct", "hhi_index", "top_n_share_pct"):
            val = rec.get(key)
            if val is not None and (math.isnan(val) or math.isinf(val)):
                rec[key] = 0.0

    if records:
        with ENGINE.begin() as conn:
            for i in range(0, len(records), 100):
                conn.execute(text("""
                    INSERT INTO concentration_analysis
                        (analysis_date, dimension, dimension_value,
                         spend_usd, spend_share_pct, hhi_index,
                         hhi_category, top_n_share_pct, recommendation)
                    VALUES
                        (:analysis_date, :dimension, :dimension_value,
                         :spend_usd, :spend_share_pct, :hhi_index,
                         :hhi_category, :top_n_share_pct, :recommendation)
                """), records[i:i+100])

    print(f"[OK] {len(records)} concentration records persisted")


if __name__ == "__main__":
    results = run_full_concentration_analysis(2024)
    for dim, info in results.items():
        print(f"\n{dim}: HHI={info['hhi']:.0f} ({info['hhi_category']}), "
              f"Top-3 Share={info['top3_share']:.1f}%")
        if not info["data"].empty:
            print(info["data"][["dimension_value", "spend_usd", "spend_share_pct"]]
                  .head(5).to_string(index=False))
