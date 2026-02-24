"""
AEGIS — Data Freshness Tracker
Records pipeline run timestamps and shows freshness in the dashboard.
"""

import datetime as dt
from utils.logging_config import get_logger, _get_connection

log = get_logger("freshness")

# Table is created in schema file 08_create_audit_tables.sql
# If not present, we create it on the fly.
_ENSURE_TABLE = """
CREATE TABLE IF NOT EXISTS pipeline_runs (
    run_id       INT AUTO_INCREMENT PRIMARY KEY,
    started_at   DATETIME NOT NULL,
    finished_at  DATETIME NULL,
    status       ENUM('running','success','failed') DEFAULT 'running',
    duration_sec FLOAT NULL,
    steps_run    TEXT NULL,
    INDEX idx_started (started_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""


def record_start() -> int:
    """Record pipeline start. Returns run_id."""
    try:
        conn = _get_connection()
        with conn.cursor() as cur:
            cur.execute(_ENSURE_TABLE)
            cur.execute(
                "INSERT INTO pipeline_runs (started_at) VALUES (%s)",
                (dt.datetime.now(),),
            )
            run_id = cur.lastrowid
        conn.close()
        log.info("Pipeline run #%d started", run_id)
        return run_id
    except Exception:
        log.warning("Could not record pipeline start", exc_info=True)
        return 0


def record_finish(run_id: int, status: str = "success",
                  duration: float = 0.0, steps: str = ""):
    """Record pipeline end."""
    if run_id == 0:
        return
    try:
        conn = _get_connection()
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE pipeline_runs "
                "SET finished_at=%s, status=%s, duration_sec=%s, steps_run=%s "
                "WHERE run_id=%s",
                (dt.datetime.now(), status, duration, steps, run_id),
            )
        conn.close()
        log.info("Pipeline run #%d finished (%s, %.1fs)", run_id, status, duration)
    except Exception:
        log.warning("Could not record pipeline finish", exc_info=True)


def get_last_run() -> dict | None:
    """Return the most recent successful pipeline run, or None."""
    try:
        conn = _get_connection()
        with conn.cursor() as cur:
            cur.execute(_ENSURE_TABLE)
            cur.execute(
                "SELECT run_id, started_at, finished_at, status, duration_sec "
                "FROM pipeline_runs "
                "WHERE status='success' "
                "ORDER BY finished_at DESC LIMIT 1"
            )
            row = cur.fetchone()
        conn.close()
        if row:
            return {
                "run_id": row[0],
                "started_at": row[1],
                "finished_at": row[2],
                "status": row[3],
                "duration_sec": row[4],
            }
        return None
    except Exception:
        return None


def freshness_badge() -> str:
    """Return a human-readable freshness string for the sidebar."""
    last = get_last_run()
    if not last or not last["finished_at"]:
        return "⚠️ No pipeline run recorded"

    age = dt.datetime.now() - last["finished_at"]
    hours = age.total_seconds() / 3600

    if hours < 1:
        return f"🟢 Fresh ({int(age.total_seconds()//60)}m ago)"
    elif hours < 24:
        return f"🟡 {hours:.0f}h ago"
    else:
        days = hours / 24
        return f"🔴 Stale ({days:.0f}d ago)"
