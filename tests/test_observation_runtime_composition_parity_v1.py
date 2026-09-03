"""OBSERVATION_RUNTIME_COMPOSITION_PARITY_V1 boundary + golden proofs."""

from __future__ import annotations

import argparse
import ast
import json
import sys
import tempfile
import unittest
from datetime import UTC, datetime
from io import StringIO
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.observation_provider_pacing import (  # noqa: E402
    AdvancingClock,
    WallClock,
)
from solana_alpha_lab.factory.observation_schedule_composition import (  # noqa: E402
    CompositionParityError,
    TickPhysicalOverrides,
    materialize_tick_physical_dependencies,
    validate_tick_physical_overrides,
)
from solana_alpha_lab.factory.observation_schedule_runtime import (  # noqa: E402
    DEFAULT_RUNTIME_RELATIVE,
    UNIT_RELATIVE,
    FakeProviderOpener,
    load_runtime_config,
    parse_unit_exec_start,
)
from solana_alpha_lab.factory.observation_schedule_store import (  # noqa: E402
    ObservationScheduleStore,
)
from scripts.observation_runtime_composition_parity import (  # noqa: E402
    NOW,
    PASS_TERMINAL,
    authorize_and_activate,
    build_parity_schedule,
    load_parity_opener,
    run_parity,
    run_parity_once,
    semantic_sha256,
)
from scripts.observation_schedule import main as cli_main  # noqa: E402


