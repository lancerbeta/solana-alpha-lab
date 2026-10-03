"""One-time, explicit call-ledger index preparation after a verified backup.

Run only during the separately authorized commissioning window. No payload is
read or printed. An existing populated store is never migrated on startup.
"""

from __future__ import annotations

import argparse
import shutil
import sqlite3
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from solana_alpha_lab.factory.observation_schedule_store import (  # noqa: E402
    OPERABILITY_INDEX_SQL,
    OPERABILITY_TIME_SQL,
)


def prepare(path: Path) -> dict[str, object]:
    if not path.is_absolute() or path.is_symlink() or not path.is_file():
        raise RuntimeError("STORE_PATH_INVALID")
    size = path.stat().st_size
    if shutil.disk_usage(path.parent).free < max(size * 2, 1 << 30):
        raise RuntimeError("INSUFFICIENT_FREE_SPACE")
    started = time.monotonic()
    conn = sqlite3.connect(path, timeout=5)
    try:
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute("PRAGMA cache_size=-8192")
        conn.execute("PRAGMA temp_store=FILE")
        conn.set_progress_handler(lambda: int(time.monotonic() - started >= 120), 1000)
        conn.execute("BEGIN IMMEDIATE")
        if conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='call_ledger'").fetchone() is None:
            raise RuntimeError("CALL_LEDGER_MISSING")
        existing = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='index' AND name='idx_call_ledger_operability_time'"
        ).fetchone()
        if existing is not None and existing[0].replace("IF NOT EXISTS ", "") != OPERABILITY_INDEX_SQL.replace("IF NOT EXISTS ", ""):
            raise RuntimeError("INDEX_DEFINITION_MISMATCH")
        conn.execute(OPERABILITY_INDEX_SQL)
        plan = conn.execute(
            f"EXPLAIN QUERY PLAN SELECT primitive_id FROM call_ledger WHERE {OPERABILITY_TIME_SQL} >= julianday(?)",
            ("2026-01-01T00:00:00Z",),
        ).fetchall()
        if not any("idx_call_ledger_operability_time" in str(row) for row in plan):
            raise RuntimeError("INDEX_NOT_USED")
        conn.commit()
        return {"result": "PASS", "index": "idx_call_ledger_operability_time",
                "db_bytes_before": size, "elapsed_seconds": round(time.monotonic() - started, 3)}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True, type=Path)
    args = parser.parse_args()
    try:
        result = prepare(args.db)
    except (RuntimeError, sqlite3.Error, OSError) as exc:
        # Errors are typed and contain no absolute path, query result or payload.
        code = str(exc) if isinstance(exc, RuntimeError) else "SQLITE_INDEX_PREPARATION_FAILED"
        if isinstance(exc, sqlite3.Error):
            primary = getattr(exc, "sqlite_errorcode", 0) & 0xFF
            code = {
                sqlite3.SQLITE_BUSY: "STORE_BUSY",
                sqlite3.SQLITE_LOCKED: "STORE_BUSY",
                sqlite3.SQLITE_INTERRUPT: "INDEX_PREPARATION_DEADLINE",
            }.get(primary, code)
        print(f"INDEX_PREPARATION={code}")
        raise SystemExit(2) from None
    print(" ".join(f"{key}={value}" for key, value in result.items()))


if __name__ == "__main__":
    main()
