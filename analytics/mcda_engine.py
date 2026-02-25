"""
AEGIS — MCDA Engine (Multi-Criteria Decision Analysis)
Implements TOPSIS, PROMETHEE II, and WSM for supplier ranking.
AHP-derived weights from config.MCDA_DEFAULT_WEIGHTS.
"""

import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from utils.logging_config import get_logger

log = get_logger("mcda")

try:
    from utils.db import get_engine
    ENGINE = get_engine()
except (ImportError, ModuleNotFoundError):
    ENGINE = create_engine(config.DATABASE_URL, echo=False)


# ═════════════════════════════════════════════════════════════════════
#  1. Data Collection — build the decision matrix
# ═════════════════════════════════════════════════════════════════════
def build_decision_matrix(conn, period_year: int = 2024, period_quarter: int = None):
    """
    Returns DataFrame with one row per supplier, columns:
        supplier_id, cost, quality, delivery, risk, esg, innovation, financial
    All scores normalized 0-100 (higher = better).
    """
    filters = f"YEAR(po.order_date) = {period_year}"
    if period_quarter:
        filters += f" AND QUARTER(po.order_date) = {period_quarter}"

    sql = text(f"""
        SELECT
            s.supplier_id,
            s.supplier_name,
            -- COST: inverse of avg cost variance (lower variance = higher score)
            GREATEST(0, 100 - COALESCE(AVG(
                ABS(li.unit_price - m.standard_cost_usd) / NULLIF(m.standard_cost_usd, 0)
            ) * 100, 50)) AS cost_score,

            -- QUALITY: 100 - defect rate
            100 - COALESCE(AVG(qi.defect_rate_pct), 3.0) AS quality_score,

            -- DELIVERY: on-time percentage
            COALESCE(AVG(CASE WHEN sh.delay_days <= 0 THEN 100 ELSE
                GREATEST(0, 100 - sh.delay_days * 5) END), 70) AS delivery_score,

            -- RISK: inverse of composite risk (from latest assessment)
            COALESCE(100 - ra.composite_risk, 60) AS risk_score,

            -- ESG: latest overall
            COALESCE(esg.esg_overall_score, 50) AS esg_score,

            -- INNOVATION: proxy from certification count (max 10 = 100)
            LEAST(100, COALESCE(cert.cert_count, 0) * 25) AS innovation_score,

            -- FINANCIAL: revenue-based proxy
            LEAST(100, COALESCE(s.annual_revenue_usd, 10) / 5) AS financial_score

        FROM suppliers s
        JOIN purchase_orders po ON s.supplier_id = po.supplier_id
        LEFT JOIN po_line_items li ON po.po_id = li.po_id
        LEFT JOIN materials m ON li.material_id = m.material_id
        LEFT JOIN shipments sh ON po.po_id = sh.po_id
        LEFT JOIN quality_inspections qi ON sh.shipment_id = qi.shipment_id
        LEFT JOIN (
            SELECT supplier_id, composite_risk,
                   ROW_NUMBER() OVER (PARTITION BY supplier_id
                                      ORDER BY assessment_date DESC) rn
            FROM risk_assessments
        ) ra ON s.supplier_id = ra.supplier_id AND ra.rn = 1
        LEFT JOIN (
            SELECT supplier_id, esg_overall_score,
                   ROW_NUMBER() OVER (PARTITION BY supplier_id
                                      ORDER BY assessment_date DESC) rn
            FROM esg_assessments
        ) esg ON s.supplier_id = esg.supplier_id AND esg.rn = 1
        LEFT JOIN (
            SELECT supplier_id, COUNT(*) cert_count
            FROM supplier_certifications WHERE is_verified = TRUE AND expiry_date > CURDATE()
            GROUP BY supplier_id
        ) cert ON s.supplier_id = cert.supplier_id
        WHERE {filters}
        GROUP BY s.supplier_id, s.supplier_name, ra.composite_risk,
                 esg.esg_overall_score, cert.cert_count, s.annual_revenue_usd
    """)

    df = pd.read_sql(sql, conn)
    return df


