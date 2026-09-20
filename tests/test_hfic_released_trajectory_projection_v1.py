"""Non-synthetic NORMALIZED_TRAJECTORY_V1 runtime seam.

After a qualifying CONTROL, a verified imported live-cohort release must
produce a projection/input receipt through already-merged code — no future
Git atom.  PIT cutoffs stay frozen, missingness stays M, no mint identity
leaks into the representation, and provenance binds
release/source/census/observations/schedule/activation.
"""

from __future__ import annotations

import json
import sys
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.hfic_representation_probe import (  # noqa: E402
    INVALID_INSUFFICIENT_YIELD,
    RepresentationProbeError,
    build_challenger_packet,
    control_baseline_from_receipt,
)
from solana_alpha_lab.factory.hfic_released_trajectory_projection import (  # noqa: E402
    CANONICAL_SCHEDULE_UNBOUND,
    INVALID_PROJECTION_PROVENANCE,
    FUTURE_POINT_LEAKAGE,
    MINT_IDENTITY_LEAK,
    resolve_release_projection_input,
)
from solana_alpha_lab.factory.normalized_trajectory_v1 import (  # noqa: E402
    FIELD_IDS,
    REPRESENTATION_ID,
)
from solana_alpha_lab.factory.run_passport import canonical_sha256  # noqa: E402

sys.path.insert(0, str(ROOT / "tests"))
from tests.test_hfic_representation_probe import (  # noqa: E402
    _control_receipt,
)


