"""
AEGIS — Carbon Footprint Engine
GHG Protocol Scope 3 Category 4 (upstream transport) calculations.
GLEC Framework v3 emission factors.
"""

import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

ENGINE = create_engine(config.DATABASE_URL, echo=False)


def haversine(lat1, lon1, lat2, lon2):
    """Haversine distance between two lat/lon points in km. Works with scalars and Series."""
    R = 6371  # Earth radius km
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat/2)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon/2)**2
    return 2 * R * np.arcsin(np.sqrt(a))


def calculate_emissions(year: int = None) -> pd.DataFrame:
    """
    Calculate CO2e for all shipments.
    Method: weight_tonnes × distance_km × emission_factor
    """
    year_filter = f"AND YEAR(sh.dispatch_date) = {year}" if year else ""

    with ENGINE.connect() as conn:
        df = pd.read_sql(text(f"""
            SELECT
                sh.shipment_id,
                sh.transport_mode,
                sh.weight_tonnes,
                sh.dispatch_date,
                po.freight_cost_usd,
                po.supplier_id,
                s.supplier_name,
                c_orig.country_name AS origin_country,
                c_dest.country_name AS dest_country,
                p_orig.latitude AS orig_lat, p_orig.longitude AS orig_lon,
                p_dest.latitude AS dest_lat, p_dest.longitude AS dest_lon,
                DATEDIFF(COALESCE(sh.actual_arrival, sh.eta_date), sh.dispatch_date)
                    AS transit_days
            FROM shipments sh
            JOIN purchase_orders po ON sh.po_id = po.po_id
            JOIN suppliers s ON po.supplier_id = s.supplier_id
            LEFT JOIN ports p_orig ON sh.origin_port_id = p_orig.port_id
            LEFT JOIN ports p_dest ON sh.destination_port_id = p_dest.port_id
            LEFT JOIN countries c_orig ON p_orig.country_id = c_orig.country_id
            LEFT JOIN countries c_dest ON p_dest.country_id = c_dest.country_id
            WHERE 1=1 {year_filter}
        """), conn)

    if df.empty:
        return df

    # Haversine distance (using module-level function)

    df["distance_km"] = haversine(
        df["orig_lat"].fillna(6.45),
        df["orig_lon"].fillna(3.38),
        df["dest_lat"].fillna(6.45),
        df["dest_lon"].fillna(3.38))

    # Minimum distance
    df["distance_km"] = df["distance_km"].clip(lower=100)

    # Emission factors
    ef_map = config.EMISSION_FACTORS
    df["emission_factor"] = df["transport_mode"].map(ef_map).fillna(0.016)

    # CO2e calculation
    df["co2e_kg"] = np.round(
        df["weight_tonnes"] * df["distance_km"] * df["emission_factor"], 2)

    df["co2e_tonnes"] = np.round(df["co2e_kg"] / 1000, 4)

    # Carbon intensity (kgCO2e per $1000 freight)
    df["carbon_intensity"] = np.where(
        df["freight_cost_usd"] > 0,
        df["co2e_kg"] / df["freight_cost_usd"] * 1000,
        0)

    return df


def get_carbon_summary(year: int = 2024) -> dict:
    """Aggregate carbon metrics."""
    df = calculate_emissions(year)
    if df.empty:
        return {}

    # By mode
    by_mode = df.groupby("transport_mode").agg({
        "co2e_kg": "sum",
        "shipment_id": "count",
        "weight_tonnes": "sum",
        "distance_km": "mean",
    }).rename(columns={"shipment_id": "shipment_count"}).reset_index()

    # By supplier
    by_supplier = df.groupby(["supplier_id", "supplier_name"]).agg({
        "co2e_kg": "sum",
        "shipment_id": "count",
        "freight_cost_usd": "sum",
    }).rename(columns={"shipment_id": "shipments"}).reset_index()
    by_supplier["co2e_tonnes"] = by_supplier["co2e_kg"] / 1000
    by_supplier = by_supplier.sort_values("co2e_kg", ascending=False)

    # By route
    by_route = df.groupby(["origin_country", "dest_country"]).agg({
        "co2e_kg": "sum",
        "shipment_id": "count",
        "distance_km": "mean",
    }).reset_index().sort_values("co2e_kg", ascending=False)

    total_co2e = df["co2e_kg"].sum()

    return {
        "year": year,
        "total_co2e_kg": total_co2e,
        "total_co2e_tonnes": total_co2e / 1000,
        "shipment_count": len(df),
        "avg_co2e_per_shipment": total_co2e / max(len(df), 1),
        "by_mode": by_mode,
        "by_supplier": by_supplier.head(20),
        "by_route": by_route.head(15),
        "detail": df,
    }


def get_reduction_opportunities(year: int = 2024) -> pd.DataFrame:
    """
    Identify shipments where mode-shifting could reduce emissions.
    e.g., Air → Sea for non-urgent shipments.
    """
    df = calculate_emissions(year)
    if df.empty:
        return df

    ef = config.EMISSION_FACTORS

    # Air shipments that could switch to sea
    air = df[df["transport_mode"] == "Air"].copy()
    if air.empty:
        return pd.DataFrame()

    air["current_co2e"] = air["co2e_kg"]
    air["sea_co2e"] = air["weight_tonnes"] * air["distance_km"] * ef["Sea"]
    air["rail_co2e"] = air["weight_tonnes"] * air["distance_km"] * ef["Rail"]
    air["reduction_if_sea"] = air["current_co2e"] - air["sea_co2e"]
    air["reduction_pct_sea"] = (air["reduction_if_sea"] / air["current_co2e"] * 100)

    return air[["shipment_id", "supplier_name", "origin_country", "dest_country",
                "weight_tonnes", "current_co2e", "sea_co2e",
                "reduction_if_sea", "reduction_pct_sea"]
              ].sort_values("reduction_if_sea", ascending=False)


if __name__ == "__main__":
    summary = get_carbon_summary(2024)
    if summary:
        print(f"Total CO2e: {summary['total_co2e_tonnes']:,.1f} tonnes")
        print(f"Shipments: {summary['shipment_count']}")
        print(f"\nBy Mode:")
        print(summary["by_mode"].to_string(index=False))
