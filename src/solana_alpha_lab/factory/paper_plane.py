"""Generic research-to-paper plane: StrategyVersion configs in, bot and
position lifecycle out. Owns no scientific truth and never produces
REAL_FILL."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Mapping

import jsonschema
import yaml

SCHEMA_RELATIVE = "catalog/schemas/strategy_version.schema.json"
SIGNAL_KINDS = frozenset(
    {
        "NO_SIGNAL",
        "NO_ROUTE",
        "QUOTE_UNAVAILABLE",
        "UNKNOWN",
        "SIMULATED_FILL",
        "SHADOW_EXECUTABLE",
        "REAL_FILL",
    }
)
POSITION_STATES = (
    "WATCHED",
    "SIGNALLED",
    "INTENT_CREATED",
    "ATTEMPTING",
    "OPEN",
    "PARTIAL",
    "UNKNOWN",
    "EXIT_REQUIRED",
    "EXITING",
    "CLOSED",
    "UNRESOLVED",
    "RECONCILED",
)
TRANSITIONS: dict[str, set[str]] = {
    "WATCHED": {"SIGNALLED"},
    "SIGNALLED": {"INTENT_CREATED"},
    "INTENT_CREATED": {"ATTEMPTING"},
    "ATTEMPTING": {"OPEN", "PARTIAL", "UNKNOWN", "UNRESOLVED"},
    "OPEN": {"EXIT_REQUIRED", "EXITING"},
    "PARTIAL": {"EXIT_REQUIRED", "EXITING"},
    "UNKNOWN": {"EXIT_REQUIRED", "EXITING", "UNRESOLVED", "RECONCILED"},
    "EXIT_REQUIRED": {"EXITING"},
    "EXITING": {"CLOSED", "UNRESOLVED"},
    "CLOSED": {"RECONCILED"},
    "UNRESOLVED": {"RECONCILED"},
    "RECONCILED": set(),
}
FORBIDDEN_SIGNAL_KINDS = frozenset({"REAL_FILL"})


class PaperPlaneError(ValueError):
    """Raised when a strategy version or paper-plane transition is invalid."""


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def load_strategy_version(root: Path, relative: str) -> dict[str, Any]:
    candidate = Path(relative)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise PaperPlaneError("STRATEGY_PATH_UNSAFE")
    path = root / candidate
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise PaperPlaneError("STRATEGY_MISSING") from exc
    if not isinstance(loaded, dict):
        raise PaperPlaneError("STRATEGY_INVALID")
    schema = json.loads((root / SCHEMA_RELATIVE).read_text(encoding="utf-8"))
    try:
        jsonschema.validate(loaded, schema)
    except jsonschema.ValidationError as exc:
        raise PaperPlaneError("STRATEGY_SCHEMA_INVALID") from exc
    unsigned = dict(loaded)
    claimed = str(unsigned.pop("spec_sha256"))
    actual = hashlib.sha256(
        (json.dumps(unsigned, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
    ).hexdigest()
    if claimed != actual:
        raise PaperPlaneError("SPEC_SHA256_MISMATCH")
    return loaded


def signal_kind_for(
    strategy: Mapping[str, Any],
    row: Mapping[str, Any],
) -> str:
    """Evaluate one decision-time row against one declarative signal rule.

    Data-driven: the rule comes from config; missing feature data yields
    UNKNOWN, never zero.
    """

    rule = strategy["signal_rule"]
    value = row.get(str(rule["feature"]))
    if value is None:
        return "UNKNOWN"
    threshold = Decimal(str(rule["bin_threshold"]))
    try:
        numeric = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return "UNKNOWN"
    op = str(rule["bin_op"])
    high = numeric >= threshold if op == ">=" else numeric > threshold
    entry_kinds = list(strategy["entry_rule"]["when_signal_kind_in"])
    return entry_kinds[0] if high else "NO_SIGNAL"


class PaperPlaneStore:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS bot_instances (
                bot_instance_id TEXT PRIMARY KEY,
                strategy_id TEXT NOT NULL,
                strategy_version TEXT NOT NULL,
                mode TEXT NOT NULL CHECK (mode IN ('PAPER','SHADOW')),
                status TEXT NOT NULL,
                started_at TEXT NOT NULL,
                stopped_at TEXT
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS positions (
                position_id TEXT PRIMARY KEY,
                bot_instance_id TEXT NOT NULL,
                mint TEXT NOT NULL,
                state TEXT NOT NULL,
                signal_kind TEXT,
                entered_notional_usd REAL,
                exit_notional_usd REAL,
                opened_at TEXT,
                closed_at TEXT
            )
            """
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def start_bot(self, strategy: Mapping[str, Any], *, mode: str = "PAPER") -> dict[str, Any]:
        if mode not in {"PAPER", "SHADOW"}:
            raise PaperPlaneError("BOT_MODE_INVALID")
        bot_instance_id = f"BOT-{strategy['strategy_id']}-{strategy['strategy_version']}-{mode}"
        existing = self.get_bot(bot_instance_id)
        if existing is not None and existing["status"] == "RUNNING":
            return existing
        record = {
            "bot_instance_id": bot_instance_id,
            "strategy_id": str(strategy["strategy_id"]),
            "strategy_version": f"{strategy['strategy_id']}-{strategy['strategy_version']}",
            "mode": mode,
            "status": "RUNNING",
            "started_at": _now(),
            "stopped_at": None,
        }
        self._conn.execute(
            """
            INSERT INTO bot_instances(
                bot_instance_id, strategy_id, strategy_version, mode,
                status, started_at, stopped_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(bot_instance_id) DO UPDATE SET
                status=excluded.status, stopped_at=excluded.stopped_at
            """,
            (
                record["bot_instance_id"], record["strategy_id"],
                record["strategy_version"], record["mode"],
                record["status"], record["started_at"], None,
            ),
        )
        self._conn.commit()
        return record

    def get_bot(self, bot_instance_id: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM bot_instances WHERE bot_instance_id = ?", (bot_instance_id,)
        ).fetchone()
        return dict(row) if row else None

    def bots(self) -> list[dict[str, Any]]:
        rows = self._conn.execute("SELECT * FROM bot_instances ORDER BY started_at").fetchall()
        return [dict(row) for row in rows]

    def open_position(self, *, bot_instance_id: str, mint: str, signal_kind: str) -> str:
        if signal_kind in FORBIDDEN_SIGNAL_KINDS:
            raise PaperPlaneError("REAL_FILL_FORBIDDEN_IN_PAPER_PLANE")
        if signal_kind not in SIGNAL_KINDS:
            raise PaperPlaneError("SIGNAL_KIND_INVALID")
        position_id = f"POS-{bot_instance_id}-{mint[:12]}-{signal_kind}"
        self._conn.execute(
            """
            INSERT INTO positions(
                position_id, bot_instance_id, mint, state, signal_kind,
                opened_at
            ) VALUES (?, ?, ?, 'WATCHED', ?, ?)
            ON CONFLICT(position_id) DO NOTHING
            """,
            (position_id, bot_instance_id, mint, signal_kind, _now()),
        )
        self._conn.commit()
        return position_id

    def transition(self, position_id: str, to_state: str) -> dict[str, Any]:
        row = self._conn.execute(
            "SELECT * FROM positions WHERE position_id = ?", (position_id,)
        ).fetchone()
        if row is None:
            raise PaperPlaneError("POSITION_NOT_FOUND")
        current = str(row["state"])
        if to_state not in TRANSITIONS.get(current, set()):
            raise PaperPlaneError(f"ILLEGAL_TRANSITION:{current}->{to_state}")
        closed_at = _now() if to_state in {"CLOSED", "RECONCILED"} else None
        self._conn.execute(
            "UPDATE positions SET state = ?, closed_at = COALESCE(?, closed_at) WHERE position_id = ?",
            (to_state, closed_at, position_id),
        )
        self._conn.commit()
        updated = self.get_position(position_id)
        assert updated is not None
        return updated

    def get_position(self, position_id: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM positions WHERE position_id = ?", (position_id,)
        ).fetchone()
        return dict(row) if row else None

    def position_id_for(self, *, bot_instance_id: str, mint: str, signal_kind: str) -> str:
        return f"POS-{bot_instance_id}-{mint[:12]}-{signal_kind}"

    def positions(self) -> list[dict[str, Any]]:
        rows = self._conn.execute("SELECT * FROM positions ORDER BY opened_at").fetchall()
        return [dict(row) for row in rows]

    def fill_paper(self, *, bot_instance_id: str, mint: str, notional_usd: Decimal) -> tuple[str, str]:
        position_id = self.open_position(
            bot_instance_id=bot_instance_id,
            mint=mint,
            signal_kind="SIMULATED_FILL",
        )
        self.transition(position_id, "SIGNALLED")
        self.transition(position_id, "INTENT_CREATED")
        self.transition(position_id, "ATTEMPTING")
        self.transition(position_id, "OPEN")
        self._conn.execute(
            "UPDATE positions SET entered_notional_usd=? WHERE position_id=?",
            (float(notional_usd), position_id),
        )
        self._conn.commit()
        return position_id, "SIMULATED_FILL"


