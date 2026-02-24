"""
AEGIS — Working Capital & Cash Flow Analytics
Invoice payment analysis, DPO/DSO, early payment discount optimization.
"""

import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

ENGINE = create_engine(config.DATABASE_URL, echo=False)


def analyze_working_capital(year: int = 2024) -> dict:
    """Comprehensive working capital analysis."""

    with ENGINE.connect() as conn:
        # Invoice aging
        aging = pd.read_sql(text("""
            SELECT
                s.supplier_name,
                s.tier_level,
                COUNT(*) AS invoice_count,
                SUM(i.amount_usd) AS total_amount,
                AVG(i.days_to_pay) AS avg_dtp,
                AVG(s.payment_terms_days) AS avg_terms,
                SUM(CASE WHEN i.due_date < CURDATE() AND i.status NOT IN ('Paid','Cancelled')
                    THEN i.amount_usd ELSE 0 END) AS overdue_amount,
                SUM(CASE WHEN i.early_payment_discount_taken THEN i.amount_usd * 0.02
                    ELSE 0 END) AS discount_captured,
                SUM(CASE WHEN NOT i.early_payment_discount_taken
                    AND i.payment_date IS NOT NULL
                    AND i.payment_date <= i.due_date
                    THEN i.amount_usd * 0.02 ELSE 0 END) AS discount_missed
            FROM invoices i
            JOIN suppliers s ON i.supplier_id = s.supplier_id
            WHERE YEAR(i.invoice_date) = :year
            GROUP BY s.supplier_id, s.supplier_name, s.tier_level
            ORDER BY total_amount DESC
        """), conn, params={"year": year})

        # DPO by month
        dpo_trend = pd.read_sql(text("""
            SELECT
                CONCAT(YEAR(i.invoice_date), '-', LPAD(MONTH(i.invoice_date), 2, '0')) AS month,
                AVG(i.days_to_pay) AS avg_dpo,
                SUM(i.amount_usd) AS total_spend,
                COUNT(*) AS invoice_count,
                SUM(CASE WHEN i.due_date < CURDATE() AND i.status NOT IN ('Paid','Cancelled')
                    THEN 1 ELSE 0 END) AS overdue_count
            FROM invoices i
            WHERE YEAR(i.invoice_date) = :year AND i.payment_date IS NOT NULL
            GROUP BY month
            ORDER BY month
        """), conn, params={"year": year})

        # Cash flow impact of early payment
        epd_analysis = pd.read_sql(text("""
            SELECT
                s.payment_terms_days AS terms,
                COUNT(*) AS invoice_count,
                SUM(i.amount_usd) AS total_value,
                SUM(CASE WHEN i.early_payment_discount_taken
                    THEN i.amount_usd ELSE 0 END) AS discount_captured_value,
                AVG(CASE WHEN i.early_payment_discount_taken
                    THEN i.days_to_pay ELSE NULL END) AS avg_early_dtp
            FROM invoices i
            JOIN suppliers s ON i.supplier_id = s.supplier_id
            WHERE YEAR(i.invoice_date) = :year
            GROUP BY s.payment_terms_days
            ORDER BY terms
        """), conn, params={"year": year})

    # Summary metrics
    total_spend = aging["total_amount"].sum() if not aging.empty else 0
    total_overdue = aging["overdue_amount"].sum() if not aging.empty else 0
    discount_captured = aging["discount_captured"].sum() if not aging.empty else 0
    discount_missed = aging["discount_missed"].sum() if not aging.empty else 0
    avg_dpo = dpo_trend["avg_dpo"].mean() if not dpo_trend.empty else 0

    return {
        "year": year,
        "total_spend": total_spend,
        "total_overdue": total_overdue,
        "overdue_pct": (total_overdue / total_spend * 100) if total_spend else 0,
        "avg_dpo": avg_dpo,
        "discount_captured": discount_captured,
        "discount_missed": discount_missed,
        "discount_opportunity": discount_captured + discount_missed,
        "aging_by_supplier": aging,
        "dpo_trend": dpo_trend,
        "epd_analysis": epd_analysis,
    }


def optimize_payment_timing(budget_constraint_usd: float = 500_000,
                            discount_rate_annual: float = 0.08) -> pd.DataFrame:
    """
    Optimize which invoices to pay early for maximum ROI.
    Uses annualized return vs cost of capital comparison.
    """
    with ENGINE.connect() as conn:
        pending = pd.read_sql(text("""
            SELECT
                i.invoice_id,
                i.supplier_id,
                s.supplier_name,
                i.amount_usd,
                s.payment_terms_days,
                i.due_date,
                c.early_payment_discount_pct
            FROM invoices i
            JOIN suppliers s ON i.supplier_id = s.supplier_id
            LEFT JOIN purchase_orders po ON i.po_id = po.po_id
            LEFT JOIN contracts c ON po.contract_id = c.contract_id
            WHERE i.status = 'Pending'
              AND c.early_payment_discount_pct > 0
            ORDER BY i.amount_usd DESC
        """), conn)

    if pending.empty:
        return pending

    # Calculate annualized return for early payment
    pending["discount_pct"] = pending["early_payment_discount_pct"].fillna(2.0)
    pending["days_early"] = pending["payment_terms_days"] - 10  # Pay on day 10
    pending["savings_usd"] = pending["amount_usd"] * pending["discount_pct"] / 100
    pending["annualized_return"] = (
        pending["discount_pct"] / 100 * 365 / pending["days_early"].clip(lower=1))

    # Select invoices where annualized return > cost of capital
    daily_rate = discount_rate_annual / 365
    pending["roi_vs_capital"] = pending["annualized_return"] - discount_rate_annual
    eligible = pending[pending["roi_vs_capital"] > 0].sort_values(
        "annualized_return", ascending=False)

    # Greedy selection within budget
    selected = []
    remaining = budget_constraint_usd
    for _, row in eligible.iterrows():
        if row["amount_usd"] <= remaining:
            selected.append(row)
            remaining -= row["amount_usd"]

    result = pd.DataFrame(selected) if selected else pd.DataFrame()
    if not result.empty:
        print(f"[OK] {len(result)} invoices selected for early payment")
        print(f"  Total: ${result['amount_usd'].sum():,.0f}")
        print(f"  Savings: ${result['savings_usd'].sum():,.0f}")
        print(f"  Avg annualized return: {result['annualized_return'].mean():.1%}")

    return result


if __name__ == "__main__":
    wc = analyze_working_capital(2024)
    print(f"Total Spend: ${wc['total_spend']:,.0f}")
    print(f"Avg DPO: {wc['avg_dpo']:.1f} days")
    print(f"Overdue: ${wc['total_overdue']:,.0f} ({wc['overdue_pct']:.1f}%)")
    print(f"Discount Captured: ${wc['discount_captured']:,.0f}")
    print(f"Discount Missed: ${wc['discount_missed']:,.0f}")
