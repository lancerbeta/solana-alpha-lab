"""Content-stable candidate identity for Hypothesis Forge sessions."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from solana_alpha_lab.factory.run_passport import canonical_sha256


IDENTITY_FIELDS = (
    "claim",
    "mechanism",
    "actor_counterparty",
    "population",
    "decision_timestamp",
    "primary_x_family",
    "primary_y",
    "horizon_notional",
    "negative_control",
    "cheapest_falsifier",
)
NON_IDENTITY_KEYS = frozenset(
    {
        "display_ordinal",
        "label",
        "generated_at",
        "model",
        "live_git_head",
        "candidate_id",
    }
)
PREFIX_LEN = 12
PREFIX_STEP = 4
_NON_WORD = re.compile(r"[^\w]+", flags=re.UNICODE)


class HficIdentityError(ValueError):
    """Fail-closed candidate identity error."""


@dataclass(frozen=True, slots=True)
class CandidateIdentity:
    candidate_id: str
    full_sha256: str
    definition: dict[str, str]
    display_ordinal: int | None
    label: str


def normalize_text(value: object) -> str:
    if not isinstance(value, str):
        raise HficIdentityError("IDENTITY_FIELD_INVALID")
    text = unicodedata.normalize("NFKC", value).casefold()
    text = _NON_WORD.sub(" ", text)
    return " ".join(text.split())


def canonical_candidate_definition(card: Mapping[str, Any]) -> dict[str, str]:
    missing = [field for field in IDENTITY_FIELDS if field not in card]
    if missing:
        raise HficIdentityError("CANDIDATE_DEFINITION_INCOMPLETE")
    definition = {field: normalize_text(card[field]) for field in IDENTITY_FIELDS}
    if any(not definition[field] for field in IDENTITY_FIELDS):
        raise HficIdentityError("CANDIDATE_DEFINITION_INCOMPLETE")
    return definition


def candidate_identity(card: Mapping[str, Any]) -> CandidateIdentity:
    definition = canonical_candidate_definition(card)
    full_sha256 = canonical_sha256(definition)
    ordinal = card.get("display_ordinal")
    label = str(card.get("label") or "").strip()
    return CandidateIdentity(
        candidate_id=_format_candidate_id(full_sha256, PREFIX_LEN),
        full_sha256=full_sha256,
        definition=definition,
        display_ordinal=ordinal if isinstance(ordinal, int) else None,
        label=label,
    )


def assign_portfolio_ids(cards: Sequence[Mapping[str, Any]]) -> list[CandidateIdentity]:
    identities = [candidate_identity(card) for card in cards]
    full_hashes = [item.full_sha256 for item in identities]
    if len(full_hashes) != len(set(full_hashes)):
        raise HficIdentityError("DUPLICATE_CANDIDATE_DEFINITION")
    length = PREFIX_LEN
    while length <= 64:
        ids = [_format_candidate_id(item.full_sha256, length) for item in identities]
        if len(ids) == len(set(ids)):
            return [
                CandidateIdentity(
                    candidate_id=candidate_id,
                    full_sha256=item.full_sha256,
                    definition=item.definition,
                    display_ordinal=item.display_ordinal,
                    label=item.label,
                )
                for candidate_id, item in zip(ids, identities, strict=True)
            ]
        length += PREFIX_STEP
    raise HficIdentityError("CANDIDATE_ID_COLLISION")


def _format_candidate_id(full_sha256: str, length: int) -> str:
    return f"HFIC-CAND-{full_sha256[:length].upper()}"
