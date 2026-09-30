"""Authored scientific assessments of ordinary Forge work (ORDINARY_SCIENTIFIC_DISPOSITION_V1).

One RESEARCH_ARTIFACT kind records what an operator, model or owner concluded
about one saved question, or about one bounded pre-values search scope, and on
which basis. The record is advice with a bound basis. It is not owner
authority, not a candidate PASS/KILL, not a search-wide NO_WORTHY terminal and
not a family close. It never reserves a look, spends budget or changes market
identity.

Applicability (CURRENT_FOR_BOUND_BASIS, REVIEW_REQUIRED, ...) is computed on
read from the store as it is now. Nothing here persists a lifecycle state.
Lineage is explicit: a successor names its predecessor ref and hash; the
winner is never chosen by timestamp, filename or load order.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import time
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

ARTIFACT_KIND = "ORDINARY_SCIENTIFIC_DISPOSITION_V1"
BODY_SCHEMA = "smial.hfic-scientific-disposition"
SUPPORTED_SCHEMA_VERSIONS = frozenset({"1.0"})
SCHEMA_VERSION = "1.0"
RECORD_PREFIX = "HFIC-ART-DISP"
CAPABILITY_ID = "CAP-HFIC-SCIENTIFIC-DISPOSITION-001"
CONTEXT_SCHEMA = "smial.hfic-scientific-disposition-context"
SCHEMA_RELATIVE = "catalog/schemas/hfic_scientific_disposition_v1.schema.json"
WRITER_NAME = "hypothesis_forge.disposition-record"

MAX_BODY_BYTES = 16384
COMPACT_CONTEXT_MAX_BYTES = 4096

QUESTION = "QUESTION"
BOUNDED_SEARCH = "BOUNDED_SEARCH_ASSESSMENT"
ASSESSMENT = "ASSESSMENT"
WITHDRAWAL = "WITHDRAWAL"
MODE_NEW = "NEW"
MODE_IMPORT = "HISTORICAL_IMPORT"

LIMITED_NON_CANDIDATE = "LIMITED_NON_CANDIDATE_FOR_THIS_QUESTION"
INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
NO_WORTHY_SIMPLE_NEXT = "NO_WORTHY_SIMPLE_NEXT"

# Allowed (subject kind -> verdict -> recommendations). Kept to real consumers.
_ALLOWED_JUDGEMENTS: dict[str, dict[str, frozenset[str]]] = {
    QUESTION: {
        LIMITED_NON_CANDIDATE: frozenset({"STOP_THIS_QUESTION", "REVIEW_BOUNDED_SCOPE"}),
        INSUFFICIENT_EVIDENCE: frozenset({"STOP_THIS_QUESTION", "REVIEW_BOUNDED_SCOPE"}),
    },
    BOUNDED_SEARCH: {
        NO_WORTHY_SIMPLE_NEXT: frozenset({"PAUSE_CONSIDERED_SIMPLE_SCOPE", "REVIEW_BOUNDED_SCOPE"}),
        INSUFFICIENT_EVIDENCE: frozenset({"REVIEW_BOUNDED_SCOPE"}),
    },
}

STATUS_CURRENT = "CURRENT_FOR_BOUND_BASIS"
STATUS_NOT_RECORDED = "NOT_RECORDED"
STATUS_REVIEW = "REVIEW_REQUIRED"
STATUS_HISTORICAL = "HISTORICAL"
STATUS_WITHDRAWN = "WITHDRAWN"
STATUS_CONFLICT = "CONFLICT"
STATUS_UNREADABLE = "UNREADABLE"

_STATUS_ORDER = {
    STATUS_CONFLICT: 0,
    STATUS_UNREADABLE: 1,
    STATUS_CURRENT: 2,
    STATUS_REVIEW: 3,
    STATUS_WITHDRAWN: 4,
    STATUS_HISTORICAL: 5,
}

CLAIM_BOUNDARY = (
    "Authored assessment of the named scope and bound basis only; not owner "
    "authority, not a candidate verdict, not search-wide NO_WORTHY, not a "
    "family close, not alpha; grants no look, budget or admission."
)

_PACKET_KEYS = frozenset(
    {"schema", "schema_version", "entry", "subject", "basis", "judgement", "withdrawal", "provenance", "supersedes"}
)
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
# Exact copy of the forge CLI physical-path guard (_WINDOWS_PHYSICAL_PATH_RE in
# scripts/hypothesis_forge.py); a test keeps the two identical. Stored advice
# must never trip the guard that protects every Forge readout.
CLI_PHYSICAL_PATH_RE = re.compile(
    r"""
    (?:
        (?<![A-Za-z0-9+.-])[A-Za-z]:(?:(?!//)[\\/]|[^\s\\/:]+\\)
        | (?<!:)//[^/\\\s]+[\\/][^\\\s]+
        | \\\\[^\\/]+[\\/][^\\/]+
        | (?<!\\)\\[^\\/\s]+\\[^\\/\s]+
    )
    """,
    re.VERBOSE,
)
# Further host-path shapes refused in stored text: any backslash, a rooted POSIX
# path of two or more named segments, a well-known home/mount segment, URI
# forms the ResearchStore itself refuses, and the data-root variable name.
_HOST_PATH = re.compile(
    r"\\"
    r"|(?:^|[\s\"'(=,;<>\[\]{}])/[A-Za-z0-9._~+-]+/[A-Za-z0-9._~+-]"
    r"|[/](?:Users|home|root|mnt|srv|tmp|var|opt|private)/"
    r"|//"
    r"|\bfile:/"
    r"|SMIAL_DATA_ROOT"
)


def host_path_in(value: str) -> bool:
    return bool(CLI_PHYSICAL_PATH_RE.search(value) or _HOST_PATH.search(value))


def _string_leaves(value: Any) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []

    def walk(item: Any, where: str) -> None:
        if isinstance(item, str):
            found.append((where, item))
        elif isinstance(item, Mapping):
            for key, child in item.items():
                found.append((f"{where}.{key}:key", str(key)))
                walk(child, f"{where}.{key}" if where else str(key))
        elif isinstance(item, (list, tuple)):
            for index, child in enumerate(item):
                walk(child, f"{where}[{index}]")

    walk(value, "")
    return found


class DispositionError(ValueError):
    """Typed refusal. ``head_refs`` names the actual lineage head when relevant."""

    def __init__(self, code: str, *, head_refs: Sequence[str] | None = None, detail: str | None = None) -> None:
        self.code = code
        self.head_refs = list(head_refs or [])
        self.detail = detail
        super().__init__(code)


class _AlreadyCommitted(Exception):
    pass


def _canonical(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha(payload: Any) -> str:
    return hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest()


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


@lru_cache(maxsize=1)
def _validator() -> Any:
    from jsonschema import Draft202012Validator

    schema = json.loads((_repo_root() / SCHEMA_RELATIVE).read_text(encoding="utf-8"))
    return Draft202012Validator(schema)


@lru_cache(maxsize=1)
def _writer_module_sha256() -> str:
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def _writer_git_sha(repo_root: Path | None) -> str | None:
    if repo_root is None:
        return None
    try:
        completed = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    text = completed.stdout.strip()
    return text if completed.returncode == 0 and re.fullmatch(r"[0-9a-f]{40}", text) else None


# ---------------------------------------------------------------------------
# Subject identity and packet normalization
# ---------------------------------------------------------------------------


def subject_key(subject: Mapping[str, Any]) -> str:
    """Document identifier of one subject. Not a focus, session, slot or trial key."""

    kind = subject.get("subject_kind")
    base = {
        "subject_kind": kind,
        "market_evidence_epoch_sha256": subject.get("market_evidence_epoch_sha256"),
        "owner_focus": subject.get("owner_focus"),
        "journal_scope": subject.get("journal_scope"),
    }
    if kind == QUESTION:
        base["question_spec_sha256"] = subject.get("question_spec_sha256")
    else:
        scope = subject.get("search_scope") if isinstance(subject.get("search_scope"), Mapping) else {}
        base["search_scope"] = {
            "search_tier": scope.get("search_tier"),
            "population": scope.get("population"),
            "window": scope.get("window"),
            "constraints": sorted(str(item) for item in scope.get("constraints") or []),
        }
    return _sha(base)


def _identity(body: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in body.items() if key not in {"disposition_sha256", "ingestion"}}


def record_id_for(disposition_sha256: str) -> str:
    return f"{RECORD_PREFIX}-{disposition_sha256[:40].upper()}"


def _require_hex(value: Any, code: str) -> str:
    if not isinstance(value, str) or not _HEX64.fullmatch(value):
        raise DispositionError(code)
    return value


def _reject_absolute_paths(value: Any) -> None:
    for where, text in _string_leaves(value):
        if host_path_in(text):
            raise DispositionError("DISPOSITION_ABSOLUTE_PATH_FORBIDDEN", detail=where.replace(":key", ""))


def normalize_packet(packet: Mapping[str, Any]) -> dict[str, Any]:
    """Shape-only normalization of an explicit submission. No store reads."""

    if not isinstance(packet, Mapping):
        raise DispositionError("DISPOSITION_PACKET_INVALID")
    unknown = set(packet) - _PACKET_KEYS
    if unknown:
        raise DispositionError("DISPOSITION_PACKET_UNKNOWN_FIELD", detail=",".join(sorted(unknown)))
    if packet.get("schema", BODY_SCHEMA) != BODY_SCHEMA:
        raise DispositionError("DISPOSITION_SCHEMA_UNSUPPORTED")
    if str(packet.get("schema_version", SCHEMA_VERSION)) not in SUPPORTED_SCHEMA_VERSIONS:
        raise DispositionError("DISPOSITION_SCHEMA_UNSUPPORTED")
    _reject_absolute_paths(packet)
    entry = packet.get("entry", ASSESSMENT)
    if entry not in {ASSESSMENT, WITHDRAWAL}:
        raise DispositionError("DISPOSITION_ENTRY_INVALID")
    subject_in = packet.get("subject")
    if not isinstance(subject_in, Mapping):
        raise DispositionError("DISPOSITION_SUBJECT_REQUIRED")
    subject = {key: subject_in[key] for key in subject_in}
    kind = subject.get("subject_kind")
    if kind not in {QUESTION, BOUNDED_SEARCH}:
        raise DispositionError("DISPOSITION_SUBJECT_KIND_INVALID")
    _require_hex(subject.get("market_evidence_epoch_sha256"), "DISPOSITION_SUBJECT_MARKET_REQUIRED")
    _require_hex(subject.get("journal_scope"), "DISPOSITION_SUBJECT_JOURNAL_REQUIRED")
    if not isinstance(subject.get("owner_focus"), str) or not subject["owner_focus"].strip():
        raise DispositionError("DISPOSITION_SUBJECT_FOCUS_REQUIRED")
    if kind == BOUNDED_SEARCH and isinstance(subject.get("search_scope"), Mapping):
        scope = dict(subject["search_scope"])
        scope["constraints"] = sorted(str(item) for item in scope.get("constraints") or [])
        subject["search_scope"] = scope
    basis_in = packet.get("basis") if isinstance(packet.get("basis"), Mapping) else {}
    basis = dict(basis_in)
    basis.setdefault("result_refs", [])
    basis.setdefault("values_loaded", False)
    basis.setdefault("scientific_look_delta", 0)
    basis.setdefault("saved_results_read", bool(basis.get("result_refs")))
    provenance_in = packet.get("provenance") if isinstance(packet.get("provenance"), Mapping) else {}
    provenance = {
        "mode": provenance_in.get("mode", MODE_NEW),
        "author_role": provenance_in.get("author_role"),
        "model": provenance_in.get("model") or "UNKNOWN",
        "effort": provenance_in.get("effort") or "UNKNOWN",
        "source_episode": provenance_in.get("source_episode"),
        "source_refs": list(provenance_in.get("source_refs") or []),
        "source_sha256": provenance_in.get("source_sha256"),
        "source_encoding": provenance_in.get("source_encoding"),
        "assessed_at": provenance_in.get("assessed_at") or "UNKNOWN",
    }
    extra = set(provenance_in) - set(provenance)
    if extra:
        raise DispositionError("DISPOSITION_PACKET_UNKNOWN_FIELD", detail=",".join(sorted(extra)))
    if provenance["mode"] == MODE_IMPORT and not (
        isinstance(provenance["source_sha256"], str) and _HEX64.fullmatch(provenance["source_sha256"])
    ):
        # The writer records the hash; comparing it to the real source bytes is operator work.
        raise DispositionError("DISPOSITION_IMPORT_SOURCE_SHA_REQUIRED")
    body: dict[str, Any] = {
        "schema": BODY_SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "artifact_kind": ARTIFACT_KIND,
        "entry": entry,
        "subject": subject,
        "subject_key": subject_key(subject),
        "basis": basis,
        "provenance": provenance,
        "supersedes": packet.get("supersedes"),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    if entry == ASSESSMENT:
        judgement_in = packet.get("judgement")
        if not isinstance(judgement_in, Mapping):
            raise DispositionError("DISPOSITION_JUDGEMENT_REQUIRED")
        judgement = dict(judgement_in)
        judgement.setdefault("caveats", [])
        allowed = _ALLOWED_JUDGEMENTS[str(kind)]
        verdict = judgement.get("verdict")
        if verdict not in allowed:
            raise DispositionError(
                "DISPOSITION_VERDICT_NOT_ALLOWED_FOR_SUBJECT", detail="allowed=" + ",".join(sorted(allowed))
            )
        if judgement.get("recommendation") not in allowed[str(verdict)]:
            raise DispositionError(
                "DISPOSITION_RECOMMENDATION_NOT_ALLOWED",
                detail="allowed=" + ",".join(sorted(allowed[str(verdict)])),
            )
        if verdict == NO_WORTHY_SIMPLE_NEXT and (subject.get("search_scope") or {}).get("search_tier") != "SIMPLE_SCREEN":
            # A SIMPLE no-worthy-next never speaks for another tier.
            raise DispositionError(
                "DISPOSITION_SCOPE_TIER_MISMATCH", detail="NO_WORTHY_SIMPLE_NEXT requires search_tier=SIMPLE_SCREEN"
            )
        body["judgement"] = judgement
        if packet.get("withdrawal") is not None:
            raise DispositionError("DISPOSITION_ENTRY_INVALID")
    else:
        withdrawal = packet.get("withdrawal")
        if not isinstance(withdrawal, Mapping) or packet.get("judgement") is not None:
            raise DispositionError("DISPOSITION_WITHDRAWAL_REASON_REQUIRED")
        if not isinstance(packet.get("supersedes"), Mapping):
            raise DispositionError("DISPOSITION_WITHDRAWAL_NEEDS_PREDECESSOR")
        body["withdrawal"] = dict(withdrawal)
    if kind == BOUNDED_SEARCH and entry == ASSESSMENT:
        if not isinstance(basis.get("synthesis_basis"), str) or not basis["synthesis_basis"].strip():
            raise DispositionError("DISPOSITION_SYNTHESIS_BASIS_REQUIRED")
    if entry == ASSESSMENT and kind == QUESTION and len(basis.get("result_refs") or []) != 1:
        raise DispositionError("DISPOSITION_QUESTION_NEEDS_ONE_RESULT")
    if entry == WITHDRAWAL and (basis.get("result_refs") or basis.get("journal_frontier")):
        # A withdrawal cites its predecessor, not new evidence.
        raise DispositionError("DISPOSITION_WITHDRAWAL_TAKES_NO_BASIS")
    return body


def _schema_errors(body: Mapping[str, Any]) -> list[str]:
    errors = sorted(_validator().iter_errors(dict(body)), key=lambda item: list(item.path))
    return ["/".join(str(part) for part in error.path) or "<root>" for error in errors]


def _finalize(body: dict[str, Any], *, recorded_at: datetime, repo_root: Path | None) -> dict[str, Any]:
    body["disposition_sha256"] = _sha(_identity(body))
    body["ingestion"] = {
        "recorded_at": recorded_at.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        "writer_module_sha256": _writer_module_sha256(),
        "writer_git_sha": _writer_git_sha(repo_root),
        "writer": WRITER_NAME,
    }
    errors = _schema_errors(body)
    if errors:
        raise DispositionError("DISPOSITION_SCHEMA_INVALID", detail=";".join(errors[:6]))
    if len(_canonical(body).encode("utf-8")) > MAX_BODY_BYTES:
        raise DispositionError("DISPOSITION_BODY_TOO_LARGE")
    return body


# ---------------------------------------------------------------------------
# One read view per request
# ---------------------------------------------------------------------------


def _unwrap(record: Any) -> tuple[dict[str, Any] | None, str | None]:
    try:
        wrapper = json.loads(record.payload_json)
    except (TypeError, json.JSONDecodeError, AttributeError):
        return None, None
    if not isinstance(wrapper, Mapping):
        return None, None
    kind = wrapper.get("artifact_kind")
    canonical = wrapper.get("payload_canonical")
    try:
        body = json.loads(str(canonical or ""))
    except (TypeError, json.JSONDecodeError):
        return {"__wrapper__": dict(wrapper)}, str(kind) if kind else None
    if not isinstance(body, dict):
        return {"__wrapper__": dict(wrapper)}, str(kind) if kind else None
    body["__payload_sha_ok__"] = (
        hashlib.sha256(str(canonical).encode("utf-8")).hexdigest() == wrapper.get("payload_sha256")
    )
    return body, str(kind) if kind else None


def _parse_disposition(record_id: str, body: Mapping[str, Any]) -> dict[str, Any]:
    """A readable record, or an UNREADABLE marker localized to its subject if possible."""

    scoped_key = body.get("subject_key") if isinstance(body.get("subject_key"), str) else None
    subject = body.get("subject") if isinstance(body.get("subject"), Mapping) else {}

    def _bad(reason: str) -> dict[str, Any]:
        focus = subject.get("owner_focus")
        market = subject.get("market_evidence_epoch_sha256")
        return {
            "record_id": record_id,
            "readable": False,
            "reason": reason,
            "subject_key": scoped_key if scoped_key and _HEX64.fullmatch(scoped_key) else None,
            "owner_focus": focus if isinstance(focus, str) and not host_path_in(focus) else None,
            "market": market if isinstance(market, str) and _HEX64.fullmatch(market) else None,
        }

    if "__wrapper__" in body:
        return _bad("PAYLOAD_UNPARSEABLE")
    if body.get("__payload_sha_ok__") is not True:
        return _bad("PAYLOAD_HASH_MISMATCH")
    clean = {key: value for key, value in body.items() if key != "__payload_sha_ok__"}
    if str(clean.get("schema_version")) not in SUPPORTED_SCHEMA_VERSIONS:
        return _bad("UNSUPPORTED_SCHEMA_VERSION")
    if _schema_errors(clean):
        return _bad("SCHEMA_INVALID")
    if _sha(_identity(clean)) != clean.get("disposition_sha256"):
        return _bad("DISPOSITION_HASH_MISMATCH")
    if record_id_for(str(clean["disposition_sha256"])) != record_id:
        return _bad("RECORD_ID_MISMATCH")
    if subject_key(clean["subject"]) != clean.get("subject_key"):
        return _bad("SUBJECT_KEY_MISMATCH")
    if any(host_path_in(text) for _where, text in _string_leaves(clean)):
        # Restored/foreign history carrying a host path: localized, never displayed.
        return _bad("HOST_PATH_IN_STORED_TEXT")
    return {"record_id": record_id, "readable": True, "body": clean}


class _View:
    """Committed looks, operations and dispositions read in one pass."""

    def __init__(self, store: Any) -> None:
        self.looks_by_journal: dict[str, list[dict[str, Any]]] = {}
        self.operations: dict[str, dict[str, Any]] = {}
        self.dispositions: list[dict[str, Any]] = []
        for record in store.iter_committed_records():
            kind = getattr(record.record_kind, "value", record.record_kind)
            if kind != "RESEARCH_ARTIFACT":
                continue
            body, artifact_kind = _unwrap(record)
            record_id = str(getattr(record, "record_id", "") or "")
            if artifact_kind == ARTIFACT_KIND or record_id.startswith(RECORD_PREFIX + "-"):
                self.dispositions.append(_parse_disposition(record_id, body or {"__wrapper__": {}}))
                continue
            if body is None or "__wrapper__" in body:
                continue
            if artifact_kind == "DISCOVERY_QUERY_LOOK":
                body.pop("__payload_sha_ok__", None)
                body["record_id"] = record_id
                self.looks_by_journal.setdefault(str(body.get("journal_scope") or ""), []).append(body)
            elif artifact_kind == "ORDINARY_OPERATION_V1":
                digest = str(body.get("operation_sha256") or "")
                if digest:
                    # Journal/market/focus are immutable per operation hash.
                    self.operations.setdefault(digest, body)

    def looks(self, journal: str) -> list[dict[str, Any]]:
        return self.looks_by_journal.get(journal, [])

    def find_look(self, journal: str, record_id: str) -> dict[str, Any] | None:
        for item in self.looks(journal):
            if item.get("record_id") == record_id:
                return item
        return None

    def by_subject(self) -> dict[str, list[dict[str, Any]]]:
        grouped: dict[str, list[dict[str, Any]]] = {}
        for item in self.dispositions:
            key = item.get("subject_key") if not item["readable"] else item["body"]["subject_key"]
            if key:
                grouped.setdefault(str(key), []).append(item)
        return grouped


def current_search_key(store: Any, *, market: str | None, owner_focus: str) -> str | None:
    """The ordinary journal preflight would use now for this market and focus."""

    if not market or not _HEX64.fullmatch(market) or owner_focus in {"", "AUTO"}:
        return None
    from solana_alpha_lab.factory.hfic_memory_policy import effective_policy
    from solana_alpha_lab.factory.hfic_session import PROMPT_VERSION, search_key_sha256

    memory = str(effective_policy(store).get("memory_eligibility_sha256") or "")
    return search_key_sha256(market, owner_focus, PROMPT_VERSION, memory or None, None)


def journal_frontier(looks: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Digest of saved attempts and their current evidence in one journal.

    Uses the existing look/revision lineage. Receipts, logs, operations and
    dispositions are not part of it, so an assessment never invalidates itself.
    """

    from solana_alpha_lab.factory.hfic_temporal_discovery import current_look_evidence, look_revision_root

    roots: dict[str, Mapping[str, Any]] = {}
    for item in looks:
        if not isinstance(item.get("result"), Mapping):
            continue
        root = look_revision_root(item)
        if root and root not in roots:
            roots[root] = item
    attempts = []
    for root in sorted(roots):
        base = next((item for item in looks if str(item.get("record_id")) == root), roots[root])
        current = current_look_evidence(base, looks)
        attempts.append(
            {
                "attempt_ref": root,
                "evidence_ref": str(current.get("record_id") or ""),
                "result_sha256": str(current.get("result_sha256") or ""),
                "calculation_version": str(current.get("calculation_version") or ""),
            }
        )
    return {"attempts": attempts, "frontier_sha256": _sha(attempts)}


def frontier_digest(attempts: Sequence[Mapping[str, Any]]) -> str:
    rows = sorted(
        (
            {
                "attempt_ref": str(item.get("attempt_ref") or ""),
                "evidence_ref": str(item.get("evidence_ref") or ""),
                "result_sha256": str(item.get("result_sha256") or ""),
                "calculation_version": str(item.get("calculation_version") or ""),
            }
            for item in attempts
        ),
        key=lambda row: row["attempt_ref"],
    )
    return _sha(rows)


# ---------------------------------------------------------------------------
# Basis validation (writer side)
# ---------------------------------------------------------------------------


def _bind_result(view: _View, subject: Mapping[str, Any], ref: Mapping[str, Any]) -> dict[str, Any]:
    journal = str(subject["journal_scope"])
    look = view.find_look(journal, str(ref.get("result_ref") or ""))
    if look is None:
        raise DispositionError("DISPOSITION_BASIS_RESULT_NOT_FOUND", detail=str(ref.get("result_ref")))
    if look.get("result_sha256") != ref.get("result_sha256") or look.get("calculation_version") != ref.get(
        "calculation_version"
    ):
        raise DispositionError("DISPOSITION_BASIS_RESULT_MISMATCH", detail=str(ref.get("result_ref")))
    operation = view.operations.get(str(look.get("operation_sha256") or ""))
    if operation is None:
        # journal alone cannot prove market or focus; caller strings are not proof.
        raise DispositionError("DISPOSITION_BASIS_MARKET_UNPROVEN", detail=str(ref.get("result_ref")))
    if (
        operation.get("market_evidence_epoch_sha256") != subject.get("market_evidence_epoch_sha256")
        or operation.get("owner_focus") != subject.get("owner_focus")
        or operation.get("journal_scope") != journal
    ):
        raise DispositionError("DISPOSITION_BASIS_SCOPE_MISMATCH", detail=str(ref.get("result_ref")))
    return look


def _science_ready(look: Mapping[str, Any]) -> bool:
    from solana_alpha_lab.factory.hfic_temporal_discovery import temporal_result_coherence

    result = look.get("result") if isinstance(look.get("result"), Mapping) else None
    if result is None or result.get("technical_failure") is True:
        return False
    return temporal_result_coherence(result)["status"] == "COHERENT"


def _is_current_evidence(view: _View, journal: str, look: Mapping[str, Any]) -> bool:
    from solana_alpha_lab.factory.hfic_temporal_discovery import current_look_evidence

    current = current_look_evidence(look, view.looks(journal))
    return str(current.get("record_id") or "") == str(look.get("record_id") or "")


def _validate_basis(view: _View, body: dict[str, Any], *, current_market: str | None) -> None:
    subject = body["subject"]
    basis = body["basis"]
    mode = body["provenance"]["mode"]
    journal = str(subject["journal_scope"])
    if mode == MODE_NEW and current_market and current_market != subject["market_evidence_epoch_sha256"]:
        raise DispositionError("DISPOSITION_MARKET_NOT_CURRENT")
    if basis.get("scientific_look_delta") != 0:
        raise DispositionError("DISPOSITION_LOOK_DELTA_FORBIDDEN")
    if body["entry"] == WITHDRAWAL:
        basis["operation_sha256"] = None
        return
    operations: set[str] = set()
    for ref in basis.get("result_refs") or []:
        look = _bind_result(view, subject, ref)
        operations.add(str(look.get("operation_sha256")))
        if subject["subject_kind"] == QUESTION:
            if look.get("spec_sha256") != subject.get("question_spec_sha256"):
                raise DispositionError("DISPOSITION_BASIS_SPEC_MISMATCH")
            declared_binding = basis.get("data_binding_sha256")
            if declared_binding is not None and declared_binding != look.get("data_binding_sha256"):
                raise DispositionError("DISPOSITION_BASIS_INPUT_BINDING_MISMATCH")
            basis["data_binding_sha256"] = look.get("data_binding_sha256")
        if mode == MODE_NEW and body["entry"] == ASSESSMENT:
            if not _is_current_evidence(view, journal, look):
                raise DispositionError("DISPOSITION_BASIS_NOT_CURRENT", detail=str(look.get("record_id")))
            if not _science_ready(look):
                # A technical or incoherent result is corrected by its numerical owner first.
                raise DispositionError("DISPOSITION_BASIS_NOT_SCIENCE_READY", detail=str(look.get("record_id")))
    declared_operation = basis.get("operation_sha256")
    if subject["subject_kind"] == QUESTION:
        only = next(iter(operations)) if operations else None
        if declared_operation is not None and declared_operation != only:
            raise DispositionError("DISPOSITION_BASIS_OPERATION_MISMATCH")
        basis["operation_sha256"] = only
    elif declared_operation is not None:
        operation = view.operations.get(str(declared_operation))
        if operation is None or operation.get("journal_scope") != journal:
            raise DispositionError("DISPOSITION_BASIS_OPERATION_MISMATCH")
    else:
        basis["operation_sha256"] = None
    if subject["subject_kind"] == BOUNDED_SEARCH:
        declared = basis.get("journal_frontier")
        current = journal_frontier(view.looks(journal))
        if mode == MODE_NEW:
            if isinstance(declared, Mapping) and frontier_digest(declared.get("attempts") or []) != current["frontier_sha256"]:
                raise DispositionError("DISPOSITION_FRONTIER_STALE")
            basis["journal_frontier"] = current
        else:
            if not isinstance(declared, Mapping) or not isinstance(declared.get("attempts"), list):
                raise DispositionError(
                    "DISPOSITION_IMPORT_FRONTIER_REQUIRED",
                    detail="basis.journal_frontier.attempts; current values: disposition-show journal_frontiers",
                )
            attempts = [dict(item) for item in declared["attempts"]]
            from solana_alpha_lab.factory.hfic_temporal_discovery import look_revision_root

            for item in attempts:
                look = view.find_look(journal, str(item.get("evidence_ref") or ""))
                if (
                    look is None
                    or look.get("result_sha256") != item.get("result_sha256")
                    or look.get("calculation_version") != item.get("calculation_version")
                    or look_revision_root(look) != item.get("attempt_ref")
                ):
                    # attempt_ref is the revision root of evidence_ref (the attempt's first look).
                    raise DispositionError("DISPOSITION_FRONTIER_UNRESOLVED", detail=str(item.get("evidence_ref")))
            basis["journal_frontier"] = {
                "attempts": sorted(attempts, key=lambda row: str(row.get("attempt_ref"))),
                "frontier_sha256": frontier_digest(attempts),
            }
    elif "journal_frontier" in basis:
        raise DispositionError("DISPOSITION_PACKET_UNKNOWN_FIELD", detail="basis.journal_frontier")


# ---------------------------------------------------------------------------
# Lineage and applicability (read side; one resolver for every consumer)
# ---------------------------------------------------------------------------


def _lineage(items: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    readable = [item for item in items if item["readable"]]
    unreadable = [item for item in items if not item["readable"]]
    by_id = {item["record_id"]: item for item in readable}
    superseded: set[str] = set()
    broken: list[str] = []
    for item in readable:
        link = item["body"].get("supersedes")
        if not isinstance(link, Mapping):
            continue
        parent = by_id.get(str(link.get("record_id")))
        if parent is None or parent["body"].get("disposition_sha256") != link.get("disposition_sha256"):
            broken.append(item["record_id"])
            continue
        superseded.add(parent["record_id"])
    heads = sorted(item["record_id"] for item in readable if item["record_id"] not in superseded)
    return {
        "readable": readable,
        "unreadable": unreadable,
        "by_id": by_id,
        "heads": heads,
        "broken": sorted(broken),
    }


def _applicability(
    view: _View,
    body: Mapping[str, Any],
    *,
    current_market: str | None,
    current_journal: str | None = None,
) -> tuple[str, list[str]]:
    subject = body["subject"]
    journal = str(subject["journal_scope"])
    reasons: list[str] = []
    for ref in body["basis"].get("result_refs") or []:
        look = view.find_look(journal, str(ref.get("result_ref") or ""))
        if look is None:
            return STATUS_UNREADABLE, [f"BASIS_RESULT_MISSING:{ref.get('result_ref')}"]
        if look.get("result_sha256") != ref.get("result_sha256") or look.get("calculation_version") != ref.get(
            "calculation_version"
        ):
            return STATUS_UNREADABLE, [f"BASIS_RESULT_HASH_MISMATCH:{ref.get('result_ref')}"]
    if current_market and subject["market_evidence_epoch_sha256"] != current_market:
        return STATUS_HISTORICAL, ["MARKET_CHANGED"]
    if not current_market:
        # UNKNOWN market is never read as a current basis.
        return STATUS_REVIEW, ["MARKET_UNVERIFIED"]
    if subject["subject_kind"] == QUESTION:
        ref = body["basis"]["result_refs"][0]
        look = view.find_look(journal, str(ref["result_ref"]))
        assert look is not None
        if not _is_current_evidence(view, journal, look):
            return STATUS_REVIEW, [f"BASIS_RESULT_REVISED:{ref['result_ref']}"]
        if not _science_ready(look):
            return STATUS_HISTORICAL, [f"BASIS_NOT_SCIENCE_READY:{ref['result_ref']}"]
    else:
        if not current_journal:
            # UNKNOWN current journal is never read as the judged one.
            return STATUS_REVIEW, ["JOURNAL_UNVERIFIED"]
        if current_journal != journal:
            # Same market, rotated search key (memory policy or prompt version):
            # the judged frontier is no longer the journal new attempts land in.
            return STATUS_REVIEW, ["JOURNAL_CHANGED"]
        recorded = (body["basis"].get("journal_frontier") or {}).get("frontier_sha256")
        current = journal_frontier(view.looks(journal))
        if current["frontier_sha256"] != recorded:
            known = {
                str(item.get("attempt_ref"))
                for item in (body["basis"].get("journal_frontier") or {}).get("attempts") or []
            }
            new_attempts = sum(1 for item in current["attempts"] if item["attempt_ref"] not in known)
            reasons.append("FRONTIER_CHANGED")
            if new_attempts:
                reasons.append(f"NEW_ATTEMPTS:{new_attempts}")
            return STATUS_REVIEW, reasons
    return STATUS_CURRENT, reasons


def resolve_subject(
    view: _View,
    items: Sequence[Mapping[str, Any]],
    *,
    current_market: str | None,
    current_journal: str | None = None,
) -> dict[str, Any]:
    lineage = _lineage(items)
    readable = lineage["readable"]
    any_body = readable[0]["body"] if readable else None
    entry: dict[str, Any] = {
        "subject_key": (any_body or {}).get("subject_key") or next(
            (item.get("subject_key") for item in lineage["unreadable"] if item.get("subject_key")), None
        ),
        "record_count": len(items),
        "lineage_heads": lineage["heads"],
    }
    if any_body is not None:
        entry["subject"] = dict(any_body["subject"])
    if lineage["unreadable"] or lineage["broken"]:
        reasons = [f"{item['reason']}:{item['record_id']}" for item in lineage["unreadable"]]
        reasons += [f"PREDECESSOR_UNRESOLVED:{ref}" for ref in lineage["broken"]]
        entry.update(
            {"status": STATUS_UNREADABLE, "reasons": reasons, "head_ref": None, "recommendation_active": False}
        )
        return entry
    if len(lineage["heads"]) != 1:
        entry.update(
            {"status": STATUS_CONFLICT, "reasons": ["LINEAGE_FORK"], "head_ref": None, "recommendation_active": False}
        )
        return entry
    head = lineage["by_id"][lineage["heads"][0]]["body"]
    entry["head_ref"] = lineage["heads"][0]
    entry["head_disposition_sha256"] = head["disposition_sha256"]
    entry["provenance_mode"] = head["provenance"]["mode"]
    entry["history_refs"] = sorted(item["record_id"] for item in readable if item["record_id"] != entry["head_ref"])
    if head["entry"] == WITHDRAWAL:
        entry.update(
            {
                "status": STATUS_WITHDRAWN,
                "reasons": ["EXPLICIT_WITHDRAWAL"],
                "recommendation_active": False,
                "withdrawal_reason": head["withdrawal"]["reason"],
            }
        )
        return entry
    status, reasons = _applicability(view, head, current_market=current_market, current_journal=current_journal)
    entry.update(
        {
            "status": status,
            "reasons": reasons,
            "verdict": head["judgement"]["verdict"],
            "recommendation": head["judgement"]["recommendation"],
            "recommendation_active": status == STATUS_CURRENT,
            "caveats": list(head["judgement"].get("caveats") or []),
            "result_refs": [item["result_ref"] for item in head["basis"].get("result_refs") or []],
        }
    )
    return entry


def _scope_match(subject: Mapping[str, Any] | None, current_market: str | None) -> str:
    if not subject:
        return "UNKNOWN"
    if not current_market:
        return "FOCUS_ONLY_MARKET_UNVERIFIED"
    return "EXACT" if subject.get("market_evidence_epoch_sha256") == current_market else "RELATED_OTHER_MARKET"


def resolve_focus(
    store: Any,
    *,
    owner_focus: str,
    current_market: str | None = None,
    journal_scope: str | None = None,
    view: _View | None = None,
) -> dict[str, Any]:
    """Full resolved state for one owner focus. Exact focus match only; no fuzzy family."""

    view = view or _View(store)
    entries: list[dict[str, Any]] = []
    unscoped = 0
    for key, items in sorted(view.by_subject().items()):
        focus = next(
            (
                item["body"]["subject"]["owner_focus"] if item["readable"] else item.get("owner_focus")
                for item in items
                if (item["readable"] or item.get("owner_focus"))
            ),
            None,
        )
        if focus != owner_focus:
            continue
        entry = resolve_subject(view, items, current_market=current_market, current_journal=journal_scope)
        entry["scope_match"] = _scope_match(entry.get("subject"), current_market)
        if entry["scope_match"] == "RELATED_OTHER_MARKET" and entry["status"] not in {
            STATUS_CONFLICT,
            STATUS_UNREADABLE,
            STATUS_WITHDRAWN,
        }:
            entry["status"] = STATUS_HISTORICAL
            entry["recommendation_active"] = False
            entry["reasons"] = ["MARKET_CHANGED"]
        entries.append(entry)
    for item in view.dispositions:
        if not item["readable"] and not item.get("subject_key"):
            unscoped += 1
    in_scope = {"EXACT", "FOCUS_ONLY_MARKET_UNVERIFIED"}
    # Journals this focus actually works in: ordinary operations on the current
    # market (or any market when unverified) plus recorded in-scope subjects.
    journals = {journal_scope} if journal_scope else set()
    journals |= {
        str(operation.get("journal_scope") or "")
        for operation in view.operations.values()
        if operation.get("owner_focus") == owner_focus
        and (not current_market or operation.get("market_evidence_epoch_sha256") == current_market)
    }
    journals |= {
        str(entry["subject"]["journal_scope"])
        for entry in entries
        if entry.get("subject") and entry.get("scope_match") in in_scope
    }
    # A question counts as having a subject only in its own journal and in scope.
    # A withdrawn subject is shown as WITHDRAWN (with how to re-assess), not twice.
    assessed = {
        (str(entry["subject"]["journal_scope"]), str(entry["subject"].get("question_spec_sha256")))
        for entry in entries
        if entry.get("subject")
        and entry["subject"].get("subject_kind") == QUESTION
        and entry.get("scope_match") in in_scope
    }
    not_recorded: list[dict[str, Any]] = []
    for journal in sorted(item for item in journals if item):
        frontier = journal_frontier(view.looks(journal))
        for attempt in frontier["attempts"]:
            look = view.find_look(journal, attempt["evidence_ref"]) or {}
            spec = str(look.get("spec_sha256") or "")
            if spec and (journal, spec) not in assessed:
                operation = view.operations.get(str(look.get("operation_sha256") or "")) or {}
                not_recorded.append(
                    {
                        "status": STATUS_NOT_RECORDED,
                        "subject_kind": QUESTION,
                        "market_evidence_epoch_sha256": operation.get("market_evidence_epoch_sha256"),
                        "journal_scope": journal,
                        "question_spec_sha256": spec,
                        "question_text": operation.get("question_text"),
                        "result_ref": attempt["evidence_ref"],
                        "result_sha256": attempt["result_sha256"],
                        "calculation_version": attempt["calculation_version"],
                        "note": "calculation saved; no authored assessment recorded",
                    }
                )
                assessed.add((journal, spec))
    entries.sort(
        key=lambda item: (
            0 if item.get("scope_match") in {"EXACT", "FOCUS_ONLY_MARKET_UNVERIFIED"} else 1,
            _STATUS_ORDER.get(str(item.get("status")), 9),
            0 if (item.get("subject") or {}).get("subject_kind") == BOUNDED_SEARCH else 1,
            str(item.get("subject_key")),
        )
    )
    assessed_tiers = sorted(
        {
            str((entry["subject"].get("search_scope") or {}).get("search_tier"))
            for entry in entries
            if entry.get("subject")
            and entry["subject"].get("subject_kind") == BOUNDED_SEARCH
            and entry.get("scope_match") in in_scope
            and entry.get("status") not in {STATUS_WITHDRAWN}
        }
    )
    return {
        "owner_focus": owner_focus,
        "current_market_evidence_epoch_sha256": current_market,
        "current_journal_scope": journal_scope,
        "assessed_search_tiers": assessed_tiers,
        "journals": sorted(item for item in journals if item),
        "entries": entries,
        "not_recorded": not_recorded,
        "unreadable_unscoped_records": unscoped,
    }


def _compact_entry(entry: Mapping[str, Any]) -> dict[str, Any]:
    subject = entry.get("subject") or {}
    compact: dict[str, Any] = {
        "ref": entry.get("head_ref"),
        "ref_sha256": entry.get("head_disposition_sha256"),
        "subject_key": entry.get("subject_key"),
        "kind": subject.get("subject_kind"),
        "status": entry.get("status"),
        "scope_match": entry.get("scope_match"),
    }
    if subject.get("subject_kind") == BOUNDED_SEARCH:
        scope = subject.get("search_scope") or {}
        compact["scope"] = {"search_tier": scope.get("search_tier"), "population": scope.get("population"), "window": scope.get("window")}
    elif subject.get("subject_kind") == QUESTION:
        compact["scope"] = {"question_spec_sha256": subject.get("question_spec_sha256")}
        if subject.get("question_text"):
            compact["question"] = str(subject["question_text"])[:80]
    for key in ("verdict", "recommendation", "recommendation_active"):
        if key in entry:
            compact[key] = entry[key]
    if entry.get("result_refs"):
        compact["result_refs"] = list(entry["result_refs"])[:4]
    caveats = [str(item)[:120] for item in entry.get("caveats") or []][:2]
    if caveats:
        compact["caveats"] = caveats
    if entry.get("reasons"):
        compact["reasons"] = [str(item)[:96] for item in entry["reasons"]][:3]
    if entry.get("withdrawal_reason"):
        compact["withdrawal_reason"] = str(entry["withdrawal_reason"])[:120]
    if entry.get("status") == STATUS_CONFLICT:
        compact["heads"] = list(entry.get("lineage_heads") or [])[:4]
    if entry.get("status") in {STATUS_CONFLICT, STATUS_UNREADABLE}:
        compact["owner_action"] = "STOP_OWNER_RESOLUTION"
    return compact


def detail_query(
    owner_focus: str,
    *,
    subject_key_value: str | None = None,
    offset: int | None = None,
    journal_scope: str | None = None,
) -> str:
    import shlex

    command = (
        "uv run --locked --managed-python python -B scripts/hypothesis_forge.py disposition-show "
        f"--owner-focus {shlex.quote(owner_focus)} --format json"
    )
    if journal_scope:
        command += f" --journal-scope {journal_scope}"
    if subject_key_value:
        command += f" --subject-key {subject_key_value}"
    if offset:
        command += f" --offset {offset}"
    return command


def disposition_context(
    store: Any,
    *,
    owner_focus: str,
    current_market: str | None = None,
    journal_scope: str | None = None,
    max_bytes: int = COMPACT_CONTEXT_MAX_BYTES,
) -> dict[str, Any]:
    """Compact advisory capsule for readback and pre-values synthesis (<= max_bytes).

    Counts are computed before display truncation, so omitted entries are
    reported, never silently dropped.
    """

    resolved = resolve_focus(
        store, owner_focus=owner_focus, current_market=current_market, journal_scope=journal_scope
    )
    entries = resolved["entries"]
    counts: dict[str, int] = {}
    for entry in entries:
        counts[str(entry["status"])] = counts.get(str(entry["status"]), 0) + 1
    if resolved["not_recorded"]:
        counts[STATUS_NOT_RECORDED] = len(resolved["not_recorded"])
    capsule: dict[str, Any] = {
        "schema": CONTEXT_SCHEMA,
        "schema_version": "1.0",
        "owner_focus": owner_focus,
        "focus_resolved": owner_focus not in {"", "AUTO"},
        "market_verified": bool(current_market),
        "journal_verified": bool(journal_scope),
        "assessed_search_tiers": resolved["assessed_search_tiers"],
        "advisory_only": True,
        "authority_granted": False,
        "machine_next_action_owner": "ORDINARY_RESOLVER",
        "claim_boundary": "authored advice on named scopes; not a look, budget, admission or family close",
        "total_subjects": len(entries),
        "status_counts": dict(sorted(counts.items())),
        "unreadable_unscoped_records": resolved["unreadable_unscoped_records"],
        "entries": [],
        "not_recorded": [],
        "shown": 0,
        "omitted": 0,
        "detail_query": detail_query(owner_focus, journal_scope=journal_scope),
    }

    def _size() -> int:
        return len(_canonical(capsule).encode("utf-8"))

    for entry in entries:
        capsule["entries"].append(_compact_entry(entry))
        capsule["shown"] = len(capsule["entries"])
        capsule["omitted"] = len(entries) - capsule["shown"]
        if _size() > max_bytes:
            capsule["entries"].pop()
            capsule["shown"] = len(capsule["entries"])
            capsule["omitted"] = len(entries) - capsule["shown"]
            break
    for item in resolved["not_recorded"]:
        capsule["not_recorded"].append(
            {
                "result_ref": item["result_ref"],
                "result_sha256": item["result_sha256"],
                "calculation_version": item["calculation_version"],
                "question_spec_sha256": item["question_spec_sha256"],
            }
        )
        if _size() > max_bytes:
            capsule["not_recorded"].pop()
            break
    capsule["not_recorded_omitted"] = len(resolved["not_recorded"]) - len(capsule["not_recorded"])
    if _size() > max_bytes:
        # Even the header cannot carry entries: keep counts and the detail query only.
        capsule["entries"] = []
        capsule["not_recorded"] = []
        capsule["shown"] = 0
        capsule["omitted"] = len(entries)
        capsule["not_recorded_omitted"] = len(resolved["not_recorded"])
    return capsule


def disposition_detail(
    store: Any,
    *,
    owner_focus: str,
    current_market: str | None = None,
    subject_key_value: str | None = None,
    record_id: str | None = None,
    offset: int = 0,
    limit: int = 20,
    journal_scope: str | None = None,
) -> dict[str, Any]:
    """Exact-ref detail: full bodies and lineage. Reads no market outcome rows."""

    view = _View(store)
    if record_id:
        found = next((item for item in view.dispositions if item["record_id"] == record_id), None)
        if found is None:
            raise DispositionError("DISPOSITION_RECORD_NOT_FOUND")
        key = found["body"]["subject_key"] if found["readable"] else found.get("subject_key")
        subject_key_value = str(key) if key else None
        if subject_key_value is None:
            return {"records": [found], "entries": [], "total_subjects": 0}
        owner_focus = (
            found["body"]["subject"]["owner_focus"] if found["readable"] else str(found.get("owner_focus") or owner_focus)
        )
    resolved = resolve_focus(
        store, owner_focus=owner_focus, current_market=current_market, journal_scope=journal_scope, view=view
    )
    entries = resolved["entries"]
    if subject_key_value:
        entries = [item for item in entries if item.get("subject_key") == subject_key_value]
    page = entries[offset : offset + max(1, limit)]
    grouped = view.by_subject()
    records = []
    for entry in page:
        for item in grouped.get(str(entry.get("subject_key")), []):
            records.append(item if not item["readable"] else {"record_id": item["record_id"], "readable": True, "body": item["body"]})
    return {
        "schema": "smial.hfic-scientific-disposition-detail",
        "schema_version": "1.0",
        "owner_focus": owner_focus,
        "advisory_only": True,
        "authority_granted": False,
        "journals": resolved["journals"],
        "current_journal_scope": journal_scope,
        # Current frontier per journal: the values a bounded-search import declares.
        "journal_frontiers": {journal: journal_frontier(view.looks(journal)) for journal in resolved["journals"]},
        "total_subjects": len(entries),
        "offset": offset,
        "limit": limit,
        "next_offset": offset + len(page) if offset + len(page) < len(entries) else None,
        "entries": page,
        "records": records,
        "not_recorded": resolved["not_recorded"] if not subject_key_value else [],
        "unreadable_unscoped_records": resolved["unreadable_unscoped_records"],
    }


# ---------------------------------------------------------------------------
# Writer: explicit bounded packet -> one append (idempotent, CAS on the head)
# ---------------------------------------------------------------------------


def _check_lineage(store: Any, body: Mapping[str, Any]) -> None:
    view = _View(store)
    if any(item["record_id"] == record_id_for(str(body["disposition_sha256"])) for item in view.dispositions):
        raise _AlreadyCommitted()
    items = view.by_subject().get(str(body["subject_key"]), [])
    lineage = _lineage(items)

    def _refuse(code: str) -> DispositionError:
        # Name the actual head(s) with the hash a successor must cite.
        heads = [
            f"{ref}:{lineage['by_id'][ref]['body']['disposition_sha256']}"
            for ref in lineage["heads"]
            if ref in lineage["by_id"]
        ]
        return DispositionError(code, head_refs=lineage["heads"], detail=";".join(heads) or None)

    if lineage["unreadable"] or lineage["broken"]:
        # Restored/corrupt history is not repaired by another append: owner resolution.
        raise _refuse("DISPOSITION_SUBJECT_UNREADABLE")
    link = body.get("supersedes")
    if link is None:
        if lineage["heads"]:
            raise _refuse("DISPOSITION_SUBJECT_HAS_HEAD")
        return
    parent = lineage["by_id"].get(str(link.get("record_id")))
    if parent is None or parent["body"]["disposition_sha256"] != link.get("disposition_sha256"):
        raise _refuse("DISPOSITION_PREDECESSOR_NOT_FOUND")
    if len(lineage["heads"]) > 1:
        raise _refuse("DISPOSITION_SUBJECT_CONFLICT")
    if lineage["heads"] != [parent["record_id"]]:
        raise _refuse("DISPOSITION_STALE_PARENT")
    if body["entry"] == WITHDRAWAL and parent["body"]["entry"] == WITHDRAWAL:
        raise _refuse("DISPOSITION_ALREADY_WITHDRAWN")


def _existing(store: Any, disposition_sha256: str) -> dict[str, Any] | None:
    wanted = record_id_for(disposition_sha256)
    for item in _View(store).dispositions:
        if item["record_id"] == wanted and item["readable"]:
            return item["body"]
    return None


def _event(body: Mapping[str, Any], *, now: datetime) -> Any:
    from solana_alpha_lab.factory.research_store import RecordKind, ResearchEvent

    canonical = _canonical(dict(body))
    payload = {
        "artifact_kind": ARTIFACT_KIND,
        "payload_canonical": canonical,
        "payload_sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
    }
    payload_json = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    digest = str(body["disposition_sha256"])
    record_id = record_id_for(digest)
    link = body.get("supersedes")
    git_sha = body["ingestion"].get("writer_git_sha") or "0" * 40
    return ResearchEvent(
        record_id=record_id,
        record_kind=RecordKind.RESEARCH_ARTIFACT,
        entity_id=record_id,
        hypothesis_version_id=None,
        run_id=None,
        # Idempotency lives on record_id; the transaction is per attempt so an
        # orphan partition from a crash before manifest commit never blocks a retry.
        transaction_id=f"RESEARCH-TXN-DISP-{digest[:24].upper()}-{now.astimezone(timezone.utc):%Y%m%dT%H%M%S%f}",
        effective_at=now,
        first_reliable_available_at=now,
        supersedes_record_id=str(link["record_id"]) if isinstance(link, Mapping) else None,
        payload_json=payload_json,
        payload_sha256=hashlib.sha256(payload_json.encode("utf-8")).hexdigest(),
        schema_version=SCHEMA_VERSION,
        producer_capability_id=CAPABILITY_ID,
        producer_git_sha=git_sha,
        created_at=now,
    )


def _result(
    store: Any,
    body: Mapping[str, Any],
    disposition: str,
    *,
    current_market: str | None = None,
    current_journal: str | None = None,
) -> dict[str, Any]:
    view = _View(store)
    items = view.by_subject().get(str(body["subject_key"]), [])
    resolved = resolve_subject(view, items, current_market=current_market, current_journal=current_journal)
    return {
        "schema": "smial.hfic-scientific-disposition-write",
        "schema_version": "1.0",
        "disposition": disposition,
        "record_id": record_id_for(str(body["disposition_sha256"])),
        "disposition_sha256": body["disposition_sha256"],
        "subject_key": body["subject_key"],
        "subject_kind": body["subject"]["subject_kind"],
        "entry": body["entry"],
        "ingestion": dict(body["ingestion"]),
        "readback": {key: resolved.get(key) for key in ("status", "reasons", "head_ref", "lineage_heads")},
        "writes": {"research_store": 1 if disposition == "CREATED" else 0},
        "scientific_delta": {"looks": 0, "reservations": 0, "operations": 0, "sessions": 0, "candidates": 0},
        "advisory_only": True,
        "authority_granted": False,
    }


def prepare_disposition(
    store: Any,
    packet: Mapping[str, Any],
    *,
    current_market: str | None = None,
    repo_root: Path | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Validated immutable body for a packet. Reads the store; never writes."""

    body = normalize_packet(packet)
    view = _View(store)
    _validate_basis(view, body, current_market=current_market)
    return _finalize(body, recorded_at=now or datetime.now(timezone.utc), repo_root=repo_root)


def preview_disposition(
    store: Any,
    packet: Mapping[str, Any],
    *,
    current_market: str | None = None,
    current_journal: str | None = None,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    """Exact append plan without appending: record, lineage link and expected deltas."""

    body = prepare_disposition(store, packet, current_market=current_market, repo_root=repo_root)
    existing = _existing(store, str(body["disposition_sha256"]))
    lineage_refusal = None
    if existing is None:
        try:
            _check_lineage(store, body)
        except DispositionError as exc:
            lineage_refusal = {"code": exc.code, "head_refs": exc.head_refs, "detail": exc.detail}
        except _AlreadyCommitted:
            existing = _existing(store, str(body["disposition_sha256"]))
    would_be: dict[str, Any] = {"status": None, "reasons": []}
    if body["entry"] == ASSESSMENT:
        status, reasons = _applicability(
            _View(store), body, current_market=current_market, current_journal=current_journal
        )
        would_be = {"status": status, "reasons": reasons}
    elif body["entry"] == WITHDRAWAL:
        would_be = {"status": STATUS_WITHDRAWN, "reasons": ["EXPLICIT_WITHDRAWAL"]}
    return {
        "schema": "smial.hfic-scientific-disposition-preview",
        "would_be_applicability": would_be,
        "schema_version": "1.0",
        "would_append": existing is None and lineage_refusal is None,
        "replay_existing": existing is not None,
        "lineage_refusal": lineage_refusal,
        "record_id": record_id_for(str(body["disposition_sha256"])),
        "record_kind": "RESEARCH_ARTIFACT",
        "artifact_kind": ARTIFACT_KIND,
        "disposition_sha256": body["disposition_sha256"],
        "subject_key": body["subject_key"],
        "supersedes": body.get("supersedes"),
        "expected_inventory_delta_records": 0 if existing is not None else 1,
        "scientific_delta": {"looks": 0, "reservations": 0, "operations": 0, "sessions": 0, "candidates": 0},
        "body": existing or body,
        "writes": {"research_store": 0},
    }


def record_disposition(
    store: Any,
    packet: Mapping[str, Any],
    *,
    current_market: str | None = None,
    repo_root: Path | None = None,
    now: datetime | None = None,
    before_append: Callable[[], None] | None = None,
    current_journal: str | None = None,
) -> dict[str, Any]:
    """Append one assessment or withdrawal. An exact repeat returns the saved record.

    The head check runs inside the store writer lease, so a successor with a
    stale parent is refused with the actual head ref instead of forking.
    """

    from solana_alpha_lab.factory.research_store import ResearchStoreError

    moment = now or datetime.now(timezone.utc)
    body = prepare_disposition(store, packet, current_market=current_market, repo_root=repo_root, now=moment)
    saved = _existing(store, str(body["disposition_sha256"]))
    if saved is not None:
        return _result(store, saved, "REPLAY_EXISTING", current_market=current_market, current_journal=current_journal)
    event = _event(body, now=moment)

    def _check() -> None:
        if before_append is not None:
            before_append()
        _check_lineage(store, body)

    for attempt in range(40):
        try:
            store.append([event], transaction_id=event.transaction_id, before_commit=_check)
            return _result(store, body, "CREATED", current_market=current_market, current_journal=current_journal)
        except _AlreadyCommitted:
            break
        except ResearchStoreError as exc:
            if exc.code == "DUPLICATE_RECORD_ID":
                break
            if exc.code != "WRITER_BUSY" or attempt >= 39:
                raise
            time.sleep(0.05)
    saved = _existing(store, str(body["disposition_sha256"]))
    if saved is None:
        raise DispositionError("DISPOSITION_WRITE_NOT_VISIBLE")
    return _result(store, saved, "REPLAY_EXISTING", current_market=current_market, current_journal=current_journal)


# ---------------------------------------------------------------------------
# Owner-facing lines for ordinary readback
# ---------------------------------------------------------------------------


def format_context_lines(capsule: Mapping[str, Any] | None) -> list[str]:
    """Scientific context, visibly separate from the machine next_action."""

    if not isinstance(capsule, Mapping):
        return []
    if capsule.get("status") == "UNAVAILABLE":
        return [
            "scientific_context: UNAVAILABLE "
            f"({capsule.get('reason_code') or 'UNKNOWN'}) — recorded assessments could not be read; "
            "numerical results and next_action are unaffected",
            f"  detail: {capsule.get('detail_query')}",
        ]
    lines = ["scientific_context (advisory; not next_action, not authority):"]
    if capsule.get("focus_resolved") is False:
        lines.append(
            f"  focus {capsule.get('owner_focus') or 'AUTO'} is not a named focus; "
            "assessments are recorded per focus — pass --owner-focus <FOCUS> to see them"
        )
    if not capsule.get("market_verified"):
        lines.append("  market UNVERIFIED — no assessment is shown as current")
    elif not capsule.get("journal_verified"):
        lines.append("  current journal UNVERIFIED — no search-scope assessment is shown as current")
    entries = capsule.get("entries") or []
    if (
        not capsule.get("total_subjects")
        and not capsule.get("not_recorded")
        and not capsule.get("not_recorded_omitted")
        and capsule.get("focus_resolved") is not False
    ):
        lines.append("  none recorded for this focus")
    for entry in entries:
        scope = entry.get("scope") or {}
        if entry.get("kind") == BOUNDED_SEARCH:
            scope_text = f"tier={scope.get('search_tier')}"
        else:
            question = entry.get("question") or f"spec {str(scope.get('question_spec_sha256') or '')[:12]}"
            scope_text = f'question="{question}" result={",".join(entry.get("result_refs") or []) or "NONE"}'
        lines.append(
            "  {status} {kind} {scope} verdict={verdict} advice={advice}{active} ref={ref}".format(
                status=entry.get("status"),
                kind=entry.get("kind") or "UNKNOWN",
                scope=scope_text,
                verdict=entry.get("verdict") or "NONE",
                advice=entry.get("recommendation") or "NONE",
                active="" if entry.get("recommendation_active") else " (inactive)",
                ref=entry.get("ref") or "NONE",
            )
        )
        if entry.get("reasons"):
            lines.append("    reasons: " + ", ".join(str(item) for item in entry["reasons"]))
        if entry.get("withdrawal_reason"):
            lines.append(f"    withdrawn because: {entry['withdrawal_reason']}")
        status = entry.get("status")
        supersede = f"supersedes={{record_id: {entry.get('ref')}, disposition_sha256: {entry.get('ref_sha256')}}}"
        if status in {STATUS_REVIEW, STATUS_HISTORICAL}:
            lines.append(
                f"    advice_next: re-assess on the current basis with disposition-record and {supersede}, "
                "or leave as history"
            )
        elif status == STATUS_WITHDRAWN:
            lines.append(f"    advice_next: none required; a new assessment uses disposition-record with {supersede}")
        elif status == STATUS_CONFLICT:
            lines.append("    heads: " + ", ".join(str(item) for item in entry.get("heads") or []))
            lines.append(
                "    advice_next: STOP for this subject — owner resolution needed; writes to it are refused "
                "(see docs/contracts/hfic_scientific_disposition_continuity_v1.md)"
            )
        elif status == STATUS_UNREADABLE:
            lines.append(
                "    advice_next: STOP for this subject — owner resolution needed; writes to it are refused "
                "(see docs/contracts/hfic_scientific_disposition_continuity_v1.md)"
            )
    for item in capsule.get("not_recorded") or []:
        lines.append(
            f"  NOT_RECORDED QUESTION result={item.get('result_ref')} sha256={item.get('result_sha256')} "
            f"calc={item.get('calculation_version')} — calculation saved, assessment missing; "
            "write it with disposition-record"
        )
    if capsule.get("omitted") or capsule.get("not_recorded_omitted"):
        lines.append(
            f"  omitted: {capsule.get('omitted', 0)} subjects, {capsule.get('not_recorded_omitted', 0)} unassessed results"
        )
    if capsule.get("unreadable_unscoped_records"):
        lines.append(
            f"  unreadable records without a subject: {capsule['unreadable_unscoped_records']} (counted, not shown)"
        )
    lines.append(f"  detail: {capsule.get('detail_query')}")
    untested = sorted({"SIMPLE_SCREEN", "COMPOUND_SCREEN"} - set(capsule.get("assessed_search_tiers") or []))
    lines.append(
        "  note: advice does not open, close or budget a look"
        + (f"; search tiers without a recorded assessment: {', '.join(untested)}" if untested else "")
    )
    return lines


def _leaks(capsule: Mapping[str, Any], forbidden_texts: Sequence[str]) -> bool:
    # Raw string leaves, as the CLI guard walks them; never the JSON-escaped text.
    needles = [item for item in forbidden_texts if item]
    return any(
        host_path_in(text) or any(needle in text for needle in needles)
        for _where, text in _string_leaves(capsule)
    )


def safe_disposition_context(
    store: Any,
    *,
    owner_focus: str,
    current_market: str | None,
    journal_scope: str | None = None,
    forbidden_texts: Sequence[str] = (),
    max_bytes: int = COMPACT_CONTEXT_MAX_BYTES,
) -> dict[str, Any]:
    """Consumer wrapper: a disposition read failure never blocks Forge input or readback.

    The capsule is also checked for host paths here, inside the boundary, so
    stored advice text can never trip the caller's physical-path leak guard.
    """

    def _unavailable(code: str, detail: str | None = None) -> dict[str, Any]:
        body = {
            "schema": CONTEXT_SCHEMA,
            "schema_version": "1.0",
            "status": "UNAVAILABLE",
            "reason_code": code,
            "owner_focus": owner_focus,
            "advisory_only": True,
            "authority_granted": False,
            "detail_query": detail_query(owner_focus, journal_scope=journal_scope),
        }
        if detail:
            body["error_class"] = detail
        return body

    try:
        capsule = disposition_context(
            store,
            owner_focus=owner_focus,
            current_market=current_market,
            journal_scope=journal_scope,
            max_bytes=max_bytes,
        )
    except Exception as exc:  # noqa: BLE001 - isolation boundary, typed code only
        code = getattr(exc, "code", None)
        return _unavailable(str(code) if code else "DISPOSITION_CONTEXT_READ_FAILED", None if code else type(exc).__name__)
    if _leaks(capsule, forbidden_texts):
        return _unavailable("DISPOSITION_CONTEXT_PATH_LEAK")
    return capsule


def compact_counts_only(capsule: Mapping[str, Any]) -> dict[str, Any]:
    """Smallest honest capsule: counts and the detail query, no entries."""

    reduced = {key: value for key, value in capsule.items() if key not in {"entries", "not_recorded"}}
    reduced["entries"] = []
    reduced["not_recorded"] = []
    reduced["shown"] = 0
    reduced["omitted"] = int(capsule.get("total_subjects") or 0)
    reduced["not_recorded_omitted"] = int(
        len(capsule.get("not_recorded") or []) + int(capsule.get("not_recorded_omitted") or 0)
    )
    reduced["reduced_for_packet_budget"] = True
    return reduced
