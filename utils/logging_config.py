"""
AEGIS — Centralised Logging & Audit Trail
==========================================
• get_logger(name)          → stdlib logger with console + file output
• AuditLogger               → writes to audit_log table
• DataQualityLogger         → writes to data_quality_log table
"""

import logging
import sys
import os
import datetime as dt
from pathlib import Path

import config

# ── Log directory ────────────────────────────────────────────────────
LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

# ── Formatter ────────────────────────────────────────────────────────
_FMT = "%(asctime)s  %(levelname)-8s  [%(name)s]  %(message)s"
_DATE_FMT = "%Y-%m-%d %H:%M:%S"
_formatter = logging.Formatter(_FMT, datefmt=_DATE_FMT)

# ── Shared file handler (all modules → single log file) ─────────────
_file_handler = logging.FileHandler(
    LOG_DIR / "aegis_pipeline.log", encoding="utf-8"
)
_file_handler.setFormatter(_formatter)
_file_handler.setLevel(logging.DEBUG)

# ── Console handler ─────────────────────────────────────────────────
_console_handler = logging.StreamHandler(sys.stdout)
_console_handler.setFormatter(_formatter)
_console_handler.setLevel(logging.INFO)


def get_logger(name: str) -> logging.Logger:
    """Return a named logger that writes to both console and log file."""
    logger = logging.getLogger(f"aegis.{name}")
    if not logger.handlers:
        logger.setLevel(logging.DEBUG)
        logger.addHandler(_file_handler)
        logger.addHandler(_console_handler)
        logger.propagate = False
    return logger


# ── Database audit helpers ───────────────────────────────────────────
def _get_connection():
    """Obtain a raw PyMySQL connection (same pattern as pipeline)."""
    import pymysql
    from urllib.parse import urlparse

    parsed = urlparse(config.DATABASE_URL)
    return pymysql.connect(
        host=parsed.hostname or "localhost",
        port=parsed.port or 3306,
        user=parsed.username or "root",
        password=parsed.password or "",
        database=parsed.path.lstrip("/"),
        charset="utf8mb4",
        autocommit=True,
    )


class AuditLogger:
    """Write to the *audit_log* table for row-level change tracking."""

    _INSERT = (
        "INSERT INTO audit_log "
        "(table_name, record_id, action, old_values, new_values, changed_by) "
        "VALUES (%s, %s, %s, %s, %s, %s)"
    )

    def __init__(self, changed_by: str = "aegis_pipeline"):
        self.changed_by = changed_by

    def log(
        self,
        table_name: str,
        record_id: int,
        action: str,
        old_values: str | None = None,
        new_values: str | None = None,
    ):
        try:
            conn = _get_connection()
            with conn.cursor() as cur:
                cur.execute(
                    self._INSERT,
                    (table_name, record_id, action, old_values, new_values, self.changed_by),
                )
            conn.close()
        except Exception:
            get_logger("audit").warning(
                "Could not write audit_log row for %s/%s", table_name, record_id,
                exc_info=True,
            )


class DataQualityLogger:
    """Write to the *data_quality_log* table after DQ checks."""

    _INSERT = (
        "INSERT INTO data_quality_log "
        "(check_name, check_type, table_name, column_name, "
        " records_checked, records_failed, severity, details) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"
    )

    def log(
        self,
        check_name: str,
        check_type: str,
        table_name: str,
        column_name: str | None,
        records_checked: int,
        records_failed: int,
        severity: str = "Info",
        details: str | None = None,
    ):
        try:
            conn = _get_connection()
            with conn.cursor() as cur:
                cur.execute(
                    self._INSERT,
                    (
                        check_name,
                        check_type,
                        table_name,
                        column_name,
                        records_checked,
                        records_failed,
                        severity,
                        details,
                    ),
                )
            conn.close()
        except Exception:
            get_logger("dq").warning(
                "Could not write data_quality_log row for %s.%s",
                table_name,
                check_name,
                exc_info=True,
            )
