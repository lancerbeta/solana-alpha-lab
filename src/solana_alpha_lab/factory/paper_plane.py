"""Generic research-to-paper plane: StrategyVersion configs in, bot and
position lifecycle out. Owns no scientific truth and never produces
REAL_FILL.

v1.0 commissioning path retains declarative signal_rule evaluation.
v1.1 candidate path consumes already-frozen SignalDecision / ExitDecision
and never inspects scientific feature names.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Mapping

from solana_alpha_lab.factory.strategy_runtime import (
    PaperPlaneError,
    load_strategy_version,
    normalize_strategy,
    position_id_for_signal_decision,
    validate_exit_decision,
    validate_signal_decision,
)

# Re-export for legacy callers/tests.
__all__ = [
    "PaperPlaneError",
    "PaperPlaneStore",
    "accept_exit_decision",
    "accept_signal_decision",
    "load_strategy_version",
    "observe_shadow",
    "run_commissioning",
    "run_shadow_tick",
    "signal_kind_for",
]

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
OPEN_RISK_STATES = frozenset(
    {"WATCHED", "SIGNALLED", "INTENT_CREATED", "ATTEMPTING", "OPEN", "PARTIAL", "UNKNOWN"}
)


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def signal_kind_for(
    strategy: Mapping[str, Any],
    row: Mapping[str, Any],
) -> str:
    """Evaluate one decision-time row against one declarative signal rule.

    Legacy v1.0 compatibility path only. v1.1 must not call this.
    Missing feature data yields UNKNOWN, never zero.
    """

    if str(strategy.get("schema_version", "1.0")) == "1.1":
        raise PaperPlaneError("SIGNAL_KIND_FOR_FORBIDDEN_ON_V1_1")
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


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {str(row[1]) for row in rows}


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, ddl_type: str) -> None:
    if column in _table_columns(conn, table):
        return
    conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl_type}")


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
        self._migrate_v1_1_lineage()
        self._conn.commit()

    def _migrate_v1_1_lineage(self) -> None:
        """Idempotent additive columns for v1.1 lineage. Legacy rows may be NULL."""

        _ensure_column(self._conn, "bot_instances", "activation_epoch_id", "TEXT")
        _ensure_column(self._conn, "bot_instances", "runtime_schema_version", "TEXT")
        _ensure_column(self._conn, "positions", "signal_decision_id", "TEXT")
        _ensure_column(self._conn, "positions", "activation_epoch_id", "TEXT")
        _ensure_column(self._conn, "positions", "strategy_id", "TEXT")
        _ensure_column(self._conn, "positions", "strategy_version_label", "TEXT")
        _ensure_column(self._conn, "positions", "exit_decision_id", "TEXT")
        _ensure_column(self._conn, "positions", "reason_code", "TEXT")
        self._conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_positions_signal_decision_id
            ON positions(signal_decision_id)
            """
        )
        self._conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_bot_activation_epoch_id
            ON bot_instances(activation_epoch_id)
            """
        )

    def close(self) -> None:
        self._conn.close()

    def start_bot(
        self,
        strategy: Mapping[str, Any],
        *,
        mode: str = "PAPER",
        activation_epoch_id: str | None = None,
    ) -> dict[str, Any]:
        if mode not in {"PAPER", "SHADOW"}:
            raise PaperPlaneError("BOT_MODE_INVALID")
        schema_version = str(strategy.get("schema_version", "1.0"))
        if schema_version == "1.1":
            if not activation_epoch_id:
                raise PaperPlaneError("ACTIVATION_EPOCH_REQUIRED")
            bot_instance_id = (
                f"BOT-{strategy['strategy_id']}-{strategy['strategy_version']}"
                f"-{mode}-{activation_epoch_id}"
            )
        else:
            bot_instance_id = (
                f"BOT-{strategy['strategy_id']}-{strategy['strategy_version']}-{mode}"
            )
            activation_epoch_id = None
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
            "activation_epoch_id": activation_epoch_id,
            "runtime_schema_version": schema_version,
        }
        self._conn.execute(
            """
            INSERT INTO bot_instances(
                bot_instance_id, strategy_id, strategy_version, mode,
                status, started_at, stopped_at, activation_epoch_id,
                runtime_schema_version
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(bot_instance_id) DO UPDATE SET
                status=excluded.status,
                stopped_at=excluded.stopped_at,
                activation_epoch_id=COALESCE(excluded.activation_epoch_id, bot_instances.activation_epoch_id),
                runtime_schema_version=COALESCE(excluded.runtime_schema_version, bot_instances.runtime_schema_version)
            """,
            (
                record["bot_instance_id"],
                record["strategy_id"],
                record["strategy_version"],
                record["mode"],
                record["status"],
                record["started_at"],
                None,
                record["activation_epoch_id"],
                record["runtime_schema_version"],
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

    def open_position_from_signal(
        self,
        *,
        bot_instance_id: str,
        signal_decision: Mapping[str, Any],
        signal_kind: str = "SIMULATED_FILL",
    ) -> str:
        signal_decision_id = str(signal_decision["signal_decision_id"])
        position_id = position_id_for_signal_decision(signal_decision_id)
        self._conn.execute(
            """
            INSERT INTO positions(
                position_id, bot_instance_id, mint, state, signal_kind,
                opened_at, signal_decision_id, activation_epoch_id,
                strategy_id, strategy_version_label, reason_code
            ) VALUES (?, ?, ?, 'WATCHED', ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(position_id) DO NOTHING
            """,
            (
                position_id,
                bot_instance_id,
                str(signal_decision["mint"]),
                signal_kind,
                _now(),
                signal_decision_id,
                str(signal_decision["activation_epoch_id"]),
                str(signal_decision["strategy_id"]),
                str(signal_decision["strategy_version"]),
                str(signal_decision["reason_code"]),
            ),
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

    def open_risk_count(self, bot_instance_id: str) -> int:
        rows = self._conn.execute(
            "SELECT state FROM positions WHERE bot_instance_id = ?",
            (bot_instance_id,),
        ).fetchall()
        return sum(1 for row in rows if str(row["state"]) in OPEN_RISK_STATES)

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

    def fill_paper_from_signal(
        self,
        *,
        bot_instance_id: str,
        signal_decision: Mapping[str, Any],
        notional_usd: Decimal,
        signal_kind: str = "SIMULATED_FILL",
    ) -> tuple[str, str]:
        if signal_kind not in {"SIMULATED_FILL", "SHADOW_EXECUTABLE"}:
            raise PaperPlaneError("SIGNAL_KIND_INVALID")
        position_id = position_id_for_signal_decision(
            str(signal_decision["signal_decision_id"])
        )
        existing = self.get_position(position_id)
        if existing is None:
            self.open_position_from_signal(
                bot_instance_id=bot_instance_id,
                signal_decision=signal_decision,
                signal_kind=signal_kind,
            )
            existing = self.get_position(position_id)
        assert existing is not None
        if existing["state"] in {"OPEN", "PARTIAL", "EXIT_REQUIRED", "EXITING", "CLOSED", "RECONCILED", "UNRESOLVED"}:
            return position_id, str(existing.get("signal_kind") or signal_kind)
        # Resume incomplete lifecycle after crash/retry between commits.
        state = str(existing["state"])
        if state == "WATCHED":
            self._conn.execute(
                "UPDATE positions SET signal_kind=? WHERE position_id=?",
                (signal_kind, position_id),
            )
            self._conn.commit()
            self.transition(position_id, "SIGNALLED")
            state = "SIGNALLED"
        if state == "SIGNALLED":
            self.transition(position_id, "INTENT_CREATED")
            state = "INTENT_CREATED"
        if state == "INTENT_CREATED":
            self.transition(position_id, "ATTEMPTING")
            state = "ATTEMPTING"
        if state == "ATTEMPTING":
            self.transition(position_id, "OPEN")
        self._conn.execute(
            "UPDATE positions SET entered_notional_usd=?, signal_kind=? WHERE position_id=?",
            (float(notional_usd), signal_kind, position_id),
        )
        self._conn.commit()
        return position_id, signal_kind

    def apply_exit_decision(
        self,
        *,
        exit_decision: Mapping[str, Any],
    ) -> dict[str, Any]:
        position_id = str(exit_decision["position_id"])
        position = self.get_position(position_id)
        if position is None:
            raise PaperPlaneError("POSITION_NOT_FOUND")
        action = str(exit_decision["action"])
        if action != "EXIT":
            return {
                "position_id": position_id,
                "applied": False,
                "action": action,
                "state": position["state"],
            }
        if position["state"] == "EXIT_REQUIRED":
            self._conn.execute(
                "UPDATE positions SET exit_decision_id=?, reason_code=? WHERE position_id=?",
                (
                    str(exit_decision["exit_decision_id"]),
                    str(exit_decision["reason_code"]),
                    position_id,
                ),
            )
            self._conn.commit()
            updated = self.get_position(position_id)
            assert updated is not None
            return {
                "position_id": position_id,
                "applied": True,
                "action": action,
                "state": updated["state"],
                "fill_claimed": False,
            }
        if position["state"] not in {"OPEN", "PARTIAL", "UNKNOWN"}:
            raise PaperPlaneError(f"EXIT_DECISION_STATE_INVALID:{position['state']}")
        updated = self.transition(position_id, "EXIT_REQUIRED")
        self._conn.execute(
            "UPDATE positions SET exit_decision_id=?, reason_code=? WHERE position_id=?",
            (
                str(exit_decision["exit_decision_id"]),
                str(exit_decision["reason_code"]),
                position_id,
            ),
        )
        self._conn.commit()
        refreshed = self.get_position(position_id)
        assert refreshed is not None
        return {
            "position_id": position_id,
            "applied": True,
            "action": action,
            "state": refreshed["state"],
            "fill_claimed": False,
        }


def resolve_activation_epoch(
    activation_epoch_id: str,
    *,
    known_activation_epochs: Mapping[str, Any] | set[str] | frozenset[str],
) -> None:
    if isinstance(known_activation_epochs, Mapping):
        ok = activation_epoch_id in known_activation_epochs
    else:
        ok = activation_epoch_id in known_activation_epochs
    if not ok:
        raise PaperPlaneError("ACTIVATION_EPOCH_UNRESOLVED")


def accept_signal_decision(
    root: Path,
    store: PaperPlaneStore,
    *,
    strategy: Mapping[str, Any],
    signal_decision: Mapping[str, Any],
    known_activation_epochs: Mapping[str, Any] | set[str] | frozenset[str],
    mode: str = "PAPER",
    as_of: str | None = None,
) -> dict[str, Any]:
    """Consume a frozen SignalDecision on the v1.1 path. Feature-name agnostic."""

    if mode not in {"PAPER", "SHADOW"}:
        raise PaperPlaneError("BOT_MODE_INVALID")
    normalized = normalize_strategy(strategy)
    if normalized["runtime_path"] != "CANDIDATE_V1_1":
        raise PaperPlaneError("SIGNAL_DECISION_REQUIRES_V1_1")
    eligibility = strategy.get("mode_eligibility", {})
    if mode == "PAPER" and eligibility.get("paper") is not True:
        raise PaperPlaneError("PAPER_MODE_NOT_ELIGIBLE")
    if mode == "SHADOW" and eligibility.get("shadow") is not True:
        raise PaperPlaneError("SHADOW_MODE_NOT_ELIGIBLE")
    if eligibility.get("micro_live") is not False:
        raise PaperPlaneError("MICRO_LIVE_FORBIDDEN")
    decision = validate_signal_decision(root, signal_decision)
    if decision["strategy_id"] != strategy["strategy_id"]:
        raise PaperPlaneError("SIGNAL_STRATEGY_ID_MISMATCH")
    if decision["strategy_version"] != strategy["strategy_version"]:
        raise PaperPlaneError("SIGNAL_STRATEGY_VERSION_MISMATCH")
    resolve_activation_epoch(
        str(decision["activation_epoch_id"]),
        known_activation_epochs=known_activation_epochs,
    )
    if _parse_utc(decision["first_reliable_available_at"]) > _parse_utc(decision["decision_at"]):
        if decision["action"] == "ENTER":
            raise PaperPlaneError("SIGNAL_FUTURE_AVAILABLE_ENTER_FORBIDDEN")
    action = str(decision["action"])
    if action != "ENTER":
        return {
            "opened": False,
            "action": action,
            "reason_code": decision["reason_code"],
            "signal_decision_id": decision["signal_decision_id"],
            "position_id": None,
        }
    as_of_dt = _parse_utc(as_of) if as_of else _parse_utc(decision["decision_at"])
    decision_at = _parse_utc(decision["decision_at"])
    max_age = int(strategy["signal_input"]["max_age_seconds"])
    age_seconds = (as_of_dt - decision_at).total_seconds()
    if age_seconds > max_age:
        raise PaperPlaneError("SIGNAL_DECISION_STALE")
    position_id = position_id_for_signal_decision(str(decision["signal_decision_id"]))
    existing = store.get_position(position_id)
    if existing is not None:
        if existing.get("activation_epoch_id") and str(existing["activation_epoch_id"]) != str(
            decision["activation_epoch_id"]
        ):
            raise PaperPlaneError("SIGNAL_ACTIVATION_EPOCH_MISMATCH")
        if existing.get("strategy_id") and str(existing["strategy_id"]) != str(
            decision["strategy_id"]
        ):
            raise PaperPlaneError("SIGNAL_POSITION_STRATEGY_MISMATCH")
        expected_bot_id = (
            f"BOT-{strategy['strategy_id']}-{strategy['strategy_version']}"
            f"-{mode}-{decision['activation_epoch_id']}"
        )
        if existing.get("bot_instance_id") and str(existing["bot_instance_id"]) != expected_bot_id:
            raise PaperPlaneError("SIGNAL_BOT_INSTANCE_MISMATCH")
    bot = store.start_bot(
        strategy,
        mode=mode,
        activation_epoch_id=str(decision["activation_epoch_id"]),
    )
    if existing is not None:
        state = str(existing["state"])
        if state == "OPEN":
            return {
                "opened": True,
                "action": action,
                "reason_code": decision["reason_code"],
                "signal_decision_id": decision["signal_decision_id"],
                "position_id": position_id,
                "idempotent": True,
                "state": state,
                "bot_instance_id": bot["bot_instance_id"],
                "activation_epoch_id": decision["activation_epoch_id"],
            }
        if state in {
            "PARTIAL",
            "EXIT_REQUIRED",
            "EXITING",
            "CLOSED",
            "RECONCILED",
            "UNRESOLVED",
            "UNKNOWN",
        }:
            return {
                "opened": state in {"PARTIAL", "UNKNOWN"},
                "action": action,
                "reason_code": decision["reason_code"],
                "signal_decision_id": decision["signal_decision_id"],
                "position_id": position_id,
                "idempotent": True,
                "state": state,
                "bot_instance_id": bot["bot_instance_id"],
                "activation_epoch_id": decision["activation_epoch_id"],
            }
        # Incomplete pre-OPEN states fall through to resume.
    open_count = store.open_risk_count(bot["bot_instance_id"])
    max_open = int(strategy["risk_policy"]["max_open_positions"])
    # Resume does not consume a new risk slot when the same signal already exists.
    if existing is None and open_count >= max_open:
        raise PaperPlaneError("BLOCK_MAX_OPEN_POSITIONS")
    signal_kind = "SHADOW_EXECUTABLE" if mode == "SHADOW" else "SIMULATED_FILL"
    notional = Decimal(str(strategy["notional_policy"]["notional_usd"]))
    was_existing = existing is not None
    opened_id, realized = store.fill_paper_from_signal(
        bot_instance_id=bot["bot_instance_id"],
        signal_decision=decision,
        notional_usd=notional,
        signal_kind=signal_kind,
    )
    refreshed = store.get_position(opened_id)
    assert refreshed is not None
    return {
        "opened": refreshed["state"] == "OPEN",
        "action": action,
        "reason_code": decision["reason_code"],
        "signal_decision_id": decision["signal_decision_id"],
        "position_id": opened_id,
        "idempotent": was_existing,
        "state": refreshed["state"],
        "realized_signal_kind": realized,
        "bot_instance_id": bot["bot_instance_id"],
        "activation_epoch_id": decision["activation_epoch_id"],
    }


def accept_exit_decision(
    root: Path,
    store: PaperPlaneStore,
    *,
    strategy: Mapping[str, Any],
    exit_decision: Mapping[str, Any],
    known_activation_epochs: Mapping[str, Any] | set[str] | frozenset[str],
) -> dict[str, Any]:
    normalized = normalize_strategy(strategy)
    if normalized["runtime_path"] != "CANDIDATE_V1_1":
        raise PaperPlaneError("EXIT_DECISION_REQUIRES_V1_1")
    decision = validate_exit_decision(root, exit_decision)
    if decision["strategy_id"] != strategy["strategy_id"]:
        raise PaperPlaneError("EXIT_STRATEGY_ID_MISMATCH")
    if decision["strategy_version"] != strategy["strategy_version"]:
        raise PaperPlaneError("EXIT_STRATEGY_VERSION_MISMATCH")
    resolve_activation_epoch(
        str(decision["activation_epoch_id"]),
        known_activation_epochs=known_activation_epochs,
    )
    if _parse_utc(decision["first_reliable_available_at"]) > _parse_utc(decision["decision_at"]):
        if decision["action"] == "EXIT":
            raise PaperPlaneError("EXIT_FUTURE_AVAILABLE_FORBIDDEN")
    position = store.get_position(str(decision["position_id"]))
    if position is None:
        raise PaperPlaneError("POSITION_NOT_FOUND")
    if position.get("activation_epoch_id") and str(position["activation_epoch_id"]) != str(
        decision["activation_epoch_id"]
    ):
        raise PaperPlaneError("EXIT_ACTIVATION_EPOCH_MISMATCH")
    if position.get("strategy_id") and str(position["strategy_id"]) != str(decision["strategy_id"]):
        raise PaperPlaneError("EXIT_POSITION_STRATEGY_MISMATCH")
    result = store.apply_exit_decision(exit_decision=decision)
    result["exit_decision_id"] = decision["exit_decision_id"]
    result["fill_claimed"] = False
    return result


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
            if str(strategy.get("schema_version", "1.0")) != "1.0":
                raise PaperPlaneError("COMMISSIONING_REQUIRES_V1_0")
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


def observe_shadow(
    store: PaperPlaneStore,
    *,
    bot_instance_id: str,
    mint: str,
    notional_usd: Decimal,
) -> tuple[str, str]:
    """SHADOW observation lifecycle. Never REAL_FILL."""

    position_id = store.open_position(
        bot_instance_id=bot_instance_id,
        mint=mint,
        signal_kind="SHADOW_EXECUTABLE",
    )
    store.transition(position_id, "SIGNALLED")
    store.transition(position_id, "INTENT_CREATED")
    store.transition(position_id, "ATTEMPTING")
    store.transition(position_id, "OPEN")
    store._conn.execute(
        "UPDATE positions SET entered_notional_usd=? WHERE position_id=?",
        (float(notional_usd), position_id),
    )
    store._conn.commit()
    return position_id, "SHADOW_EXECUTABLE"


def run_shadow_tick(
    root: Path,
    *,
    strategy_relative: str,
    store_path: Path,
    cohort: list[Mapping[str, Any]],
    max_rows: int | None = None,
) -> dict[str, Any]:
    """One unattended SHADOW tick for a COMMISSIONING_ONLY StrategyVersion."""

    strategy = load_strategy_version(root, strategy_relative)
    if strategy.get("commissioning_only") is not True:
        raise PaperPlaneError("SHADOW_REQUIRES_COMMISSIONING_ONLY")
    if strategy.get("mode_eligibility", {}).get("shadow") is not True:
        raise PaperPlaneError("SHADOW_MODE_NOT_ELIGIBLE")
    if strategy.get("mode_eligibility", {}).get("micro_live") is not False:
        raise PaperPlaneError("MICRO_LIVE_FORBIDDEN")

    store = PaperPlaneStore(store_path)
    try:
        bot = store.start_bot(strategy, mode="SHADOW")
        observed = 0
        skipped = 0
        rows = list(cohort) if max_rows is None else list(cohort)[:max_rows]
        for row in rows:
            kind = signal_kind_for(strategy, row)
            if kind == "REAL_FILL":
                raise PaperPlaneError("REAL_FILL_FORBIDDEN_IN_SHADOW_TICK")
            # Config entry may name SIMULATED_FILL; SHADOW tick maps a positive
            # signal to SHADOW_EXECUTABLE observation without claiming fill.
            if kind in {"SIMULATED_FILL", "SHADOW_EXECUTABLE"}:
                position_id = store.position_id_for(
                    bot_instance_id=bot["bot_instance_id"],
                    mint=str(row.get("mint")),
                    signal_kind="SHADOW_EXECUTABLE",
                )
                existing = store.get_position(position_id)
                if existing is not None and existing["state"] == "RECONCILED":
                    observed += 1
                    continue
                _, realized = observe_shadow(
                    store,
                    bot_instance_id=bot["bot_instance_id"],
                    mint=str(row.get("mint")),
                    notional_usd=Decimal(str(strategy["notional_policy"]["notional_usd"])),
                )
                if realized != "SHADOW_EXECUTABLE":
                    raise PaperPlaneError("SHADOW_SIGNAL_DRIFT")
                store.transition(position_id, "EXIT_REQUIRED")
                store.transition(position_id, "EXITING")
                store.transition(position_id, "CLOSED")
                store.transition(position_id, "RECONCILED")
                observed += 1
            else:
                skipped += 1
        progress_at = _now()
        return {
            "engine": "paper_plane_v1",
            "mode": "SHADOW",
            "commissioning_only": True,
            "factory_core_python_changed": False,
            "strategy_relative": strategy_relative,
            "strategy_id": strategy["strategy_id"],
            "bot_instance_id": bot["bot_instance_id"],
            "shadow_observations": observed,
            "no_signal_or_unknown": skipped,
            "progress_at": progress_at,
            "bot_instances": store.bots(),
            "positions": store.positions(),
            "open_positions": sum(
                1 for item in store.positions() if item["state"] not in {"RECONCILED", "CLOSED"}
            ),
        }
    finally:
        store.close()