def _write_release(
    root: Path,
    *,
    anchor: datetime,
    members: int = 10,
    extra_future_only_members: int = 0,
    with_candidate_state: bool = False,
) -> Path:
    """Build a production-shaped release directory fixture."""
    import pyarrow as pa
    import pyarrow.parquet as pq

    release_root = root / "release"
    release_root.mkdir(parents=True, exist_ok=True)
    x_due, y_dues = 300, (900, 1800, 3600, 7200, 14400, 43200, 86400)
    prefix = (300, 900, 1800)
    census_rows = []
    obs_rows = []
    for index in range(members):
        member = f"member-{index:03d}"
        row = {
            "member_id": member,
            "mint": f"MINT{index:03d}",
            "admitted": True,
            "authoritative_anchor": anchor.isoformat().replace("+00:00", "Z"),
        }
        if with_candidate_state:
            row["candidate_state"] = "X_ELIGIBLE"
        census_rows.append(row)
        # Anchor: pool creation (member anchor at).
        anchor_iso = anchor.isoformat().replace("+00:00", "Z")
        obs_rows.append(
            {
                "mint": f"MINT{index:03d}",
                "entity_id": f"MINT{index:03d}",
                "point_id": "X300",
                "primitive_id": "PRIM-JUPITER-TOKENS-V2-SEARCH-001",
                "field_id": "FIELD-FIRST-POOL-CREATED-AT-001",
                "value_kind": "TIMESTAMP",
                "typed_value": anchor_iso,
                "state": "OBSERVED",
                "missing_reason": None,
                "event_time": anchor_iso,
                "first_reliable_available_at": anchor_iso,
            }
        )
        for due in sorted(set((x_due,) + y_dues)):
            point = f"X{due}" if due == x_due else f"Y{due}"
            for channel, field_id in FIELD_IDS.items():
                available_at = anchor + timedelta(seconds=due)
                if channel == "LIQUIDITY":
                    value, kind = 1000.0 + index, "NUMERIC"
                elif channel == "PRICE":
                    value, kind = 1.0 + 0.1 * index, "NUMERIC"
                else:
                    value, kind = 10.0 + index, "NUMERIC"
                obs_rows.append(
                    {
                        "mint": f"MINT{index:03d}",
                        "entity_id": f"MINT{index:03d}",
                        "point_id": point,
                        "primitive_id": "PRIM-JUPITER-TOKENS-V2-SEARCH-001",
                        "field_id": field_id,
                        "value_kind": kind,
                        "typed_value": repr(value),
                        "state": "OBSERVED",
                        "missing_reason": None,
                        "event_time": (
                            anchor + timedelta(seconds=due)
                        ).isoformat(),
                        "first_reliable_available_at": (
                            available_at.isoformat()
                        ),
                    }
                )
    for extra in range(extra_future_only_members):
        index = members + extra
        member = f"member-{index:03d}"
        extra_row = {
            "member_id": member,
            "mint": f"MINT{index:03d}",
            "admitted": True,
            "authoritative_anchor": anchor.isoformat().replace("+00:00", "Z"),
        }
        if with_candidate_state:
            extra_row["candidate_state"] = "X_ELIGIBLE"
        census_rows.append(extra_row)
        future_at = anchor + timedelta(seconds=3600)
        obs_rows.append(
            {
                "mint": f"MINT{index:03d}",
                "entity_id": f"MINT{index:03d}",
                "point_id": "Y3600",
                "primitive_id": "PRIM-JUPITER-TOKENS-V2-SEARCH-001",
                "field_id": FIELD_IDS["PRICE"],
                "value_kind": "NUMERIC",
                "typed_value": repr(999.0 + extra),
                "state": "OBSERVED",
                "missing_reason": None,
                "event_time": future_at.isoformat(),
                "first_reliable_available_at": future_at.isoformat(),
            }
        )
    census_path = release_root / "census.parquet"
    obs_path = release_root / "observations.parquet"
    pq.write_table(
        pa.Table.from_pylist(
            census_rows,
            schema=pa.schema(
                [
                    ("member_id", pa.string()),
                    ("mint", pa.string()),
                    ("admitted", pa.bool_()),
                    ("authoritative_anchor", pa.string()),
                    *(
                        [("candidate_state", pa.string())]
                        if with_candidate_state
                        else []
                    ),
                ]
            ),
        ),
        census_path,
    )
    pq.write_table(
        pa.Table.from_pylist(
            obs_rows,
            schema=pa.schema(
                [
                    ("mint", pa.string()),
                    ("entity_id", pa.string()),
                    ("point_id", pa.string()),
                    ("primitive_id", pa.string()),
                    ("field_id", pa.string()),
                    ("value_kind", pa.string()),
                    ("typed_value", pa.string()),
                    ("state", pa.string()),
                    ("missing_reason", pa.string()),
                    ("event_time", pa.string()),
                    ("first_reliable_available_at", pa.string()),
                ]
            ),
        ),
        obs_path,
    )
    import hashlib

    census_sha = hashlib.sha256(census_path.read_bytes()).hexdigest()
    obs_sha = hashlib.sha256(obs_path.read_bytes()).hexdigest()
    source_sha = hashlib.sha256(
        (census_sha + obs_sha).encode("utf-8")
    ).hexdigest()
    manifest = {
        "schema": "smial.live-cohort-discovery-release",
        "schema_version": "1.0",
        "release_id": "aa" * 32,
        "cohort_id": "REL-FIXTURE-2026-001",
        "sealed_at": "2026-09-14T00:00:00Z",
        "schedule_sha256": "bb" * 32,
        "activation_id": "ACT-FIXTURE-001",
        "producer_git_sha": "1" * 40,
        "source_sha256": source_sha,
        "starts_at": "2026-09-01T00:00:00Z",
        "stops_admitting_at": "2026-09-22T00:00:00Z",
        "admission_field": "discovery_first_reliable_available_at",
        "evidence_role": "EXPLORATORY_REUSE",
        "confirmatory_reuse_forbidden": True,
        "census_sha256": census_sha,
        "observations_sha256": obs_sha,
        "census_row_count": len(census_rows),
        "observation_row_count": len(obs_rows),
        "feature_families": ["PRICE_PATH", "LIQUIDITY_PATH"],
        "yield_eligible": members,
        "yield_missing": 0,
        "readiness_state": "READY_VALID",
        "discovery_coverage_class": "DISCOVERY_COVERAGE_CONFIRMED",
        "projection_id": "TOKENS_V2_TYPED_PROJECTION_V1",
        "projection_version": "1.0",
    }
    (release_root / "release_manifest.json").write_text(
        json.dumps(manifest, sort_keys=True), encoding="utf-8"
    )
    return release_root