# ═════════════════════════════════════════════════════════════════════
#  2. TOPSIS (Technique for Order of Preference by Similarity)
# ═════════════════════════════════════════════════════════════════════
def topsis(decision_matrix: np.ndarray, weights: np.ndarray,
           benefit_criteria: list = None) -> np.ndarray:
    """
    Inputs:
        decision_matrix: m alternatives × n criteria (raw scores)
        weights: 1D array length n, sum=1
        benefit_criteria: list of booleans (True = benefit, False = cost)
    Returns: 1D array of TOPSIS closeness scores (0-1)
    """
    m, n = decision_matrix.shape
    if benefit_criteria is None:
        benefit_criteria = [True] * n

    # Step 1: Normalize (vector normalization)
    norms = np.sqrt((decision_matrix ** 2).sum(axis=0))
    norms[norms == 0] = 1
    normalized = decision_matrix / norms

    # Step 2: Weighted normalized
    weighted = normalized * weights

    # Step 3: Ideal best / worst
    ideal_best = np.where(benefit_criteria, weighted.max(axis=0), weighted.min(axis=0))
    ideal_worst = np.where(benefit_criteria, weighted.min(axis=0), weighted.max(axis=0))

    # Step 4: Distances
    dist_best = np.sqrt(((weighted - ideal_best) ** 2).sum(axis=1))
    dist_worst = np.sqrt(((weighted - ideal_worst) ** 2).sum(axis=1))

    # Step 5: Closeness coefficient
    denom = dist_best + dist_worst
    denom[denom == 0] = 1
    closeness = dist_worst / denom

    return closeness


# ═════════════════════════════════════════════════════════════════════
#  3. PROMETHEE II
# ═════════════════════════════════════════════════════════════════════
def promethee_ii(decision_matrix: np.ndarray, weights: np.ndarray,
                 preference_fn: str = "linear", q: float = 5.0,
                 p: float = 20.0) -> np.ndarray:
    """
    Simplified PROMETHEE II with linear preference function.
    Returns net flow for each alternative.
    """
    m, n = decision_matrix.shape
    phi_plus = np.zeros(m)
    phi_minus = np.zeros(m)

    for i in range(m):
        for j in range(m):
            if i == j:
                continue
            pi_ij = 0
            for k in range(n):
                diff = decision_matrix[i, k] - decision_matrix[j, k]
                if diff <= q:
                    pref = 0
                elif diff >= p:
                    pref = 1
                else:
                    pref = (diff - q) / (p - q)
                pi_ij += weights[k] * pref
            phi_plus[i] += pi_ij
            phi_minus[i] += 0  # Will compute separately

    # Recompute properly
    phi_plus = np.zeros(m)
    phi_minus = np.zeros(m)
    for i in range(m):
        for j in range(m):
            if i == j:
                continue
            pi_ij = 0
            pi_ji = 0
            for k in range(n):
                diff_ij = decision_matrix[i, k] - decision_matrix[j, k]
                diff_ji = -diff_ij
                # P(i,j)
                if diff_ij <= q:
                    pref_ij = 0
                elif diff_ij >= p:
                    pref_ij = 1
                else:
                    pref_ij = (diff_ij - q) / (p - q)
                # P(j,i)
                if diff_ji <= q:
                    pref_ji = 0
                elif diff_ji >= p:
                    pref_ji = 1
                else:
                    pref_ji = (diff_ji - q) / (p - q)

                pi_ij += weights[k] * pref_ij
                pi_ji += weights[k] * pref_ji

            phi_plus[i] += pi_ij / (m - 1)
            phi_minus[i] += pi_ji / (m - 1)

    net_flow = phi_plus - phi_minus
    return net_flow


# ═════════════════════════════════════════════════════════════════════
#  4. Weighted Sum Model (WSM)
# ═════════════════════════════════════════════════════════════════════
def wsm(decision_matrix: np.ndarray, weights: np.ndarray) -> np.ndarray:
    """Simple weighted sum. All criteria must be benefit-type and normalized."""
    # Min-max normalize each column to 0-1
    mins = decision_matrix.min(axis=0)
    maxs = decision_matrix.max(axis=0)
    ranges = maxs - mins
    ranges[ranges == 0] = 1
    normed = (decision_matrix - mins) / ranges
    return normed @ weights


