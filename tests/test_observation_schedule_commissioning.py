from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.observation_panel_coverage import CoverageIndex
from solana_alpha_lab.factory.observation_primitive_registry import (
    ObservationPrimitiveRegistry,
)
from solana_alpha_lab.factory.observation_schedule_compiler import compile_observation_request
from solana_alpha_lab.factory.observation_schedule_runtime import (
    UNIT_RELATIVE,
    parse_unit_exec_start,
)
from solana_alpha_lab.factory.observation_schedule_store import ObservationScheduleStore
from scripts.observation_schedule import main as cli_main


RUNTIME = "tests/fixtures/observation_schedule/runtime_commissioning.yaml"
COMMON = "tests/fixtures/observation_schedule/common_panel.yaml"
NARROW = "tests/fixtures/observation_schedule/x300_y900.yaml"
SUCCESSOR = "tests/fixtures/observation_schedule/successor_y259200.yaml"
PHRASE = "OK OBSERVATION_SCHEDULE_FIXTURE_AUTHORIZE"
TOKEN = "fixture-token-not-in-url"
ACT = "ACT-OBS-COMM-001"
ACT2 = "ACT-OBS-COMM-002"


def _cli(args: list[str], env: dict[str, str] | None = None) -> tuple[int, dict]:
    previous = {key: os.environ.get(key) for key in (env or {})}
    previous["JUPITER_FREE_API_KEY"] = os.environ.get("JUPITER_FREE_API_KEY")
    buf = StringIO()
    try:
        os.environ["JUPITER_FREE_API_KEY"] = TOKEN
        if env:
            os.environ.update(env)
        with redirect_stdout(buf):
            code = cli_main(args)
        payload = json.loads(buf.getvalue()) if buf.getvalue().strip() else {}
        return code, payload
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


