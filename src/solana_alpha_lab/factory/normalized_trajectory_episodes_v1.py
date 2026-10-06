"""NORMALIZED_TRAJECTORY_EPISODES_V1: additive prefix-only normalized view of episodes.

This is a new representation, not a new version of the frozen newborn
``NORMALIZED_TRAJECTORY_V1`` (X/Y points, Y1800 cutoff, CONTROL protocol).  It reads
real episode points ``E300 / E900 / E1800`` of PRICE, LIQUIDITY and HOLDERS through the
one episode point/clock resolver, inside the same research scope as the BASE question.

Per episode (keyed by ``episode_id``, never by mint) each channel yields two adjacent
transitions ``E300->E900`` and ``E900->E1800`` symbolised U (up), D (down), F (flat) or
M (a point or a usable value is missing).  A joint motif is the three channel strings.
Only counts of motifs leave the module: no identity, no raw sequence, no target, no
value after the decision point.  A motif is a description for the model; it is not an
executable feature.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any

from solana_alpha_lab.factory.hfic_research_scope import ResolvedScope, sha256_of

REPRESENTATION_ID = "NORMALIZED_TRAJECTORY_EPISODES_V1"
REPRESENTATION_VERSION = "1.0"
SCHEMA = "smial.normalized-trajectory-episodes"
PREFIX_POINTS = ("E300", "E900", "E1800")
DECISION_POINT = "E1800"
PRICE = "FIELD-USD-PRICE-001"
LIQUIDITY = "FIELD-LIQUIDITY-USD-001"
HOLDERS = "FIELD-HOLDER-COUNT-001"
CHANNELS = (("P", "PRICE", PRICE), ("L", "LIQUIDITY", LIQUIDITY), ("H", "HOLDERS", HOLDERS))
MAX_MOTIFS = 8
SYMBOLS = {"U": "strictly up", "D": "strictly down", "F": "equal", "M": "a point or a usable value is missing"}


def representation_search_key(
    base_search_key: str, parent_session_id: str, payload_sha256: str, scope_applied_sha256: str
) -> str:
    """The journal of one profile attempt: BASE journal + parent + exact payload + applied scope.

    One owner for the freeze receipt and the ordinary-operation gate.
    """

    import hashlib

    text = f"{base_search_key}:{REPRESENTATION_ID}:{parent_session_id}:{payload_sha256}:{scope_applied_sha256}"
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class EpisodeProfileError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def feature_name(channel: str, point: str) -> str:
    return f"{channel}_{point}"


def prefix_features() -> list[dict[str, Any]]:
    """The nine point reads, expressed in the ordinary episode feature vocabulary."""

    return [
        {"name": feature_name(letter, point), "op": "point_value", "field_id": field, "point": point}
        for letter, _name, field in CHANNELS
        for point in PREFIX_POINTS
    ]


def transition_symbol(left: float | None, right: float | None, *, positive_required: bool) -> str:
    """U/D/F/M from two prefix values. No interpolation, no fallback to another channel."""

    for value in (left, right):
        if value is None or not math.isfinite(float(value)):
            return "M"
        if positive_required and float(value) <= 0:
            return "M"
    if float(right) > float(left):
        return "U"
    if float(right) < float(left):
        return "D"
    return "F"


def episode_motif(values: Mapping[str, float | None]) -> str:
    """Joint motif of one episode, e.g. ``P:DU|L:FU|H:UU``."""

    parts = []
    for letter, _name, _field in CHANNELS:
        positive = letter in {"P", "L"}
        symbols = "".join(
            transition_symbol(
                values.get(feature_name(letter, a)),
                values.get(feature_name(letter, b)),
                positive_required=positive,
            )
            for a, b in zip(PREFIX_POINTS, PREFIX_POINTS[1:])
        )
        parts.append(f"{letter}:{symbols}")
    return "|".join(parts)


def _panel(motifs: Sequence[str]) -> dict[str, Any]:
    counts = Counter(motifs)
    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    kept, rest = ranked[:MAX_MOTIFS], ranked[MAX_MOTIFS:]
    members = len(motifs)
    omitted_members = sum(count for _motif, count in rest)
    panel = {
        "members_n": members,
        "motifs": [{"motif": motif, "n": count} for motif, count in kept],
        "omitted_motif_n": len(rest),
        "omitted_member_n": omitted_members,
        # Members that carry at least one missing transition are never dropped silently.
        "missing_heavy_member_n": sum(count for motif, count in counts.items() if "M" in motif.replace("|", "")),
        "missing_heavy_motifs_in_top_n": sum(1 for motif, _count in kept if "M" in motif.replace("|", "")),
    }
    if sum(item["n"] for item in panel["motifs"]) + omitted_members != members:
        raise EpisodeProfileError("EPISODE_PROFILE_COUNT_MISMATCH")
    return panel


def build_episode_normalized_profile(
    census: Sequence[Mapping[str, Any]],
    observations: Sequence[Mapping[str, Any]],
    binding: Sequence[Mapping[str, Any]],
    resolved: ResolvedScope,
    *,
    universe_policy: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Anonymous scope-bound motif panels. The scope mask is applied before aggregation."""

    from solana_alpha_lab.factory import hfic_temporal_discovery as temporal

    if not isinstance(resolved, ResolvedScope):
        raise EpisodeProfileError("RESEARCH_SCOPE_REQUIRED")
    resolved.require_covered()
    features = [
        temporal._canonical_feature(item, point_fn=temporal._episode_point, offset_fn=temporal._episode_offset)
        for item in prefix_features()
    ]
    body = {"decision_point": DECISION_POINT, "features": features, "predicates": []}
    members, _cohorts, _seen, _dups, _conflicts, _mints = temporal._project_episode_members(
        census,
        observations,
        body,
        temporal.require_episode_binding_rows(binding),
        universe_policy=universe_policy,
        prefix_only=True,
        scope=resolved,
    )
    admitted = [item for item in members if item.get("in_base")]
    # The mask is applied here, before any aggregation: outside-scope episodes never reach a panel.
    in_scope = [item for item in admitted if resolved.universe.get(item.get("episode_id")) == "TRUE"]
    eligible = [item for item in in_scope if item.get("decision_eligible")]
    excluded: Counter[str] = Counter()
    for item in in_scope:
        if not item.get("decision_eligible"):
            excluded[str(item.get("exclusion") or "DECISION_NOT_ELIGIBLE")] += 1
    motifs_all, motifs_signal, motifs_other = [], [], []
    for item in eligible:
        motif = episode_motif(item["feature_values"])
        motifs_all.append(motif)
        if resolved.list_condition is not None:
            (motifs_signal if resolved.signal.get(item["episode_id"]) == "TRUE" else motifs_other).append(motif)
    panels: dict[str, Any] = {"BASE": _panel(motifs_all)}
    if resolved.list_condition is not None:
        panels["SIGNAL"] = _panel(motifs_signal)
        panels["COMPARATOR"] = _panel(motifs_other)
    payload = {
        "schema": SCHEMA,
        "representation_id": REPRESENTATION_ID,
        "representation_version": REPRESENTATION_VERSION,
        "population": "OPPORTUNITY_EPISODES",
        "anchor_kind": "NOMINATION_T0",
        "decision_point": DECISION_POINT,
        "prefix_points": list(PREFIX_POINTS),
        "channels": [name for _letter, name, _field in CHANNELS],
        "symbols": dict(SYMBOLS),
        "motif_format": "<channel letter>:<symbol E300->E900><symbol E900->E1800>, channels P L H joined by |",
        "normalization": "WITHIN_EPISODE_PREFIX_ONLY_NO_FUTURE_DENOMINATOR",
        "values_exposed": "PREFIX_POINTS_AT_OR_BEFORE_DECISION_NO_TARGET",
        "research_scope_rule_sha256": resolved.rule_sha256,
        "scope_applied_sha256": resolved.applied_sha256,
        "scope_evidence_sha256": resolved.evidence_sha256,
        "scope_counts": {
            "admitted_n": len(admitted),
            "outside_scope_n": len(admitted) - len(in_scope),
            "admitted_in_scope_n": len(in_scope),
            "decision_eligible_n": len(eligible),
            "not_represented_n": len(in_scope) - len(eligible),
            "not_represented_by_reason": dict(sorted(excluded.items())),
            "coverage": resolved.coverage(),
        },
        "panels": panels,
        "motif_is_executable_feature": False,
        "non_claims": [
            "MOTIF_IS_A_DESCRIPTION_NOT_A_FEATURE",
            "NO_TARGET_OR_OUTCOME_VALUE",
            "NOT_THE_FROZEN_NEWBORN_NORMALIZED_TRAJECTORY_V1",
            "MEMBERSHIP_IS_OBSERVATIONAL_NOT_CAUSAL",
        ],
    }
    payload["representation_payload_sha256"] = sha256_of(payload)
    return payload