# ═════════════════════════════════════════════════════════════════════
#  5. Run Scorecard Generation
# ═════════════════════════════════════════════════════════════════════
def tier_from_score(score: float) -> str:
    if score >= 80:
        return "Strategic"
    elif score >= 65:
        return "Preferred"
    elif score >= 50:
        return "Approved"
    elif score >= 35:
        return "Conditional"
    return "Blocked"


def run_mcda(method: str = "TOPSIS",
             period_year: int = 2024,
             period_quarter: int = None,
             custom_weights: dict = None):
    """
    Execute MCDA and persist results to supplier_scorecards.
    """
    weights_dict = custom_weights or config.MCDA_DEFAULT_WEIGHTS
    criteria = ["cost", "quality", "delivery", "risk", "esg", "innovation", "compliance"]
    score_cols = [
        "cost_score", "quality_score", "delivery_score",
        "risk_score", "esg_score", "innovation_score", "financial_score"
    ]

    w = np.array([weights_dict.get(c, 0.1) for c in criteria])
    w = w / w.sum()  # Ensure sums to 1

    with ENGINE.connect() as conn:
        df = build_decision_matrix(conn, period_year, period_quarter)

    if df.empty:
        log.warning("No data for the selected period.")
        return pd.DataFrame()

    dm = df[score_cols].values.astype(float)
    dm = np.nan_to_num(dm, nan=50.0)

    if method == "TOPSIS":
        scores = topsis(dm, w) * 100
    elif method == "PROMETHEE":
        raw = promethee_ii(dm, w)
        # Normalize to 0-100
        mn, mx = raw.min(), raw.max()
        scores = ((raw - mn) / (mx - mn + 1e-9)) * 100
    else:  # WSM
        scores = wsm(dm, w) * 100

    df["composite_score"] = np.round(scores, 2)
    df["rank"] = df["composite_score"].rank(ascending=False, method="min").astype(int)
    df["tier_recommendation"] = df["composite_score"].apply(tier_from_score)
    df["methodology"] = method

    period_label = f"{period_year}-Q{period_quarter}" if period_quarter else str(period_year)

    # Persist
    records = []
    for _, row in df.iterrows():
        records.append({
            "supplier_id": int(row["supplier_id"]),
            "assessment_date": pd.Timestamp.now().date(),
            "period_label": period_label,
            "cost_score": float(row["cost_score"]),
            "quality_score": float(row["quality_score"]),
            "delivery_score": float(row["delivery_score"]),
            "risk_score": float(row["risk_score"]),
            "esg_score": float(row["esg_score"]),
            "innovation_score": float(row["innovation_score"]),
            "financial_score": float(row["financial_score"]),
            "w_cost": float(w[0]),
            "w_quality": float(w[1]),
            "w_delivery": float(w[2]),
            "w_risk": float(w[3]),
            "w_esg": float(w[4]),
            "w_innovation": float(w[5]),
            "w_financial": float(w[6]),
            "composite_score": float(row["composite_score"]),
            "rank": int(row["rank"]),
            "tier_recommendation": row["tier_recommendation"],
            "methodology": method,
        })

    with ENGINE.begin() as conn:
        conn.execute(text("""
            INSERT INTO supplier_scorecards
                (supplier_id, assessment_date, period_label,
                 cost_score, quality_score, delivery_score,
                 risk_score, esg_score, innovation_score, financial_score,
                 w_cost, w_quality, w_delivery, w_risk, w_esg,
                 w_innovation, w_financial,
                 composite_score, `rank`, tier_recommendation, methodology)
            VALUES
                (:supplier_id, :assessment_date, :period_label,
                 :cost_score, :quality_score, :delivery_score,
                 :risk_score, :esg_score, :innovation_score, :financial_score,
                 :w_cost, :w_quality, :w_delivery, :w_risk, :w_esg,
                 :w_innovation, :w_financial,
                 :composite_score, :rank, :tier_recommendation, :methodology)
        """), records)

    log.info(f"MCDA ({method}) complete -- {len(records)} suppliers scored for {period_label}")
    return df


if __name__ == "__main__":
    result = run_mcda("TOPSIS", 2024)
    if not result.empty:
        log.info(result[["supplier_name", "composite_score", "rank", "tier_recommendation"]]
              .sort_values("rank").head(15).to_string(index=False))
