"""SQLite COMPLETED-body compaction eligibility. Production compaction stays off."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


class SqliteEligibilityError(ValueError):
    """Typed SQLite body-removal eligibility failure."""


def sqlite_body_compaction_eligible(
    *,
    call_state: str,
    raw_materialized: bool,
    extracted_sha256: str,
    expected_response_sha256: str,
    unresolved_recovery: bool,
    publication_open: bool,
    production_compaction_enabled: bool,
) -> dict[str, Any]:
    if production_compaction_enabled is not True:
        return {"eligible": False, "reason": "PRODUCTION_COMPACTION_DISABLED"}
    if call_state != "COMPLETED":
        return {"eligible": False, "reason": "CALL_NOT_COMPLETED"}
    if raw_materialized is not True:
        return {"eligible": False, "reason": "RAW_NOT_MATERIALIZED"}
    if extracted_sha256 != expected_response_sha256 or len(extracted_sha256) != 64:
        return {"eligible": False, "reason": "RAW_RESPONSE_SHA256_MISMATCH"}
    if unresolved_recovery:
        return {"eligible": False, "reason": "UNRESOLVED_RECOVERY_DEPENDENCY"}
    if publication_open:
        return {"eligible": False, "reason": "OPEN_PUBLICATION_DEPENDENCY"}
    return {"eligible": True, "reason": "ELIGIBLE_NOT_APPLIED"}
