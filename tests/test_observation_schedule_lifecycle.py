from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.observation_schedule import load_observation_schedule
from solana_alpha_lab.factory.observation_schedule_lifecycle import (
    ObservationLifecycleError,
    activate_schedule,
    authorize_schedule,
    pause_schedule,
    register_schedule,
    resume_schedule,
    status_schedule,
)
from solana_alpha_lab.factory.observation_schedule_store import ObservationScheduleStore
from scripts.observation_schedule import main as cli_main


GIT = "c" * 40
NOW = datetime(2026, 9, 1, 0, 10, tzinfo=UTC)
PHRASE = "OK OBSERVATION_SCHEDULE_FIXTURE_AUTHORIZE"


class ObservationScheduleLifecycleTests(unittest.TestCase):
    def test_register_authorize_activate_pause_status_are_durable(self) -> None:
        document = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/x300_y900.yaml"
        )
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            store = ObservationScheduleStore(Path(tmp) / "ops.sqlite")
            registered = register_schedule(
                root=ROOT,
                data_root=data_root,
                store=store,
                document=document,
                now=NOW,
                producer_git_sha=GIT,
            )
            self.assertEqual(registered["terminal"], "REGISTERED")
            digest = registered["schedule_sha256"]
            again = register_schedule(
                root=ROOT,
                data_root=data_root,
                store=store,
                document=document,
                now=NOW,
                producer_git_sha=GIT,
            )
            self.assertEqual(again["terminal"], "REGISTER_REPLAY")
            auth = authorize_schedule(
                root=ROOT,
                data_root=data_root,
                store=store,
                schedule_sha256=digest,
                phrase=PHRASE,
                now=NOW,
                producer_git_sha=GIT,
            )
            self.assertEqual(auth["terminal"], "AUTHORIZED")
            activated = activate_schedule(
                data_root=data_root,
                store=store,
                schedule_sha256=digest,
                activation_id="ACT-OBS-LIFE-001",
                now=NOW,
                producer_git_sha=GIT,
            )
            self.assertEqual(activated["terminal"], "ACTIVATED")
            with self.assertRaisesRegex(ObservationLifecycleError, "ACTIVATION_ALREADY_LIVE"):
                activate_schedule(
                    data_root=data_root,
                    store=store,
                    schedule_sha256=digest,
                    activation_id="ACT-OBS-LIFE-LIVE-2",
                    now=NOW,
                    producer_git_sha=GIT,
                )
            paused = pause_schedule(
                data_root=data_root,
                store=store,
                schedule_sha256=digest,
                activation_id="ACT-OBS-LIFE-001",
                now=NOW,
                producer_git_sha=GIT,
            )
            self.assertEqual(paused["terminal"], "PAUSED")
            still = activate_schedule(
                data_root=data_root,
                store=store,
                schedule_sha256=digest,
                activation_id="ACT-OBS-LIFE-001",
                now=NOW,
                producer_git_sha=GIT,
            )
            self.assertEqual(still["terminal"], "ACTIVATE_STILL_PAUSED")
            resumed = resume_schedule(
                data_root=data_root,
                store=store,
                schedule_sha256=digest,
                activation_id="ACT-OBS-LIFE-001",
                now=NOW,
                producer_git_sha=GIT,
            )
            self.assertEqual(resumed["terminal"], "RESUMED")
            replay = resume_schedule(
                data_root=data_root,
                store=store,
                schedule_sha256=digest,
                activation_id="ACT-OBS-LIFE-001",
                now=NOW,
                producer_git_sha=GIT,
            )
            self.assertEqual(replay["terminal"], "RESUME_REPLAY")
            status = status_schedule(
                store,
                schedule_sha256=digest,
                activation_id="ACT-OBS-LIFE-001",
            )
            self.assertEqual(status["terminal"], "STATUS")
            self.assertEqual(status["activations"][0]["state"], "ACTIVE")
            store.close()

    def test_activate_without_authority_fails_before_network(self) -> None:
        document = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/x300_y900.yaml"
        )
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            store = ObservationScheduleStore(Path(tmp) / "ops.sqlite")
            registered = register_schedule(
                root=ROOT,
                data_root=data_root,
                store=store,
                document=document,
                now=NOW,
                producer_git_sha=GIT,
            )
            with self.assertRaisesRegex(ObservationLifecycleError, "AUTHORITY_MISSING"):
                activate_schedule(
                    data_root=data_root,
                    store=store,
                    schedule_sha256=registered["schedule_sha256"],
                    activation_id="ACT-OBS-LIFE-002",
                    now=NOW,
                    producer_git_sha=GIT,
                )
            store.close()

    def test_cli_stubs_are_gone(self) -> None:
        from io import StringIO
        from contextlib import redirect_stdout

        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            buf = StringIO()
            with redirect_stdout(buf):
                code = cli_main(
                    [
                        "doctor",
                        "--runtime-config",
                        "tests/fixtures/observation_schedule/runtime_commissioning.yaml",
                        "--data-root",
                        str(data_root.resolve()),
                    ]
                )
        payload = json.loads(buf.getvalue())
        self.assertEqual(code, 2)
        self.assertEqual(payload["terminal"], "DOCTOR_NO_LIVE_ACTIVATION")
        self.assertNotIn("_RECORDED", payload["terminal"])


if __name__ == "__main__":
    unittest.main()
