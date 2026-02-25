"""
AEGIS — Page 12: Settings & Configuration
Manage weights, thresholds, feature flags, external data upload.
"""

import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import json
import tempfile
import os
import config

st.set_page_config(page_title="AEGIS · Settings", layout="wide")
st.title("⚙️ Settings & Configuration")

tab_mcda, tab_risk, tab_fx, tab_upload, tab_sys = st.tabs([
    "🏅 MCDA Weights", "🛡️ Risk Config", "💱 FX Config",
    "📤 Import Data", "🖥️ System"])

# ── Tab 1: MCDA Weights ─────────────────────────────────────────────
with tab_mcda:
    st.subheader("Multi-Criteria Decision Analysis Weights")
    st.caption("Adjust weights used for supplier scoring (must sum to 1.0)")

    weights = dict(config.MCDA_DEFAULT_WEIGHTS)

    cols = st.columns(4)
    new_weights = {}
    for i, (key, val) in enumerate(weights.items()):
        with cols[i % 4]:
            new_weights[key] = st.number_input(
                key.replace("_", " ").title(),
                0.0, 1.0, float(val), 0.01,
                key=f"mcda_{key}")

    total = sum(new_weights.values())
    if abs(total - 1.0) > 0.01:
        st.warning(f"⚠️ Weights sum to {total:.2f} — should be 1.00")
    else:
        st.success(f"✓ Weights sum to {total:.2f}")

    st.json(new_weights)

# ── Tab 2: Risk Config ──────────────────────────────────────────────
with tab_risk:
    st.subheader("Risk Assessment Configuration")

    st.markdown("#### Risk Dimension Weights")
    risk_w = dict(config.RISK_WEIGHTS)

    cols = st.columns(4)
    new_risk = {}
    for i, (key, val) in enumerate(risk_w.items()):
        with cols[i % 4]:
            new_risk[key] = st.number_input(
                key.replace("_", " ").title(),
                0.0, 1.0, float(val), 0.01,
                key=f"risk_{key}")

    risk_total = sum(new_risk.values())
    if abs(risk_total - 1.0) > 0.01:
        st.warning(f"⚠️ Risk weights sum to {risk_total:.2f}")
    else:
        st.success(f"✓ Risk weights sum to {risk_total:.2f}")

    st.markdown("#### HHI Thresholds")
    c1, c2, c3 = st.columns(3)
    c1.number_input("Competitive", value=config.HHI_COMPETITIVE, key="hhi_mod")
    c2.number_input("Moderate", value=config.HHI_MODERATE, key="hhi_high")
    c3.number_input("Concentrated", value=config.HHI_CONCENTRATED, key="hhi_vh")

    st.markdown("#### Cost Leakage Thresholds")
    c1, c2, c3 = st.columns(3)
    c1.number_input("Investigate (%)", value=int(config.COST_LEAKAGE_INVESTIGATE_PCT), key="cl_inv")
    c2.number_input("Escalate (%)", value=int(config.COST_LEAKAGE_ESCALATE_PCT), key="cl_esc")
    c3.number_input("Red Flag (%)", value=int(config.COST_LEAKAGE_RED_FLAG_PCT), key="cl_rf")

# ── Tab 3: FX Config ────────────────────────────────────────────────
with tab_fx:
    st.subheader("Foreign Exchange Configuration")

    st.markdown("#### Anchor Rates (per 1 USD)")
    anchor = dict(config.FX_ANCHOR_RATES)
    cols = st.columns(5)
    for i, (ccy, rate) in enumerate(anchor.items()):
        with cols[i % 5]:
            st.number_input(ccy, value=float(rate), key=f"anchor_{ccy}",
                          format="%.4f")

    st.markdown("#### Annual Volatilities (σ)")
    vols = dict(config.FX_VOLATILITIES)
    cols = st.columns(5)
    for i, (ccy, vol) in enumerate(vols.items()):
        with cols[i % 5]:
            st.number_input(ccy, value=float(vol), key=f"vol_{ccy}",
                          format="%.2f", min_value=0.01, max_value=1.0)

    st.markdown("#### Monte Carlo Defaults")
    c1, c2 = st.columns(2)
    c1.number_input("Default Paths", value=config.MC_DEFAULT_PATHS,
                   min_value=1000, max_value=500000, step=1000, key="mc_paths")
    c2.number_input("Default Horizon (days)", value=config.MC_DEFAULT_HORIZON_DAYS,
                   min_value=7, max_value=365, step=7, key="mc_horizon")

    st.markdown("---")
    st.markdown("#### 🔄 Live FX Refresh")
    if st.button("Fetch Live FX Rates", type="primary"):
        with st.spinner("Fetching from public APIs..."):
            try:
                from data_ingestion.live_data_fetcher import refresh_live_data
                result = refresh_live_data()
                if result.get("fx_updated", 0) > 0:
                    st.success(f"Updated {result['fx_updated']} FX rates")
                    if "fx_rates" in result:
                        import pandas as pd
                        df = pd.DataFrame(
                            list(result["fx_rates"].items()),
                            columns=["Currency", "Rate to USD"],
                        )
                        st.dataframe(df, use_container_width=True)
                else:
                    st.warning("No rates updated. Live FX may be disabled in config.")
            except Exception as e:
                st.error(f"Fetch failed: {e}")