class CompositionSeamUnitTests(unittest.TestCase):
    def test_production_default_selects_wall_clock_without_network(self) -> None:
        config = load_runtime_config(ROOT, DEFAULT_RUNTIME_RELATIVE)
        self.assertNotIn("fake_provider_fixture", config)

        def _load() -> str:
            return "test-not-a-real-credential"

        with patch(
            "solana_alpha_lab.factory.observation_schedule_composition.build_opener",
            return_value=object(),
        ) as mocked:
            binding = materialize_tick_physical_dependencies(
                root=ROOT,
                config=config,
                load_credential=_load,
                physical_overrides=None,
            )
        self.assertIsInstance(binding.pacing_clock, WallClock)
        self.assertIsNone(binding.credential_loader)
        mocked.assert_called_once()
        self.assertEqual(mocked.call_args.kwargs.get("credential"), "test-not-a-real-credential")

    def test_complete_override_accepted(self) -> None:
        opener = load_parity_opener()
        clock = AdvancingClock(NOW)
        overrides = TickPhysicalOverrides(now=NOW, opener=opener, pacing_clock=clock)
        binding = materialize_tick_physical_dependencies(
            root=ROOT,
            config=load_runtime_config(ROOT, DEFAULT_RUNTIME_RELATIVE),
            load_credential=lambda: (_ for _ in ()).throw(RuntimeError("CREDENTIAL_PATH_TOUCHED")),
            physical_overrides=overrides,
        )
        self.assertIs(binding.opener, opener)
        self.assertIs(binding.pacing_clock, clock)
        self.assertIsNone(binding.credential_loader)

    def test_partial_override_rejected(self) -> None:
        incomplete = object.__new__(TickPhysicalOverrides)
        object.__setattr__(incomplete, "now", NOW)
        object.__setattr__(incomplete, "opener", None)
        object.__setattr__(incomplete, "pacing_clock", AdvancingClock(NOW))
        with self.assertRaises(CompositionParityError) as ctx:
            validate_tick_physical_overrides(incomplete)  # type: ignore[arg-type]
        self.assertEqual(str(ctx.exception), "PHYSICAL_OVERRIDES_INCOMPLETE")

    def test_bare_callable_rejected(self) -> None:
        overrides = TickPhysicalOverrides(
            now=NOW,
            opener=object(),
            pacing_clock=lambda: datetime.now(UTC),
        )
        with self.assertRaises(CompositionParityError) as ctx:
            validate_tick_physical_overrides(overrides)
        self.assertEqual(str(ctx.exception), "CLOCK_SLEEP_REQUIRED")

    def test_clock_now_mismatch_rejected(self) -> None:
        overrides = TickPhysicalOverrides(
            now=NOW,
            opener=object(),
            pacing_clock=AdvancingClock(datetime(2026, 1, 1, tzinfo=UTC)),
        )
        with self.assertRaises(CompositionParityError) as ctx:
            validate_tick_physical_overrides(overrides)
        self.assertEqual(str(ctx.exception), "PHYSICAL_CLOCK_NOW_MISMATCH")

    def test_override_not_reachable_from_cli_config_env(self) -> None:
        parser = argparse.ArgumentParser()
        # Rebuild tick parser surface from live CLI help text.
        buf = StringIO()
        with patch("sys.stdout", buf), patch("sys.stderr", buf):
            try:
                cli_main(["tick", "--help"])
            except SystemExit:
                pass
        help_text = buf.getvalue()
        self.assertNotIn("physical_overrides", help_text)
        self.assertNotIn("fake-provider", help_text)
        self.assertNotIn("simulation_mode", help_text)
        schema = json.loads(
            (
                ROOT / "catalog/schemas/observation_schedule_runtime_v1.schema.json"
            ).read_text(encoding="utf-8")
        )
        props = schema.get("properties") or {}
        self.assertNotIn("simulation_mode", props)
        self.assertNotIn("physical_overrides", props)
        unit = (ROOT / UNIT_RELATIVE).read_text(encoding="utf-8")
        self.assertNotIn("simulation_mode", unit)
        self.assertNotIn("FAKE_PROVIDER", unit)
        prod = (ROOT / DEFAULT_RUNTIME_RELATIVE).read_text(encoding="utf-8")
        self.assertNotIn("fake_provider", prod)
        self.assertNotIn("clock_utc", prod)

    def test_systemd_identity(self) -> None:
        unit = (ROOT / UNIT_RELATIVE).read_text(encoding="utf-8")
        argv = parse_unit_exec_start(unit)
        self.assertIn("scripts/observation_schedule.py", " ".join(argv))
        self.assertIn("tick", argv)
        self.assertIn("--once", argv)
        self.assertIn("--runtime-config", argv)
        self.assertEqual(
            argv[argv.index("--runtime-config") + 1],
            DEFAULT_RUNTIME_RELATIVE,
        )

    def test_cli_tick_cannot_bypass_composition_seam(self) -> None:
        src = (ROOT / "scripts/observation_schedule.py").read_text(encoding="utf-8")
        self.assertNotIn("build_opener(", src)
        self.assertNotIn("WallClock()", src)
        self.assertIn("materialize_tick_physical_dependencies", src)
        # Behavioral lock: materialize must run on the override tick path.
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            schedule = build_parity_schedule()
            store = ObservationScheduleStore(
                data_root / "observation_schedule_state.sqlite"
            )
            authorize_and_activate(
                store=store, data_root=data_root, schedule=schedule, now=NOW
            )
            store.close()
            opener = load_parity_opener()
            clock = AdvancingClock(NOW)
            with patch(
                "scripts.observation_schedule.materialize_tick_physical_dependencies",
                side_effect=CompositionParityError("SEAM_MUST_RUN"),
            ):
                buf = StringIO()
                from contextlib import redirect_stdout

                with redirect_stdout(buf):
                    code = cli_main(
                        [
                            "tick",
                            "--once",
                            "--runtime-config",
                            DEFAULT_RUNTIME_RELATIVE,
                            "--data-root",
                            str(data_root),
                        ],
                        physical_overrides=TickPhysicalOverrides(
                            now=NOW, opener=opener, pacing_clock=clock
                        ),
                    )
                payload = json.loads(buf.getvalue())
            self.assertEqual(code, 2)
            self.assertEqual(payload.get("terminal"), "SEAM_MUST_RUN")
            self.assertEqual(opener.urls, [])

    def test_tick_once_consumes_materialize_binding_override_path(self) -> None:
        from solana_alpha_lab.factory import observation_schedule_composition as seam

        captured: dict = {}
        real = seam.materialize_tick_physical_dependencies

        def _wrap(**kwargs):  # type: ignore[no-untyped-def]
            binding = real(**kwargs)
            captured["binding"] = binding
            return binding

        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            schedule = build_parity_schedule()
            store = ObservationScheduleStore(
                data_root / "observation_schedule_state.sqlite"
            )
            authorize_and_activate(
                store=store, data_root=data_root, schedule=schedule, now=NOW
            )
            store.close()
            opener = load_parity_opener()
            clock = AdvancingClock(NOW)
            with patch(
                "scripts.observation_schedule.materialize_tick_physical_dependencies",
                side_effect=_wrap,
            ), patch(
                "scripts.observation_schedule.tick_once",
                return_value={
                    "terminal": "TICK_COMPLETE",
                    "provider_calls": 0,
                    "credential_reads": 0,
                },
            ) as mocked_tick:
                buf = StringIO()
                from contextlib import redirect_stdout

                with redirect_stdout(buf):
                    code = cli_main(
                        [
                            "tick",
                            "--once",
                            "--runtime-config",
                            DEFAULT_RUNTIME_RELATIVE,
                            "--data-root",
                            str(data_root),
                        ],
                        physical_overrides=TickPhysicalOverrides(
                            now=NOW, opener=opener, pacing_clock=clock
                        ),
                    )
            self.assertEqual(code, 0)
            self.assertIn("binding", captured)
            kwargs = mocked_tick.call_args.kwargs
            self.assertIs(kwargs["opener"], captured["binding"].opener)
            self.assertIs(kwargs["clock"], captured["binding"].pacing_clock)
            self.assertIs(kwargs["opener"], opener)
            self.assertIs(kwargs["clock"], clock)

    def test_tick_once_consumes_materialize_binding_production_path(self) -> None:
        from solana_alpha_lab.factory import observation_schedule_composition as seam

        captured: dict = {}
        real = seam.materialize_tick_physical_dependencies

        def _wrap(**kwargs):  # type: ignore[no-untyped-def]
            binding = real(**kwargs)
            captured["binding"] = binding
            return binding

        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            schedule = build_parity_schedule()
            store = ObservationScheduleStore(
                data_root / "observation_schedule_state.sqlite"
            )
            authorize_and_activate(
                store=store, data_root=data_root, schedule=schedule, now=NOW
            )
            store.close()
            with patch(
                "scripts.observation_schedule.materialize_tick_physical_dependencies",
                side_effect=_wrap,
            ), patch(
                "scripts.observation_schedule.tick_once",
                return_value={
                    "terminal": "TICK_COMPLETE",
                    "provider_calls": 0,
                    "credential_reads": 0,
                },
            ) as mocked_tick, patch.dict(
                "os.environ",
                {
                    "JUPITER_FREE_API_KEY": "x" * 16,
                    "OBSERVATION_SCHEDULE_CLOCK_UTC": NOW.strftime(
                        "%Y-%m-%dT%H:%M:%SZ"
                    ),
                },
            ):
                buf = StringIO()
                from contextlib import redirect_stdout

                with redirect_stdout(buf):
                    code = cli_main(
                        [
                            "tick",
                            "--once",
                            "--runtime-config",
                            DEFAULT_RUNTIME_RELATIVE,
                            "--data-root",
                            str(data_root),
                        ],
                        physical_overrides=None,
                    )
            self.assertEqual(code, 0)
            self.assertIn("binding", captured)
            kwargs = mocked_tick.call_args.kwargs
            self.assertIs(kwargs["opener"], captured["binding"].opener)
            self.assertIs(kwargs["clock"], captured["binding"].pacing_clock)
            self.assertIsInstance(kwargs["clock"], WallClock)


