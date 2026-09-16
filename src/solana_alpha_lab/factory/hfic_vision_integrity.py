"""Deterministic machine vision integrity for the bounded Forge packet.

Bounded context must not be silently blind.  Before Prompt A consumes a
``FORGE_CONTEXT_PACKET``, every omitted feature/grounding/semantic/capability
item must be deterministically accounted for as either:

- ``REDUNDANT_WITH_RETAINED_INFORMATION`` — the same decision-useful concept
  (feature concept + availability semantics) is already represented in the
  retained packet surface; or
- ``INTENTIONALLY_OUTSIDE_THIS_REPRESENTATION`` — the item is not part of the
  declared representation surface (e.g. a feature whose availability class
  makes it unusable for candidate generation under the current surface).

Any material or unknown omission raises ``FORGE_VISION_INTEGRITY_BLOCKED``:
a typed STOP that must never masquerade as ``NO_WORTHY_HYPOTHESIS``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

FORGE_VISION_INTEGRITY_BLOCKED = "FORGE_VISION_INTEGRITY_BLOCKED"
REDUNDANT_WITH_RETAINED_INFORMATION = "REDUNDANT_WITH_RETAINED_INFORMATION"
INTENTIONALLY_OUTSIDE_THIS_REPRESENTATION = (
    "INTENTIONALLY_OUTSIDE_THIS_REPRESENTATION"
)
MATERIAL_CANDIDATE_GENERATION_INFORMATION_LOSS = (
    "MATERIAL_CANDIDATE_GENERATION_INFORMATION_LOSS"
)
UNKNOWN = "UNKNOWN"

# Availability classes whose distinction can change hypothesis admissibility.
_DECISION_MATERIAL_AVAILABILITY = frozenset(
    {
        "PIT_READY",
        "FORWARD_ONLY",
        "MISSING_CAPABILITY",
    }
)
# Classes that never carry decision-material information on their own: the
# concept is historical/missing context that retained families/hints already
# describe, or the feature is outright unavailable.
_NON_MATERIAL_AVAILABILITY = frozenset(
    {
        "MISSING",
        "HISTORICAL_RECONSTRUCTIBLE",
    }
)


class HficVisionIntegrityError(ValueError):
    """Fail-closed vision-integrity error."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def compact_feature_grounding_entries(
    entries: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Compact verbose per-feature grounding into one line per availability class.

    Each entry preserves the decision-useful distinction
    (availability_class, available_to_strategy_semantics, entity_scope) with
    the member feature ids, so no materially distinct concept is lost while
    redundant per-feature verbosity collapses into the smallest equivalent
    machine representation.
    """
    grouped: dict[tuple[str, str, str], list[str]] = {}
    for entry in entries:
        key = (
            str(entry.get("availability_class") or ""),
            str(entry.get("available_to_strategy_semantics") or ""),
            str(entry.get("entity_scope") or ""),
        )
        grouped.setdefault(key, []).append(str(entry.get("feature_id") or ""))
    return [
        {
            "availability_class": key[0],
            "available_to_strategy_semantics": key[1],
            "entity_scope": key[2],
            "feature_ids": sorted(ids),
        }
        for key, ids in sorted(grouped.items())
    ]


def _availability(entry: Mapping[str, Any]) -> str:
    return str(entry.get("availability_class") or "")


def _concept(entry: Mapping[str, Any]) -> str:
    return str(entry.get("feature_id") or "").split("/")[0].split(":")[0]


def classify_feature_omission(
    entry: Mapping[str, Any],
    *,
    retained_concepts: Sequence[str],
    retained_availability: Sequence[str],
) -> dict[str, Any]:
    """Classify one omitted grounding entry against the retained surface."""
    availability = _availability(entry)
    concept = _concept(entry)
    retained_concept_set = {str(item) for item in retained_concepts}
    retained_availability_set = {str(item) for item in retained_availability}

    # A distinct availability distinction that can change admissibility is
    # material unless the exact distinction is retained elsewhere.
    if availability in _DECISION_MATERIAL_AVAILABILITY:
        # Exact concept identity only: prefix similarity (FEAT-X vs
        # FEAT-X-V2) is not evidence the concept is represented.
        represented = (
            concept in retained_concept_set
            and availability in retained_availability_set
        )
        if not represented:
            return {
                "feature_id": entry.get("feature_id"),
                "availability_class": availability,
                "omission_class": MATERIAL_CANDIDATE_GENERATION_INFORMATION_LOSS,
                "why": (
                    "Decision-material availability distinction "
                    f"({availability}) not represented by the retained surface."
                ),
            }
        return {
            "feature_id": entry.get("feature_id"),
            "availability_class": availability,
            "omission_class": REDUNDANT_WITH_RETAINED_INFORMATION,
            "why": "Concept and availability distinction already retained.",
        }

    if availability in _NON_MATERIAL_AVAILABILITY:
        # MISSING features are never usable for candidate generation under the
        # current declared surface; historical-reconstructible detail is
        # background context already described by retained families/hints.
        return {
            "feature_id": entry.get("feature_id"),
            "availability_class": availability,
            "omission_class": INTENTIONALLY_OUTSIDE_THIS_REPRESENTATION,
            "why": (
                "Availability class cannot carry candidate-generation "
                "information under the declared representation."
            ),
        }

    return {
        "feature_id": entry.get("feature_id"),
        "availability_class": availability,
        "omission_class": UNKNOWN,
        "why": "Unmapped availability class.",
    }


def classify_semantic_omission(
    route: str,
    *,
    capability_ids_retained: Sequence[str],
) -> dict[str, Any]:
    """Semantic routes are navigation indexes over capability entries."""
    if capability_ids_retained:
        return {
            "route": route,
            "omission_class": REDUNDANT_WITH_RETAINED_INFORMATION,
            "why": "Capability registry entries remain in the packet.",
        }
    return {
        "route": route,
        "omission_class": MATERIAL_CANDIDATE_GENERATION_INFORMATION_LOSS,
        "why": "Semantic route dropped while no capability entries remain.",
    }


def compute_vision_integrity(
    *,
    grounding_entries: Sequence[Mapping[str, Any]],
    retained_feature_ids: Sequence[str],
    retained_families: Sequence[str],
    retained_grounding_index: Sequence[Mapping[str, Any]] | None = None,
    retained_availability_classes: Sequence[str] | None = None,
    dropped_semantic_routes: Sequence[str] | None = None,
    retained_capability_ids: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Compute the deterministic vision-integrity receipt for one packet.

    ``retained_grounding_index`` is the compact availability index that
    actually reaches Prompt A (rows grouped by availability class with their
    member ``feature_ids``).  An original grounding entry is represented when
    its feature id appears in the retained index; an availability distinction
    is represented when the class is retained.
    """
    retained_feature_set = {str(item) for item in retained_feature_ids}
    retained_family_set = {str(item) for item in retained_families}
    index_rows = list(retained_grounding_index or [])
    index_feature_ids: set[str] = set()
    index_availability: set[str] = set()
    for row in index_rows:
        index_availability.add(str(row.get("availability_class") or ""))
        for feature_id in row.get("feature_ids") or []:
            index_feature_ids.add(str(feature_id))
    if retained_availability_classes:
        index_availability.update(str(item) for item in retained_availability_classes)
    capability_ids = [str(item) for item in (retained_capability_ids or [])]
    dropped_routes = [str(item) for item in (dropped_semantic_routes or [])]

    omissions: list[dict[str, Any]] = []
    for entry in grounding_entries:
        feature_id = str(entry.get("feature_id") or "")
        availability = str(entry.get("availability_class") or "")
        if feature_id in retained_feature_set or feature_id in index_feature_ids:
            continue
        if availability in _DECISION_MATERIAL_AVAILABILITY and availability in index_availability and feature_id in index_feature_ids:
            # The availability distinction AND this exact feature survive in
            # the compact index; the per-feature verbose row was redundant.
            omissions.append(
                {
                    "feature_id": feature_id,
                    "availability_class": availability,
                    "omission_class": REDUNDANT_WITH_RETAINED_INFORMATION,
                    "why": "Feature and availability distinction retained by the compact index.",
                }
            )
            continue
        verdict = classify_feature_omission(
            entry,
            retained_concepts=tuple(retained_feature_set | retained_family_set),
            retained_availability=tuple(index_availability),
        )
        omissions.append(verdict)
    for route in dropped_routes:
        omissions.append(
            classify_semantic_omission(
                route, capability_ids_retained=capability_ids
            )
        )

    material = [
        item
        for item in omissions
        if item["omission_class"]
        == MATERIAL_CANDIDATE_GENERATION_INFORMATION_LOSS
    ]
    unknown = [
        item for item in omissions if item["omission_class"] == UNKNOWN
    ]
    status = "PASS" if not material and not unknown else "BLOCKED"
    receipt: dict[str, Any] = {
        "status": status,
        "schema": "smial.hfic-vision-integrity",
        "schema_version": "1.0",
        "material_information_loss": len(material),
        "unknown_omission": len(unknown),
        "omission_breakdown": {
            REDUNDANT_WITH_RETAINED_INFORMATION: sum(
                1
                for item in omissions
                if item["omission_class"]
                == REDUNDANT_WITH_RETAINED_INFORMATION
            ),
            INTENTIONALLY_OUTSIDE_THIS_REPRESENTATION: sum(
                1
                for item in omissions
                if item["omission_class"]
                == INTENTIONALLY_OUTSIDE_THIS_REPRESENTATION
            ),
            MATERIAL_CANDIDATE_GENERATION_INFORMATION_LOSS: len(material),
            UNKNOWN: len(unknown),
        },
    }
    if material:
        receipt["material_omissions"] = material
    if unknown:
        receipt["unknown_omissions"] = unknown
    if status == "BLOCKED":
        receipt["reason"] = FORGE_VISION_INTEGRITY_BLOCKED
        receipt["reason_code"] = (
            "MATERIAL_CANDIDATE_GENERATION_INFORMATION_LOSS"
            if material
            else UNKNOWN
        )
    return receipt


def assert_vision_integrity_pass(receipt: Mapping[str, Any]) -> None:
    """Fail-closed guard: Prompt A / NO_WORTHY persistence entry point."""
    if not isinstance(receipt, Mapping) or receipt.get("status") != "PASS":
        reason = (
            receipt.get("reason")
            if isinstance(receipt, Mapping)
            else FORGE_VISION_INTEGRITY_BLOCKED
        )
        raise HficVisionIntegrityError(str(reason) or FORGE_VISION_INTEGRITY_BLOCKED)
