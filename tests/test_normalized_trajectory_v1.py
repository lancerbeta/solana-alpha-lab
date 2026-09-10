from __future__ import annotations

import json
import math
import sys
import unittest
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory import normalized_trajectory_v1 as normalized_trajectory_module
from solana_alpha_lab.factory.normalized_trajectory_v1 import (
    DEFAULT_SCHEDULE,
    FIELD_IDS,
    LifecycleSchedule,
    NormalizedTrajectoryError,
    NormalizedTrajectoryRepresentation,
    TypedLifecycleObservation,
    project_normalized_trajectory,
)
from solana_alpha_lab.factory.observation_schedule import schedule_sha256

ANCHOR = datetime(2026, 1, 1, tzinfo=UTC)


def _row(
    member: str,
    due: int,
    field: str,
    value: object | None,
    *,
    observed: bool = True,
    available_at: datetime | None = None,
    schedule_sha256: str | None = None,
    activation_id: str | None = None,
) -> TypedLifecycleObservation:
    return TypedLifecycleObservation(
        member_id=member,
        member_anchor_at=ANCHOR,
        due_offset_seconds=due,
        field_id=FIELD_IDS[field],
        value=value,
        first_reliable_available_at=(
            ANCHOR + timedelta(seconds=due)
            if available_at is None and observed
            else available_at
        ),
        observed=observed,
        schedule_sha256=(
            DEFAULT_SCHEDULE.schedule_sha256
            if schedule_sha256 is None
            else schedule_sha256
        ),
        activation_id=(
            DEFAULT_SCHEDULE.activation_id if activation_id is None else activation_id
        ),
    )


def _series(member: str, field: str, values: tuple[object | None, ...]) -> list[TypedLifecycleObservation]:
    if field == "LIQUIDITY":
        values = tuple(
            None if value is None else float(value) * 1000.0 for value in values
        )
    rows: list[TypedLifecycleObservation] = []
    for due, value in zip(DEFAULT_SCHEDULE.prefix_due_offsets, values, strict=True):
        rows.append(_row(member, due, field, value, observed=value is not None))
    return rows


