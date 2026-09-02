from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import timedelta
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
from solana_alpha_lab.factory.observation_schedule import (
    canonical_sha256,
    load_observation_schedule,
    parse_utc,
    render_utc,
)
from solana_alpha_lab.factory.observation_schedule_runtime import (
    UNIT_RELATIVE,
    parse_unit_exec_start,
)
from solana_alpha_lab.factory.observation_schedule_store import ObservationScheduleStore
from solana_alpha_lab.factory.observation_schedule_lifecycle import (
    _authority_policy,
    expected_authority_phrase,
)
from scripts.observation_schedule import main as cli_main


RUNTIME = "tests/fixtures/observation_schedule/runtime_commissioning.yaml"
COMMON = "tests/fixtures/observation_schedule/common_panel.yaml"
NARROW = "tests/fixtures/observation_schedule/x300_y900.yaml"
SUCCESSOR = "tests/fixtures/observation_schedule/successor_y259200.yaml"
TOKEN = "fixture-token-not-in-url"
ACT = "ACT-OBS-COMM-001"
ACT2 = "ACT-OBS-COMM-002"


def _authority_phrase(document: dict) -> str:
    horizon = max(
        int(point["due_offset_seconds"]) + int(point["allowed_lateness_seconds"])
        for point in [document["x_point"], *document["y_points"]]
    )
    expires_at = render_utc(
        parse_utc(document["activation"]["stops_admitting_at"])
        + timedelta(seconds=horizon)
    )
    policy = _authority_policy(
        root=ROOT,
        document=document,
        schedule_key=document["schedule_key"],
        expires_at=expires_at,
    )
    return expected_authority_phrase(
        schedule_sha256=document["schedule_sha256"],
        schedule_key=document["schedule_key"],
        activation_starts_at=document["activation"]["starts_at"],
        activation_stops_admitting_at=document["activation"]["stops_admitting_at"],
        provider_route_ids=policy["provider_route_ids"],
        expires_at=expires_at,
        policy_digest=canonical_sha256(policy),
    )


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
                [
                    "authorize",
                    "--schedule-sha256",
                    digest,
                    "--phrase",
                    _authority_phrase(load_observation_schedule(ROOT, COMMON)),
                    *base,
                ]
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

            code, doctor = _cli(["doctor", *base])
            self.assertEqual(code, 0, doctor)
            self.assertEqual(doctor["terminal"], "DOCTOR_OK")

            code, paused = _cli(
                ["pause", "--schedule-sha256", digest, "--activation-id", ACT, *base]
            )
            self.assertEqual(code, 0, paused)
            self.assertEqual(paused["terminal"], "PAUSED")
            code, paused_doctor = _cli(["doctor", *base])
            self.assertEqual(code, 2, paused_doctor)
            self.assertEqual(paused_doctor["terminal"], "DOCTOR_PAUSED")
            self.assertEqual(paused_doctor["next_action"], "RESUME")
            code, paused_tick = _cli(
                ["tick", "--once", *base, "--schedule-sha256", digest, "--activation-id", ACT],
                env={"OBSERVATION_SCHEDULE_CLOCK_UTC": "2026-09-01T00:10:00Z"},
            )
            self.assertEqual(code, 2, paused_tick)
            self.assertEqual(paused_tick["terminal"], "PAUSED_OPERATOR")
            self.assertEqual(paused_tick["next_action"], "RESUME")
            code, resumed = _cli(
                ["resume", "--schedule-sha256", digest, "--activation-id", ACT, *base]
            )
            self.assertEqual(code, 0, resumed)
            self.assertEqual(resumed["terminal"], "RESUMED")
            code, doctor = _cli(["doctor", *base])
            self.assertEqual(code, 0, doctor)
            self.assertEqual(doctor["terminal"], "DOCTOR_OK")

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
                env={"OBSERVATION_SCHEDULE_CLOCK_UTC": "2026-09-01T00:10:03Z"},
            )
            self.assertEqual(code, 0, ticked)
            self.assertEqual(ticked["terminal"], "TICK_COMPLETE")
            self.assertNotIn(TOKEN, json.dumps(ticked))

            store = ObservationScheduleStore(Path(data_root) / "observation_schedule_state.sqlite")
            self.addCleanup(store.close)
            candidates = {
                row["entity_id"]: row["state"]
                for row in store.list_candidates(schedule_sha256=digest, activation_id=ACT)
            }
            self.assertEqual(
                candidates.get("MintCCCC111111111111111111111111111111111"),
                "NOT_SELECTED_PREDICATE",
            )

            code, reused = _cli(
                ["tick", "--once", *base, "--schedule-sha256", digest, "--activation-id", ACT],
                env={"OBSERVATION_SCHEDULE_CLOCK_UTC": "2026-09-01T00:10:00Z"},
            )
            self.assertEqual(code, 0, reused)
            self.assertTrue(reused.get("source_poll_reused"))

            code, y900 = _cli(
                ["tick", "--once", *base, "--schedule-sha256", digest, "--activation-id", ACT],
                env={"OBSERVATION_SCHEDULE_CLOCK_UTC": "2026-09-01T00:16:00Z"},
            )
            self.assertEqual(code, 0, y900)
            self.assertEqual(y900["terminal"], "TICK_COMPLETE")

            code, second = _cli(["register", "--schedule", NARROW, *base])
            self.assertEqual(code, 0, second)
            digest2 = second["schedule_sha256"]
            _cli(
                [
                    "authorize",
                    "--schedule-sha256",
                    digest2,
                    "--phrase",
                    _authority_phrase(load_observation_schedule(ROOT, NARROW)),
                    *base,
                ]
            )
            code, rolled = _cli(
                [
                    "rollover",
                    "--predecessor-schedule-sha256",
                    digest,
                    "--predecessor-activation-id",
                    ACT,
                    "--successor-schedule-sha256",
                    digest2,
                    "--successor-activation-id",
                    ACT2,
                    "--cutover-at",
                    "2026-09-01T12:00:00Z",
                    *base,
                ]
            )
            self.assertEqual(code, 0, rolled)
            self.assertEqual(rolled["terminal"], "ROLLOVER_COMMITTED")
            calls_before = int(
                store.load_lifetime(schedule_sha256=digest2, activation_id=ACT2)["provider_calls"]
            )
            code, shared = _cli(
                ["tick", "--once", *base, "--schedule-sha256", digest2, "--activation-id", ACT2],
                env={"OBSERVATION_SCHEDULE_CLOCK_UTC": "2026-09-01T12:00:00Z"},
            )
            self.assertIn(shared["terminal"], {"PACE_WAIT", "TICK_COMPLETE"}, shared)
            self.assertGreaterEqual(int(shared["provider_calls"]), max(1, calls_before))
            self.assertEqual(
                store.get_activation(digest, ACT)["state"],
                "DRAINING",
            )
            self.assertEqual(
                store.get_activation(digest2, ACT2)["state"],
                "ACTIVE",
            )

            code, h24 = _cli(
                ["tick", "--once", *base, "--schedule-sha256", digest, "--activation-id", ACT],
                env={"OBSERVATION_SCHEDULE_CLOCK_UTC": "2026-09-02T00:00:01Z"},
            )
            self.assertEqual(code, 0, h24)
            self.assertEqual(h24["terminal"], "TICK_COMPLETE")

            code, snapped = _cli(
                [
                    "snapshot",
                    "--schedule-sha256",
                    digest,
                    "--activation-id",
                    ACT,
                    *base,
                ],
                env={"OBSERVATION_SCHEDULE_CLOCK_UTC": "2026-09-02T00:05:00Z"},
            )
            self.assertEqual(code, 0, snapped)
            self.assertEqual(snapped["terminal"], "SNAPSHOT")
            self.assertTrue(snapped.get("first_y_proven"))

            dues = store.due_in_states(
                (
                    "OBSERVED",
                    "MISSING_TYPED",
                    "DISAPPEARED",
                    "CENSORED",
                    "CENSORED_LATE",
                )
            )
            states = {row["state"] for row in dues}
            self.assertTrue(
                {"OBSERVED", "MISSING_TYPED", "CENSORED", "CENSORED_LATE"} & states
            )
            points = {row["point_id"] for row in store.due_in_states(
                (
                    "PENDING",
                    "DUE",
                    "CLAIMED",
                    "OBSERVED",
                    "MISSING_TYPED",
                    "DISAPPEARED",
                    "CENSORED",
                    "CENSORED_LATE",
                    "DEPENDENCY_MISSING",
                )
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
            self.assertEqual(int(later["provider_calls"]), 0)
            self.assertNotEqual(int(day["provider_calls"]), 0)
            store.close()

            covering = load_observation_schedule(ROOT, COMMON)
            successor = load_observation_schedule(ROOT, SUCCESSOR)
            requested = load_observation_schedule(ROOT, NARROW)
            bound = compile_observation_request(
                {
                    "observation_request": {
                        **requested,
                        "collection_mode": "REUSE_OR_SCHEDULE",
                        "requested_evidence_role": "PROSPECTIVE_OOS",
                    },
                    "availability_cutoff": "2026-09-02T01:00:00Z",
                    "as_of": "2026-08-01T00:00:00Z",
                },
                root=ROOT,
                data_root=Path(data_root),
            )
            self.assertEqual(bound.terminal, "PANEL_REUSE_READY")
            empty = Path(tmp) / "empty-rdp"
            empty.mkdir()
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
            self.assertNotEqual(unproven.terminal, "PANEL_REUSE_READY")
            self.assertEqual(unproven.terminal, "SCHEDULE_ACTIVATION_REQUIRED")

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
        self.assertIn("--runtime-config configs/observation_schedule_runtime_v1.yaml", unit)
        self.assertNotIn("/opt/solana-alpha-lab/configs/", unit)
        self.assertIn("EnvironmentFile=-/etc/solana-alpha-lab/secrets.env", unit)
        argv = parse_unit_exec_start(unit)
        self.assertIn("scripts/observation_schedule.py", argv)
        self.assertIn("tick", argv)
        self.assertIn("--once", argv)
        self.assertIn("configs/observation_schedule_runtime_v1.yaml", argv)
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

    def test_unpinned_tick_processes_two_active_schedules_in_sorted_order(self) -> None:
        from solana_alpha_lab.factory.observation_schedule import schedule_sha256
        from solana_alpha_lab.factory.observation_schedule_lifecycle import (
            activate_schedule,
            authorize_schedule,
            register_schedule,
        )
        from solana_alpha_lab.factory.observation_schedule_store import (
            ObservationScheduleStore,
        )

        with tempfile.TemporaryDirectory() as tmp:
            data_root_path = Path(tmp) / "rdp"
            data_root_path.mkdir()
            data_root = str(data_root_path.resolve())
            store = ObservationScheduleStore(
                data_root_path / "observation_schedule_state.sqlite"
            )
            self.addCleanup(store.close)
            first_doc = load_observation_schedule(ROOT, COMMON)
            second_doc = dict(load_observation_schedule(ROOT, NARROW))
            second_doc["schedule_key"] = "OBS-INDEPENDENT-COHORT-TICK-ORDER-001"
            second_doc["sampling"] = dict(second_doc["sampling"])
            second_doc["sampling"]["seed"] = "INDEPENDENT-COHORT-TICK-ORDER-V1"
            second_doc["schedule_sha256"] = schedule_sha256(second_doc)
            first = register_schedule(
                root=ROOT,
                data_root=data_root_path,
                store=store,
                document=first_doc,
                now=parse_utc("2026-09-01T00:10:00Z"),
                producer_git_sha="c" * 40,
            )
            second = register_schedule(
                root=ROOT,
                data_root=data_root_path,
                store=store,
                document=second_doc,
                now=parse_utc("2026-09-01T00:10:00Z"),
                producer_git_sha="c" * 40,
            )
            for digest, document in (
                (first["schedule_sha256"], first_doc),
                (second["schedule_sha256"], second_doc),
            ):
                authorize_schedule(
                    root=ROOT,
                    data_root=data_root_path,
                    store=store,
                    schedule_sha256=digest,
                    phrase=_authority_phrase(document),
                    now=parse_utc("2026-09-01T00:10:00Z"),
                    producer_git_sha="c" * 40,
                )
            activate_schedule(
                root=ROOT,
                data_root=data_root_path,
                store=store,
                schedule_sha256=first["schedule_sha256"],
                activation_id=ACT,
                now=parse_utc("2026-09-01T00:10:00Z"),
                producer_git_sha="c" * 40,
            )
            activate_schedule(
                root=ROOT,
                data_root=data_root_path,
                store=store,
                schedule_sha256=second["schedule_sha256"],
                activation_id=ACT2,
                now=parse_utc("2026-09-01T00:10:00Z"),
                producer_git_sha="c" * 40,
            )
            store.close()
            expected = sorted(
                [
                    (first["schedule_sha256"], ACT),
                    (second["schedule_sha256"], ACT2),
                ]
            )
            code, ticked = _cli(
                [
                    "tick",
                    "--once",
                    "--runtime-config",
                    RUNTIME,
                    "--data-root",
                    data_root,
                ],
                env={"OBSERVATION_SCHEDULE_CLOCK_UTC": "2026-09-01T00:10:00Z"},
            )
            self.assertIn(ticked["terminal"], {"TICK_COMPLETE", "TICK_PARTIAL", "PACE_WAIT"})
            activations = ticked.get("activations")
            if activations is None:
                self.fail("unpinned tick with two live schedules must enumerate both")
            observed = [
                (item.get("schedule_sha256"), item.get("activation_id"))
                for item in activations
            ]
            self.assertEqual(observed, expected)

    def test_credential_loader_is_not_called_without_live_schedule(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = str((Path(tmp) / "rdp").resolve())
            Path(data_root).mkdir()
            with patch(
                "scripts.observation_schedule.load_credential_after_activation"
            ) as loader:
                code, payload = _cli(
                    [
                        "tick",
                        "--once",
                        "--runtime-config",
                        RUNTIME,
                        "--data-root",
                        data_root,
                    ]
                )
            self.assertEqual(code, 2)
            self.assertEqual(payload["terminal"], "TICK_REFUSED_NO_LIVE_DEFAULT")
            loader.assert_not_called()

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