def run_commissioning(
    root: Path,
    *,
    strategy_relatives: list[str],
    store_path: Path,
    cohort: list[Mapping[str, Any]],
) -> dict[str, Any]:
    """Drive both config-only strategies through the identical engine."""

    store = PaperPlaneStore(store_path)
    try:
        per_strategy: list[dict[str, Any]] = []
        for relative in strategy_relatives:
            strategy = load_strategy_version(root, relative)
            bot = store.start_bot(strategy, mode="PAPER")
            filled = 0
            skipped = 0
            for row in cohort:
                kind = signal_kind_for(strategy, row)
                if kind == "SIMULATED_FILL":
                    position_id = store.position_id_for(
                        bot_instance_id=bot["bot_instance_id"],
                        mint=str(row.get("mint")),
                        signal_kind="SIMULATED_FILL",
                    )
                    existing = store.get_position(position_id)
                    if existing is not None and existing["state"] == "RECONCILED":
                        filled += 1
                        continue
                    _, realized = store.fill_paper(
                        bot_instance_id=bot["bot_instance_id"],
                        mint=str(row.get("mint")),
                        notional_usd=Decimal(
                            str(strategy["notional_policy"]["notional_usd"])
                        ),
                    )
                    if realized == "SIMULATED_FILL":
                        filled += 1
                    store.transition(position_id, "EXIT_REQUIRED")
                    store.transition(position_id, "EXITING")
                    store.transition(position_id, "CLOSED")
                    store.transition(position_id, "RECONCILED")
                else:
                    skipped += 1
            per_strategy.append(
                {
                    "strategy_relative": relative,
                    "strategy_id": strategy["strategy_id"],
                    "strategy_version": strategy["strategy_version"],
                    "signal_feature": strategy["signal_rule"]["feature"],
                    "bot_instance_id": bot["bot_instance_id"],
                    "simulated_fills": filled,
                    "no_signal_or_unknown": skipped,
                }
            )
        return {
            "engine": "paper_plane_v1",
            "factory_core_python_changed": False,
            "per_strategy": per_strategy,
            "bot_instances": store.bots(),
            "positions": store.positions(),
        }
    finally:
        store.close()