_MOTIF_RE = re.compile(r"^P:[UDFM]{2}\|L:[UDFM]{2}\|H:[UDFM]{2}$")
_PAYLOAD_KEYS = frozenset(
    {
        "schema", "representation_id", "representation_version", "population", "anchor_kind", "decision_point", "prefix_points",
        "channels", "symbols", "motif_format", "normalization", "values_exposed", "research_scope_rule_sha256", "scope_applied_sha256",
        "scope_evidence_sha256", "scope_counts", "panels", "motif_is_executable_feature", "non_claims", "representation_payload_sha256",
    }
)
_PANEL_KEYS = frozenset({"members_n", "motifs", "omitted_motif_n", "omitted_member_n", "missing_heavy_member_n", "missing_heavy_motifs_in_top_n"})


def validate_episode_payload(payload: object, *, expected_rule_sha256: object) -> None:
    """Closed-schema check of an accepted profile: re-hash, scope rule, only motif counts.

    The builder is clean by construction; this makes the accepted bytes clean too.
    """

    from solana_alpha_lab.factory.hfic_research_scope import sha256_of

    def need(condition: bool, code: str) -> None:
        if not condition:
            raise EpisodeProfileError(code)

    need(isinstance(payload, Mapping) and set(payload) == _PAYLOAD_KEYS, "EPISODE_PAYLOAD_INVALID")
    need(payload["representation_id"] == REPRESENTATION_ID and payload["schema"] == SCHEMA, "EPISODE_PAYLOAD_INVALID")
    body = {key: value for key, value in payload.items() if key != "representation_payload_sha256"}
    need(sha256_of(body) == payload["representation_payload_sha256"], "EPISODE_PAYLOAD_HASH_MISMATCH")
    need(payload["motif_is_executable_feature"] is False, "EPISODE_PAYLOAD_INVALID")
    panels = payload["panels"]
    need(isinstance(panels, Mapping) and "BASE" in panels and set(panels) <= {"BASE", "SIGNAL", "COMPARATOR"}, "EPISODE_PAYLOAD_INVALID")
    for panel in panels.values():
        need(isinstance(panel, Mapping) and set(panel) == _PANEL_KEYS, "EPISODE_PAYLOAD_INVALID")
        need(isinstance(panel["motifs"], list) and len(panel["motifs"]) <= MAX_MOTIFS, "EPISODE_PAYLOAD_INVALID")
        for item in panel["motifs"]:
            need(isinstance(item, Mapping) and set(item) == {"motif", "n"} and isinstance(item["motif"], str) and _MOTIF_RE.match(item["motif"]) is not None, "EPISODE_PAYLOAD_INVALID")
        need(sum(item["n"] for item in panel["motifs"]) + panel["omitted_member_n"] == panel["members_n"], "EPISODE_PROFILE_COUNT_MISMATCH")
    # A profile belongs to exactly the candidate scope it was built for (None = an unscoped candidate: refused).
    need(payload["research_scope_rule_sha256"] == expected_rule_sha256, "EPISODE_PAYLOAD_SCOPE_MISMATCH")