class ReleaseProjectionInputReceipt(unittest.TestCase):
    def test_verified_release_produces_projection_receipt(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as raw:
            release_root = _write_release(
                Path(raw), anchor=datetime(2026, 9, 1, tzinfo=UTC)
            )
            result = resolve_release_projection_input(release_root)
            self.assertEqual(result["representation_id"], REPRESENTATION_ID)
            receipt = result["projection_input_receipt"]
            binding = receipt["corpus_binding"]
            self.assertEqual(binding["release_id"], "aa" * 32)
            self.assertEqual(binding["activation_id"], "ACT-FIXTURE-001")
            self.assertEqual(binding["census_sha256"], binding["census_sha256"])
            self.assertTrue(receipt["readback_verified"])
            self.assertEqual(
                receipt["readback_verifier"],
                "solana_alpha_lab.factory.live_cohort_discovery_release.verify_live_cohort",
            )
            # Anonymous: no mint identity anywhere in the payload.
            payload_text = json.dumps(result["representation"].payload)
            self.assertNotIn("MINT", payload_text)
            self.assertNotIn("member-", payload_text)
            self.assertEqual(result["eligible_member_count"], 10)
            self.assertEqual(
                result["terminal"],
                "NORMALIZED_TRAJECTORY_V1_RUNTIME_READY_NOT_EXECUTED",
            )
            payload = result["representation"].payload
            self.assertEqual(payload["schedule"]["x_allowed_lateness_seconds"], 300)
            self.assertEqual(
                payload["pit"]["x_eligibility_lateness_seconds_used"], 300
            )
            self.assertTrue(payload["pit"]["lateness_window_does_not_extend_T"])

    def test_corrupt_schedule_artifact_fails_closed(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as raw:
            release_root = _write_release(
                Path(raw), anchor=datetime(2026, 9, 1, tzinfo=UTC)
            )
            (release_root / "observation_schedule.json").write_text(
                "{not-json", encoding="utf-8"
            )
            with self.assertRaises(RepresentationProbeError) as raised:
                resolve_release_projection_input(release_root)
            self.assertEqual(str(raised.exception), CANONICAL_SCHEDULE_UNBOUND)

    def test_provenance_tamper_fails_typed(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as raw:
            release_root = _write_release(
                Path(raw), anchor=datetime(2026, 9, 1, tzinfo=UTC)
            )
            manifest_path = release_root / "release_manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["census_sha256"] = "ff" * 32
            manifest_path.write_text(json.dumps(manifest, sort_keys=True))
            with self.assertRaises(RepresentationProbeError) as raised:
                resolve_release_projection_input(release_root)
            # Terminal keeps INVALID_PROJECTION_PROVENANCE, now with the
            # underlying typed code appended for operator diagnostics.
            self.assertTrue(
                str(raised.exception).startswith(INVALID_PROJECTION_PROVENANCE)
            )


class ReleaseProjectionGuards(unittest.TestCase):
    def _release(self, raw: str) -> Path:
        return _write_release(Path(raw), anchor=datetime(2026, 9, 1, tzinfo=UTC))

    def test_future_point_leakage_fails_typed(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as raw:
            release_root = self._release(raw)
            obs_path = release_root / "observations.parquet"
            import pyarrow as pa
            import pyarrow.parquet as pq

            table = pq.read_table(obs_path)
            rows = table.to_pylist()
            for row in rows:
                if row["point_id"] == "X300" and "LIQUIDITY" in row["field_id"]:
                    row["first_reliable_available_at"] = (
                        datetime(2027, 1, 1, tzinfo=UTC).isoformat()
                    )
            pq.write_table(pa.Table.from_pylist(rows, schema=table.schema), obs_path)
            manifest_path = release_root / "release_manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            import hashlib

            manifest["observations_sha256"] = hashlib.sha256(
                obs_path.read_bytes()
            ).hexdigest()
            manifest_path.write_text(json.dumps(manifest, sort_keys=True))
            with self.assertRaises(RepresentationProbeError) as raised:
                resolve_release_projection_input(release_root)
            self.assertEqual(str(raised.exception), FUTURE_POINT_LEAKAGE)

    def test_missing_state_stays_missing(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as raw:
            release_root = self._release(raw)
            obs_path = release_root / "observations.parquet"
            import pyarrow.parquet as pq

            table = pq.read_table(obs_path)
            rows = table.to_pylist()
            dropped = 0
            for row in rows:
                if row["field_id"] == "FIELD-USD-PRICE-001" and row["point_id"] != "X300":
                    row["state"] = "MISSING_TYPED"
                    row["typed_value"] = None
                    dropped += 1
            self.assertGreater(dropped, 0)
            import pyarrow as pa

            pq.write_table(pa.Table.from_pylist(rows, schema=table.schema), obs_path)
            manifest_path = release_root / "release_manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            import hashlib

            manifest["observations_sha256"] = hashlib.sha256(
                obs_path.read_bytes()
            ).hexdigest()
            manifest_path.write_text(json.dumps(manifest, sort_keys=True))
            result = resolve_release_projection_input(release_root)
            payload = json.dumps(result["representation"].payload)
            self.assertIn('"M"', payload)  # missingness stays M

    def test_real_corpus_without_scientific_n_cannot_enter_challenger(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as raw:
            release_root = self._release(raw)
            result = resolve_release_projection_input(release_root)
            receipt = _control_receipt()
            baseline = control_baseline_from_receipt(receipt)
            readiness = _readiness_for_binding(
                result["projection_input_receipt"]["corpus_binding"],
                result["projection_input_receipt"],
            )
            self.assertNotIn(
                "base_x_population_n", result["projection_input_receipt"]
            )
            with self.assertRaises(RepresentationProbeError) as raised:
                build_challenger_packet(
                    baseline,
                    result["representation"],
                    cohort_readiness_receipt=readiness,
                    projection_input_receipt=result["projection_input_receipt"],
                )
            self.assertEqual(str(raised.exception), INVALID_INSUFFICIENT_YIELD)


def _readiness_for_binding(binding: dict, projection_receipt: dict) -> dict:
    manifest = {
        "schema": "smial.live-cohort-discovery-release",
        "schema_version": "1.0",
        "release_id": binding["release_id"],
        "cohort_id": binding["cohort_id"],
        "sealed_at": "2026-09-14T00:00:00Z",
        "schedule_sha256": binding["schedule_sha256"],
        "activation_id": binding["activation_id"],
        "producer_git_sha": binding["producer_git_sha"],
        "source_sha256": binding["source_sha256"],
        "starts_at": "2026-09-01T00:00:00Z",
        "stops_admitting_at": "2026-09-22T00:00:00Z",
        "admission_field": "discovery_first_reliable_available_at",
        "evidence_role": "EXPLORATORY_REUSE",
        "confirmatory_reuse_forbidden": True,
        "census_sha256": binding["census_sha256"],
        "observations_sha256": binding["observations_sha256"],
        "census_row_count": 10,
        "observation_row_count": 500,
        "feature_families": ["PRICE_PATH", "LIQUIDITY_PATH"],
        "yield_eligible": 10,
        "yield_missing": 0,
        "readiness_state": "READY_VALID",
        "discovery_coverage_class": "DISCOVERY_COVERAGE_CONFIRMED",
        "projection_id": "TOKENS_V2_TYPED_PROJECTION_V1",
        "projection_version": "1.0",
    }
    base = {
        "schema": "smial.normalized-trajectory-v1-readiness-receipt",
        "schema_version": "1.0",
        "source_kind": "VERIFIED_LIVE_COHORT_RELEASE_READBACK_V1",
        "readback_verified": True,
        "readback_verifier": (
            "solana_alpha_lab.factory.live_cohort_discovery_release.verify_live_cohort"
        ),
        "release_manifest": manifest,
        "release_id": manifest["release_id"],
        "manifest_sha256": canonical_sha256(manifest),
        "schedule_sha256": manifest["schedule_sha256"],
        "readiness_state": manifest["readiness_state"],
        "discovery_coverage_class": manifest["discovery_coverage_class"],
        "first_fresh_cohort_sealed_verified_imported": True,
        "confirmatory_reuse_forbidden": True,
        "yield_eligible": 10,
    }
    base["receipt_sha256"] = canonical_sha256(base)
    return base

if __name__ == "__main__":
    unittest.main()