# ── Tab 4: Import Data ──────────────────────────────────────────────
with tab_upload:
    st.subheader("Import External CSV Data")
    st.markdown(
        "Upload your own **CSV files** to replace demo seed data. "
        "Accepted types: `suppliers`, `purchase_orders`, `purchase_order_items`, "
        "`materials`, `quality_records`, `delivery_records`, `contracts`."
    )

    CSV_TYPES = [
        "suppliers", "purchase_orders", "purchase_order_items",
        "materials", "quality_records", "delivery_records", "contracts",
    ]

    uploaded_files = st.file_uploader(
        "Drag & drop CSV files (one per type)",
        type=["csv"],
        accept_multiple_files=True,
        key="csv_upload",
    )

    if uploaded_files:
        st.markdown("##### Uploaded files")
        file_map: dict[str, bytes] = {}
        for uf in uploaded_files:
            stem = os.path.splitext(uf.name)[0].lower()
            matched = None
            for ct in CSV_TYPES:
                if ct in stem:
                    matched = ct
                    break
            if matched:
                file_map[matched] = uf.getvalue()
                st.success(f"✅ **{uf.name}** → `{matched}`")
            else:
                st.warning(f"⚠️ **{uf.name}** — could not match to a known type. Skipping.")

        if file_map:
            import pandas as pd

            with st.expander("Preview first 5 rows of each file", expanded=False):
                for ftype, raw in file_map.items():
                    try:
                        df_preview = pd.read_csv(
                            __import__("io").BytesIO(raw), nrows=5
                        )
                        st.markdown(f"**{ftype}** — {len(df_preview.columns)} columns")
                        st.dataframe(df_preview, use_container_width=True)
                    except Exception as exc:
                        st.error(f"Cannot preview {ftype}: {exc}")

            if st.button("🚀 Import into Database", type="primary"):
                progress = st.progress(0, text="Preparing import…")
                try:
                    # Write uploaded files to a temp directory
                    with tempfile.TemporaryDirectory() as tmp_dir:
                        for ftype, raw in file_map.items():
                            dest = os.path.join(tmp_dir, f"{ftype}.csv")
                            with open(dest, "wb") as fh:
                                fh.write(raw)

                        progress.progress(20, text="Loading CSV files…")

                        from data_ingestion.external_data_loader import ExternalDataLoader
                        loader = ExternalDataLoader(tmp_dir)
                        loader.load_all_files()

                        progress.progress(40, text="Validating data…")
                        errors = loader.validate()
                        if errors:
                            for err in errors:
                                st.warning(err)

                        progress.progress(60, text="Importing into database…")
                        loader.import_data()

                        progress.progress(80, text="Running warehouse ETL…")
                        from data_ingestion.populate_warehouse import populate_warehouse
                        populate_warehouse()

                        progress.progress(100, text="✅ Import complete!")
                        st.success(
                            f"Successfully imported **{len(file_map)}** file(s): "
                            f"{', '.join(file_map.keys())}"
                        )
                        st.balloons()
                except Exception as exc:
                    st.error(f"Import failed: {exc}")
    else:
        st.info("Upload one or more CSV files above to get started.")

# ── Tab 5: System ───────────────────────────────────────────────────
with tab_sys:
    st.subheader("System Configuration")

    c1, c2 = st.columns(2)
    with c1:
        import re as _re
        _masked_url = _re.sub(
            r"://([^:]+):([^@]+)@", r"://\1:****@", config.DATABASE_URL
        )
        st.text_input("Database URL", value=_masked_url, disabled=True)
        st.checkbox("Demo Mode", value=config.DEMO_MODE, key="demo_mode")
        st.checkbox("Live FX Feed", value=config.ENABLE_LIVE_FX, key="live_fx")
        st.number_input("Random Seed", value=config.RANDOM_SEED, key="rand_seed")

    with c2:
        st.markdown("#### API Endpoints")
        st.text_input("Primary FX API", value=config.FX_API_PRIMARY, disabled=True)
        st.text_input("Secondary FX API", value=config.FX_API_SECONDARY, disabled=True)
        st.text_input("Tertiary FX API", value=config.FX_API_TERTIARY, disabled=True)

    st.markdown("---")
    st.markdown("#### Emission Factors")
    ef = dict(config.EMISSION_FACTORS)
    cols = st.columns(len(ef))
    for i, (mode, factor) in enumerate(ef.items()):
        with cols[i]:
            st.metric(mode.title(), f"{factor} kg/tonne-km")

    st.markdown("---")
    st.caption("**Note:** Configuration changes on this page are for exploration only. "
              "To persist changes, edit `config.py` directly.")