class ObservationScheduleCommissioningTests(unittest.TestCase):
    def test_public_cli_zero_network_commissioning_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = str((Path(tmp) / "rdp").resolve())
            Path(data_root).mkdir()
            base = [
                "--runtime-config",
                RUNTIME,
                "--data-root",
                data_root,
            ]
            code, registered = _cli(["register", "--schedule", COMMON, *base])
            self.assertEqual(code, 0, registered)
            digest = registered["schedule_sha256"]
            self.assertEqual(registered["terminal"], "REGISTERED")
            code, replay = _cli(["register", "--schedule", COMMON, *base])
            self.assertEqual(replay["terminal"], "REGISTER_REPLAY")
            code, auth = _cli(
                ["authorize", "--schedule-sha256", digest, "--phrase", PHRASE, *base]
            )
            self.assertEqual(code, 0, auth)
            self.assertEqual(auth["terminal"], "AUTHORIZED")
            code, activated = _cli(
                [
                    "activate",
                    "--schedule-sha256",
                    digest,
                    "--activation-id",
                    ACT,
                    *base,
                ]
            )
            self.assertEqual(code, 0, activated)
            self.assertEqual(activated["terminal"], "ACTIVATED")

            missing_env = dict(os.environ)
            missing_env.pop("JUPITER_FREE_API_KEY", None)
            code, refused = _cli(
                [
                    "tick",
                    "--once",
                    *base,
                    "--schedule-sha256",
                    "a" * 64,
                    "--activation-id",
                    "ACT-OBS-LEGACY-001",
                ],
                env={"OBSERVATION_SCHEDULE_CLOCK_UTC": "2026-09-01T00:10:00Z"},
            )
            self.assertEqual(code, 2)
            self.assertEqual(refused["terminal"], "TICK_REFUSED_NO_LIVE_DEFAULT")

            code, faulted = _cli(
                ["tick", "--once", *base, "--schedule-sha256", digest, "--activation-id", ACT],
                env={
                    "OBSERVATION_SCHEDULE_CLOCK_UTC": "2026-09-01T00:10:00Z",
                    "OBSERVATION_SCHEDULE_PUBLISH_FAULT": "AFTER_ARTIFACTS",
                },
            )
            self.assertEqual(code, 2, faulted)
            self.assertEqual(faulted["terminal"], "AFTER_ARTIFACTS")

            code, ticked = _cli(
                ["tick", "--once", *base, "--schedule-sha256", digest, "--activation-id", ACT],
                env={"OBSERVATION_SCHEDULE_CLOCK_UTC": "2026-09-01T00:10:00Z"},
            )
            self.assertEqual(code, 0, ticked)
            self.assertEqual(ticked["terminal"], "TICK_COMPLETE")
            self.assertNotIn(TOKEN, json.dumps(ticked))

            code, y900 = _cli(
                ["tick", "--once", *base, "--schedule-sha256", digest, "--activation-id", ACT],
                env={"OBSERVATION_SCHEDULE_CLOCK_UTC": "2026-09-01T00:16:00Z"},
            )
            self.assertIn(y900["terminal"], {"TICK_COMPLETE", "PACE_WAIT"})

            code, h24 = _cli(
                ["tick", "--once", *base, "--schedule-sha256", digest, "--activation-id", ACT],
                env={"OBSERVATION_SCHEDULE_CLOCK_UTC": "2026-09-02T00:05:00Z"},
            )
            self.assertEqual(code, 0, h24)
            self.assertEqual(h24["terminal"], "TICK_COMPLETE")

            store = ObservationScheduleStore(Path(data_root) / "observation_schedule_state.sqlite")
            dues = store.due_in_states(("OBSERVED", "MISSING_TYPED", "DISAPPEARED"))
            states = {row["state"] for row in dues}
            self.assertTrue({"OBSERVED", "MISSING_TYPED"} & states)
            points = {row["point_id"] for row in store.due_in_states(
                ("PENDING", "DUE", "CLAIMED", "OBSERVED", "MISSING_TYPED", "DISAPPEARED", "CENSORED")
            )}
            self.assertIn("X300", points)
            self.assertIn("Y900", points)
            self.assertIn("Y86400", points)
            day = store.load_accounting(
                schedule_sha256=digest, activation_id=ACT, utc_day="2026-09-01"
            )
            self.assertGreater(int(day["provider_calls"]), 0)
            later = store.load_accounting(
                schedule_sha256=digest, activation_id=ACT, utc_day="2026-09-02"
            )
            self.assertGreater(int(later["provider_calls"]), 0)
            self.assertNotEqual(int(day["provider_calls"]), 0)

            code, second = _cli(["register", "--schedule", NARROW, *base])
            self.assertEqual(code, 0, second)
            digest2 = second["schedule_sha256"]
            _cli(["authorize", "--schedule-sha256", digest2, "--phrase", PHRASE, *base])
            _cli(
                [
                    "activate",
                    "--schedule-sha256",
                    digest2,
                    "--activation-id",
                    ACT2,
                    *base,
                ]
            )
            calls_before = int(
                store.load_lifetime(schedule_sha256=digest2, activation_id=ACT2)["provider_calls"]
            )
            code, shared = _cli(
                ["tick", "--once", *base, "--schedule-sha256", digest2, "--activation-id", ACT2],
                env={"OBSERVATION_SCHEDULE_CLOCK_UTC": "2026-09-01T00:10:00Z"},
            )
            self.assertEqual(code, 0, shared)
            self.assertEqual(shared["terminal"], "TICK_COMPLETE")
            self.assertGreaterEqual(shared["provider_calls"], calls_before)

            store.save_lifetime(
                schedule_sha256=digest,
                activation_id=ACT,
                provider_calls=3200,
                canonical_bytes=1,
            )
            code, exhausted = _cli(
                ["tick", "--once", *base, "--schedule-sha256", digest, "--activation-id", ACT],
                env={"OBSERVATION_SCHEDULE_CLOCK_UTC": "2026-09-02T00:10:00Z"},
            )
            self.assertEqual(exhausted["terminal"], "BLOCKED_BUDGET")
            self.assertEqual(int(exhausted["provider_calls"]), 0)
            store.close()

            from solana_alpha_lab.factory.observation_schedule import load_observation_schedule

            covering = load_observation_schedule(ROOT, COMMON)
            successor = load_observation_schedule(ROOT, SUCCESSOR)
            index = CoverageIndex()
            index.add_snapshot(
                snapshot_sha256="b" * 64,
                schedule=covering,
                availability_cutoff=__import__("datetime").datetime(
                    2026, 9, 2, 1, 0, tzinfo=__import__("datetime").UTC
                ),
                first_y_available_at=__import__("datetime").datetime(
                    2026, 8, 1, tzinfo=__import__("datetime").UTC
                ),
            )
            bound = compile_observation_request(
                {
                    "observation_request": {
                        **successor,
                        "collection_mode": "REUSE_OR_SCHEDULE",
                        "requested_evidence_role": "PROSPECTIVE_OOS",
                    },
                    "availability_cutoff": "2026-09-02T01:00:00Z",
                    "as_of": "2026-08-01T00:00:00Z",
                },
                root=ROOT,
                coverage=index,
                data_root=Path(data_root),
            )
            self.assertEqual(bound.terminal, "PANEL_REUSE_READY")
            empty = Path(tmp) / "empty-rdp"
            empty.mkdir()
            unproven = compile_observation_request(
                {
                    "observation_request": {
                        **successor,
                        "collection_mode": "REUSE_OR_SCHEDULE",
                        "requested_evidence_role": "PROSPECTIVE_OOS",
                    },
                    "availability_cutoff": "2026-09-02T01:00:00Z",
                    "as_of": "2026-08-01T00:00:00Z",
                },
                root=ROOT,
                coverage=index,
                data_root=empty,
            )
            self.assertEqual(unproven.terminal, "PANEL_REUSE_READY")
            self.assertEqual(unproven.evidence_role, "EXPLORATORY_REUSE")

            leaked = dict(successor)
            leaked["population"] = dict(successor["population"])
            leaked["population"]["source_predicates"] = [
                {
                    "field_id": "FIELD-QUOTE-SELL-OUT-AMOUNT-001",
                    "operator": "GT",
                    "value_decimal": "1",
                }
            ]
            denied = compile_observation_request(
                {
                    "observation_request": {
                        **leaked,
                        "collection_mode": "SCHEDULE_ONLY",
                        "requested_evidence_role": "PROSPECTIVE_OOS",
                    },
                    "availability_cutoff": leaked["activation"]["starts_at"],
                    "as_of": leaked["activation"]["starts_at"],
                },
                root=ROOT,
            )
            self.assertEqual(denied.terminal, "DENY_OUTCOME_LEAKAGE")

    def test_exact_execstart_dispatches_tick(self) -> None:
        unit = (ROOT / UNIT_RELATIVE).read_text(encoding="utf-8")
        self.assertIn("tick --once", unit)
        self.assertIn("--runtime-config", unit)
        os.environ["OBSERVATION_SCHEDULE_RUNTIME_CONFIG"] = RUNTIME
        try:
            argv = parse_unit_exec_start(unit)
            self.assertIn("scripts/observation_schedule.py", argv)
            self.assertIn("tick", argv)
            self.assertIn("--once", argv)
            script_at = argv.index("scripts/observation_schedule.py")
            with tempfile.TemporaryDirectory() as tmp:
                data_root = str((Path(tmp) / "rdp").resolve())
                Path(data_root).mkdir()
                cli_args = argv[script_at + 1 :] + ["--data-root", data_root]
                completed = subprocess.run(
                    [sys.executable, "-B", str(ROOT / "scripts/observation_schedule.py"), *cli_args],
                    cwd=str(ROOT),
                    capture_output=True,
                    text=True,
                    check=False,
                )
                payload = json.loads(completed.stdout)
                self.assertEqual(completed.returncode, 2)
                self.assertEqual(payload["terminal"], "TICK_REFUSED_NO_LIVE_DEFAULT")
        finally:
            os.environ.pop("OBSERVATION_SCHEDULE_RUNTIME_CONFIG", None)

    def test_implementation_hash_drift_fails_before_network(self) -> None:
        with patch.object(
            ObservationPrimitiveRegistry,
            "implementation_bytes_sha256",
            return_value="0" * 64,
        ):
            code, payload = _cli(
                [
                    "compile",
                    "--schedule",
                    NARROW,
                    "--runtime-config",
                    RUNTIME,
                ]
            )
            self.assertEqual(code, 2)
            self.assertEqual(payload["terminal"], "CHANGE_LANE_PRIMITIVE_GAP")


if __name__ == "__main__":
    unittest.main()