class NormalizedTrajectoryProjectionTests(unittest.TestCase):
    def test_pit_missing_volume_fallback_and_future_are_deterministic(self) -> None:
        rows = []
        rows.extend(_series("mint-a", "PRICE", (1.0, 2.0, 1.0)))
        rows.extend(_series("mint-a", "LIQUIDITY", (10.0, 10.0, 5.0)))
        rows.extend(_series("mint-a", "VOLUME", (3.0, 4.0, 2.0)))
        rows.extend(_series("mint-a", "TRADERS", (1.0, 2.0, 2.0)))

        rows.extend(_series("mint-b", "PRICE", (1.0, None, 2.0)))
        rows.extend(_series("mint-b", "LIQUIDITY", (8.0, 8.0, 8.0)))
        rows.extend(_series("mint-b", "VOLUME", (1.0, None, 2.0)))
        rows.extend(_series("mint-b", "TRADERS", (2.0, 1.0, 1.0)))
        rows.append(_row("mint-b", 3600, "PRICE", 999999.0))

        projected = project_normalized_trajectory(rows)
        reversed_projected = project_normalized_trajectory(list(reversed(rows)))
        self.assertEqual(projected.payload, reversed_projected.payload)
        self.assertEqual(projected.payload["eligible_member_count"], 2)
        self.assertEqual(projected.payload["volume_mode"], "TAKER_OBSERVED")
        self.assertEqual(projected.payload["histogram_member_count"], 2)
        rendered = json.dumps(projected.payload, sort_keys=True)
        self.assertNotIn("mint-a", rendered)
        self.assertNotIn("mint-b", rendered)
        self.assertNotIn("999999", rendered)
        motifs = [item["motif"] for item in projected.payload["histogram"]]
        self.assertIn(
            {
                "PRICE": "U-D",
                "LIQUIDITY": "F-D",
                "VOLUME": "U-D",
                "TRADERS": "U-F",
            },
            motifs,
        )
        self.assertTrue(projected.payload_sha256)
        self.assertEqual(projected.payload["payload_sha256"], projected.payload_sha256)

    def test_missing_stays_missing_and_buy_sell_are_not_summed(self) -> None:
        rows = []
        rows.extend(_series("synthetic-a", "PRICE", (1.0, None, 2.0)))
        rows.extend(_series("synthetic-a", "LIQUIDITY", (2.0, 3.0, 4.0)))
        rows.extend(_series("synthetic-a", "TRADERS", (1.0, 1.0, 2.0)))
        rows.extend(_series("synthetic-a", "VOLUME_BUY", (5.0, 7.0, 6.0)))
        rows.extend(_series("synthetic-a", "VOLUME_SELL", (4.0, 4.0, 8.0)))
        projected = project_normalized_trajectory(rows)
        self.assertEqual(
            projected.payload["volume_mode"],
            "ACTIVITY_VOLUME_OBSERVED_BUY_PLUS_SELL",
        )
        motif = projected.payload["histogram"][0]["motif"]
        self.assertEqual(motif["PRICE"], "M-M")
        self.assertEqual(motif["VOLUME_BUY"], "U-D")
        self.assertEqual(motif["VOLUME_SELL"], "F-U")
        self.assertNotIn("VOLUME", motif)

    def test_mixed_taker_availability_keeps_missing_members_missing(self) -> None:
        rows = []
        rows.extend(_series("with-taker", "PRICE", (1.0, 2.0, 3.0)))
        rows.extend(_series("with-taker", "LIQUIDITY", (1.0, 1.0, 1.0)))
        rows.extend(_series("with-taker", "VOLUME", (1.0, 2.0, 3.0)))
        rows.extend(_series("with-taker", "TRADERS", (1.0, 1.0, 1.0)))
        rows.extend(_series("fallback-only", "PRICE", (1.0, 2.0, 3.0)))
        rows.extend(_series("fallback-only", "LIQUIDITY", (1.0, 1.0, 1.0)))
        rows.extend(_series("fallback-only", "VOLUME_BUY", (5.0, 6.0, 7.0)))
        rows.extend(_series("fallback-only", "VOLUME_SELL", (4.0, 4.0, 5.0)))
        rows.extend(_series("fallback-only", "TRADERS", (1.0, 1.0, 1.0)))

        projected = project_normalized_trajectory(rows)

        self.assertEqual(projected.payload["volume_mode"], "TAKER_OBSERVED")
        fallback_motifs = [
            item["motif"]
            for item in projected.payload["histogram"]
            if item["motif"]["VOLUME"] == "M-M"
        ]
        self.assertEqual(len(fallback_motifs), 1)
        self.assertNotIn("VOLUME_BUY", fallback_motifs[0])
        self.assertNotIn("VOLUME_SELL", fallback_motifs[0])

    def test_x_eligibility_filters_members_at_the_x_pit(self) -> None:
        rows = []
        rows.extend(_series("eligible", "PRICE", (1.0, 2.0, 3.0)))
        rows.extend(_series("eligible", "LIQUIDITY", (1.0, 1.0, 1.0)))
        rows.extend(_series("eligible", "TRADERS", (1.0, 1.0, 1.0)))
        rows.extend(_series("below-floor", "PRICE", (1.0, 2.0, 3.0)))
        rows.extend(_series("below-floor", "LIQUIDITY", (0.999, 0.999, 0.999)))
        rows.extend(_series("below-floor", "TRADERS", (1.0, 1.0, 1.0)))

        projected = project_normalized_trajectory(rows)

        self.assertEqual(projected.payload["eligible_member_count"], 1)
        self.assertEqual(projected.payload["histogram_member_count"], 1)

    def test_invalid_and_late_values_emit_m_without_dropping_slots(self) -> None:
        rows = []
        rows.extend(_series("synthetic-a", "PRICE", (0.0, 2.0, 3.0)))
        rows.extend(_series("synthetic-a", "LIQUIDITY", (1.0, 2.0, 3.0)))
        rows.extend(_series("synthetic-a", "TRADERS", (1.0, 1.0, 1.0)))
        rows.append(
            _row(
                "synthetic-a",
                300,
                "VOLUME",
                1.0,
                available_at=ANCHOR + timedelta(seconds=1801),
            )
        )
        rows.append(_row("synthetic-a", 900, "VOLUME", 2.0))
        rows.append(_row("synthetic-a", 1800, "VOLUME", 3.0))
        projected = project_normalized_trajectory(rows)
        motif = projected.payload["histogram"][0]["motif"]
        self.assertEqual(motif["PRICE"], "M-U")
        self.assertEqual(motif["VOLUME"], "M-U")

    def test_typed_values_are_not_coerced_and_observed_zero_does_not_create_fallback(self) -> None:
        with self.assertRaises(NormalizedTrajectoryError) as raised:
            _row("synthetic-a", 300, "PRICE", "1")
        self.assertEqual(str(raised.exception), "VALUE_MUST_BE_TYPED_NUMERIC_OR_NULL")

        rows = []
        rows.extend(_series("synthetic-a", "PRICE", (1.0, 2.0, 3.0)))
        rows.extend(_series("synthetic-a", "LIQUIDITY", (1.0, 1.0, 1.0)))
        rows.extend(_series("synthetic-a", "TRADERS", (1.0, 1.0, 1.0)))
        rows.extend(_series("synthetic-a", "VOLUME", (0.0, 0.0, 0.0)))
        rows.extend(_series("synthetic-a", "VOLUME_BUY", (5.0, 6.0, 7.0)))
        rows.extend(_series("synthetic-a", "VOLUME_SELL", (4.0, 4.0, 5.0)))
        projected = project_normalized_trajectory(rows)
        self.assertEqual(projected.payload["volume_mode"], "TAKER_OBSERVED")
        self.assertEqual(projected.payload["histogram"][0]["motif"]["VOLUME"], "M-M")
        self.assertNotIn("VOLUME_BUY", projected.payload["histogram"][0]["motif"])

    def test_nonfinite_taker_is_unavailable_and_allows_buy_sell_fallback(self) -> None:
        rows = []
        rows.extend(_series("synthetic-a", "PRICE", (1.0, 2.0, 3.0)))
        rows.extend(_series("synthetic-a", "LIQUIDITY", (1.0, 1.0, 1.0)))
        rows.extend(_series("synthetic-a", "TRADERS", (1.0, 1.0, 1.0)))
        rows.extend(_series("synthetic-a", "VOLUME", (math.nan, math.inf, -math.inf)))
        rows.extend(_series("synthetic-a", "VOLUME_BUY", (5.0, 6.0, 7.0)))
        rows.extend(_series("synthetic-a", "VOLUME_SELL", (4.0, 4.0, 5.0)))

        projected = project_normalized_trajectory(rows)

        self.assertEqual(
            projected.payload["volume_mode"],
            "ACTIVITY_VOLUME_OBSERVED_BUY_PLUS_SELL",
        )
        self.assertIn("VOLUME_BUY", projected.payload["field_ids"])
        self.assertNotIn("VOLUME", projected.payload["field_ids"])

    def test_mapping_identity_fields_are_not_coerced(self) -> None:
        with self.assertRaises(NormalizedTrajectoryError) as raised:
            TypedLifecycleObservation.from_mapping(
                {
                    "member_id": 7,
                    "member_anchor_at": ANCHOR,
                    "due_offset_seconds": 300,
                    "field_id": FIELD_IDS["PRICE"],
                    "value": 1.0,
                    "first_reliable_available_at": ANCHOR,
                }
            )
        self.assertEqual(str(raised.exception), "MEMBER_KEY_INVALID")

        with self.assertRaises(NormalizedTrajectoryError) as raised:
            LifecycleSchedule.from_mapping({"schedule_id": 7})
        self.assertEqual(str(raised.exception), "SCHEDULE_ID_INVALID")

    def test_schedule_x_900_is_insufficient_prefix(self) -> None:
        with self.assertRaises(NormalizedTrajectoryError) as raised:
            LifecycleSchedule(x_due_offset_seconds=900)
        self.assertEqual(str(raised.exception), "INVALID_INSUFFICIENT_PREFIX")

    def test_default_schedule_emits_canonical_schedule_binding(self) -> None:
        projected = project_normalized_trajectory([])
        schedule = projected.payload["schedule"]
        self.assertRegex(schedule["schedule_sha256"], r"^[0-9a-f]{64}$")

    def test_schedule_document_must_match_compact_schedule_fields(self) -> None:
        document = deepcopy(normalized_trajectory_module._SYNTHETIC_SCHEDULE_DOCUMENT)
        x_point = dict(document["x_point"])
        x_point["point_id"] = "X600"
        x_point["due_offset_seconds"] = 600
        document["x_point"] = x_point
        with self.assertRaises(NormalizedTrajectoryError) as raised:
            LifecycleSchedule(
                x_due_offset_seconds=300,
                schedule_sha256=schedule_sha256(document),
                schedule_document=document,
            )
        self.assertEqual(str(raised.exception), "SCHEDULE_DOCUMENT_BINDING_MISMATCH")

    def test_schedule_hash_must_match_canonical_schedule_contents(self) -> None:
        with self.assertRaises(NormalizedTrajectoryError) as raised:
            LifecycleSchedule(schedule_sha256="00" * 32)
        self.assertEqual(str(raised.exception), "SCHEDULE_DOCUMENT_REQUIRED")

        with self.assertRaises(NormalizedTrajectoryError) as raised:
            LifecycleSchedule(x_due_offset_seconds=600)
        self.assertEqual(str(raised.exception), "SCHEDULE_SHA256_MISMATCH")

    def test_observations_must_share_imported_schedule_and_activation(self) -> None:
        rows = _series("synthetic-a", "PRICE", (1.0, 2.0, 3.0))
        rows.append(
            _row(
                "synthetic-a",
                300,
                "LIQUIDITY",
                1.0,
                activation_id="OTHER-ACTIVATION",
            )
        )
        with self.assertRaises(NormalizedTrajectoryError) as raised:
            project_normalized_trajectory(rows)
        self.assertEqual(
            str(raised.exception), "OBSERVATION_ACTIVATION_BINDING_MISMATCH"
        )

    def test_future_only_member_cannot_enter_pre_t_denominator(self) -> None:
        rows = []
        rows.extend(_series("known-member", "PRICE", (1.0, 2.0, 3.0)))
        rows.extend(_series("known-member", "LIQUIDITY", (1.0, 1.0, 1.0)))
        rows.extend(_series("known-member", "TRADERS", (1.0, 1.0, 1.0)))
        rows.append(_row("future-only-member", 3600, "PRICE", 999.0))

        with self.assertRaises(NormalizedTrajectoryError) as raised:
            project_normalized_trajectory(rows)
        self.assertEqual(
            str(raised.exception), "FUTURE_ONLY_MEMBER_NOT_BOUND_TO_PREFIX"
        )

    def test_representation_constructor_is_not_public_provenance_boundary(self) -> None:
        with self.assertRaises(NormalizedTrajectoryError) as raised:
            NormalizedTrajectoryRepresentation({})
        self.assertEqual(
            str(raised.exception), "REPRESENTATION_CONSTRUCTION_FORBIDDEN"
        )

    def test_representation_payload_is_recursively_immutable(self) -> None:
        projected = project_normalized_trajectory([])
        with self.assertRaises(TypeError):
            projected._base_payload["histogram"] = ()  # type: ignore[index]
        with self.assertRaises(TypeError):
            projected._base_payload["schedule"]["schedule_id"] = "drift"  # type: ignore[index]
        self.assertEqual(projected.payload["schedule"]["schedule_id"], DEFAULT_SCHEDULE.schedule_id)

    def test_histogram_is_bounded_and_m_heavy_tuples_are_allowed(self) -> None:
        rows: list[TypedLifecycleObservation] = []
        patterns = (
            (1.0, 2.0, 3.0),
            (1.0, 3.0, 2.0),
            (1.0, 1.0, 2.0),
            (1.0, 2.0, 2.0),
            (2.0, 1.0, 3.0),
            (2.0, 3.0, 1.0),
            (2.0, 2.0, 1.0),
            (3.0, 2.0, 1.0),
            (3.0, 1.0, 2.0),
        )
        for index, pattern in enumerate(patterns):
            member = f"synthetic-{index}"
            rows.extend(_series(member, "PRICE", pattern))
            rows.extend(_series(member, "LIQUIDITY", (1.0, 1.0, 1.0)))
            rows.extend(_series(member, "TRADERS", (1.0, 1.0, 1.0)))
        rows.extend(_series("synthetic-m-heavy", "PRICE", (None, None, 3.0)))
        rows.extend(_series("synthetic-m-heavy", "LIQUIDITY", (1.0, 1.0, 1.0)))
        rows.extend(_series("synthetic-m-heavy", "TRADERS", (1.0, 1.0, 1.0)))
        projected = project_normalized_trajectory(rows)
        self.assertLessEqual(len(projected.payload["histogram"]), 8)
        self.assertEqual(projected.payload["eligible_member_count"], 10)
        self.assertTrue(projected.payload["histogram_truncation"]["m_heavy_members_retained"])
        self.assertTrue(
            any(
                "M" in symbol
                for item in projected.payload["histogram"]
                for symbol in item["motif"].values()
            )
        )
        self.assertTrue(
            any(
                "M-M" in item["motif"].values()
                for item in projected.payload["histogram"]
            )
        )


if __name__ == "__main__":
    unittest.main()