class CompositionParityGoldenTests(unittest.TestCase):
    def test_campaign_predicate_is_launchpad(self) -> None:
        schedule = build_parity_schedule()
        predicate = schedule["population"]["source_predicates"][0]
        self.assertEqual(predicate["field_id"], "FIELD-LAUNCHPAD-001")
        self.assertEqual(predicate["value_text"], "pump.fun")

    def test_unauthorized_activation_has_no_provider_activity(self) -> None:
        schedule = build_parity_schedule()
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            store = ObservationScheduleStore(data_root / "observation_schedule_state.sqlite")
            store.persist_registered_schedule(
                schedule_sha256=schedule["schedule_sha256"],
                schedule_key=schedule["schedule_key"],
                document=schedule,
                clock=NOW,
            )
            store.close()
            opener = load_parity_opener()
            clock = AdvancingClock(NOW)
            buf = StringIO()
            from contextlib import redirect_stdout

            with redirect_stdout(buf):
                code = cli_main(
                    [
                        "tick",
                        "--once",
                        "--runtime-config",
                        DEFAULT_RUNTIME_RELATIVE,
                        "--data-root",
                        str(data_root),
                    ],
                    physical_overrides=TickPhysicalOverrides(
                        now=NOW, opener=opener, pacing_clock=clock
                    ),
                )
            payload = json.loads(buf.getvalue())
            self.assertNotEqual(code, 0)
            self.assertEqual(opener.urls, [])
            self.assertIn("terminal", payload)

    def test_golden_vertical_and_restart(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            record = run_parity_once(root_tmp=Path(tmp))
        self.assertIn("RECENT", record["provider_endpoint_sequence"])
        self.assertIn("SEARCH", record["provider_endpoint_sequence"])
        self.assertGreaterEqual(record["provider_call_count"], 2)
        self.assertTrue(record["pump_candidate_progressed"])
        self.assertTrue(record["matured_due_progressed"])
        self.assertTrue(record["control_predicate_rejected"])
        self.assertTrue(record["legacy_nested_rejected"])
        self.assertEqual(record["credential_reads"], 0)
        self.assertGreaterEqual(
            float(record["minimum_simulated_spacing_seconds"]), 3.0
        )
        self.assertNotEqual(record["terminal"], "PACE_WAIT")
        # Pump reached post-predicate path (X_ELIGIBLE or stronger).
        self.assertIn("X_ELIGIBLE", record["candidate_state_counts"])

    def test_deterministic_digest_two_runs(self) -> None:
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            left = run_parity_once(root_tmp=Path(a))
            right = run_parity_once(root_tmp=Path(b))
        self.assertEqual(semantic_sha256(left), semantic_sha256(right))
        self.assertEqual(left["semantic_result_sha256"], right["semantic_result_sha256"])

    def test_credential_tripwire(self) -> None:
        with patch(
            "scripts.observation_schedule.load_credential_after_activation",
            side_effect=RuntimeError("CREDENTIAL_PATH_TOUCHED"),
        ):
            with tempfile.TemporaryDirectory() as tmp:
                record = run_parity_once(root_tmp=Path(tmp))
        self.assertEqual(record["credential_reads"], 0)

    def test_network_tripwire(self) -> None:
        with patch(
            "solana_alpha_lab.factory.observation_schedule_runtime.JupiterReadonlyOpener",
            side_effect=RuntimeError("NETWORK_PATH_TOUCHED"),
        ):
            with tempfile.TemporaryDirectory() as tmp:
                record = run_parity_once(root_tmp=Path(tmp))
        self.assertEqual(record["network_calls"], 0)
        self.assertIn("SEARCH", record["provider_endpoint_sequence"])

    def test_smoke_terminal(self) -> None:
        payload = run_parity()
        self.assertEqual(payload["terminal"], PASS_TERMINAL)
        self.assertEqual(payload["credential_reads"], 0)
        self.assertEqual(payload["network_calls"], 0)
        self.assertLess(payload["wall_time_seconds"], 30)


if __name__ == "__main__":
    unittest.main()
