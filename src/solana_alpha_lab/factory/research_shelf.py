"""Research Shelf wire/lineage and attention. No native execution or Git transport."""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import re
from collections import Counter, defaultdict
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path, PurePosixPath
from typing import Any, Mapping
from uuid import uuid4

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[3]
PREFIX = "capsules/research_shelf_v1"
MAX_REVISION_BYTES = 65_536
MAX_BATCH_BYTES = 1_048_576
IDENTITY = ("item_id", "product", "origin_key", "created_at")


class ShelfError(ValueError):
    """Safe code and field locator only; never echo an untrusted payload."""

    def __init__(self, code: str, field: str = ""):
        self.code, self.field = code, field
        super().__init__(code + (":" + field if field else ""))


def require(condition: Any, code: str, field: str = "") -> None:
    if not condition:
        raise ShelfError(code, field)


def canonical(body: Any) -> bytes:
    try:
        return json.dumps(body, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise ShelfError("WIRE_JSON_INVALID") from None


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def clock(value: str) -> datetime:
    try:
        require(isinstance(value, str) and value.endswith("Z"), "UTC_CLOCK_REQUIRED")
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        require(result.tzinfo == UTC, "UTC_CLOCK_REQUIRED")
        return result
    except (ValueError, TypeError):
        raise ShelfError("UTC_CLOCK_INVALID") from None


def relative_path(value: str) -> bool:
    parts = value.split("/")
    return bool(value) and not any(c in value for c in "\\:\x00\r\n\t") and all(
        p and p not in {".", ".."} and not p.endswith((".", " ")) for p in parts)


@lru_cache(maxsize=1)
def _validator() -> Draft202012Validator:
    schema = json.loads((ROOT / "catalog/schemas/research_shelf_v1.schema.json").read_bytes())
    Draft202012Validator.check_schema(schema)
    # Calendar validation below is mandatory, independent of optional extras.
    return Draft202012Validator(schema)


@lru_cache(maxsize=1)
def _scanner():
    spec = importlib.util.spec_from_file_location("shelf_secret_scan", ROOT / "scripts/secret_scan.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.findings_for_text


def _guard(value: Any, location: str = "") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if key in {"created_at", "updated_at", "review_at", "review_by", "at", "observed_at"} and child is not None:
                clock(child)
            if key == "path":
                require(isinstance(child, str) and relative_path(child), "LOGICAL_PATH_REQUIRED", location + ".path")
            _guard(child, location + "." + key)
    elif isinstance(value, list):
        for i, child in enumerate(value):
            _guard(child, f"{location}[{i}]")
    elif isinstance(value, str):
        require(not re.search(r"(?i)(?:(?<![a-z0-9+.-])[a-z]:[\\/]|\\\\|file://|(?<![a-z0-9:/._-])/(?:home|Users|tmp|mnt|var)/)", value),
                "PHYSICAL_PATH_REFUSED", location)
        require(not _scanner()(value), "SECRET_REFUSED", location)


def validate(body: Mapping[str, Any]) -> None:
    require(isinstance(body, dict), "ITEM_INVALID")
    require(body.get("schema_version") == "1.0", "UNSUPPORTED_WIRE_VERSION", "schema_version")
    error = next(_validator().iter_errors(body), None)
    if error:
        # Schema paths, unlike incoming object keys or error.message, contain no values.
        raise ShelfError("WIRE_SCHEMA_INVALID", "/".join(str(p) for p in error.schema_path))
    require(body["item_id"].startswith("RSI-" + body["product"] + "-"), "PRODUCT_ID_MISMATCH")
    require(body["parents"] == sorted(body["parents"]), "PARENTS_NOT_SORTED")
    require(clock(body["updated_at"]) >= clock(body["created_at"]), "CLOCK_REGRESSION")
    _guard(body)
    unsigned = {k: v for k, v in body.items() if k != "revision_sha256"}
    require(sha256(canonical(unsigned)) == body["revision_sha256"], "REVISION_HASH_MISMATCH")


def prepare(body: Mapping[str, Any]) -> bytes:
    """Seal a full revision once. Retries must reuse these bytes, not call this again."""
    unsigned = copy.deepcopy(dict(body))
    supplied = unsigned.pop("revision_sha256", None)
    unsigned["revision_sha256"] = sha256(canonical(unsigned))
    require(supplied is None or supplied == unsigned["revision_sha256"], "REVISION_HASH_MISMATCH")
    validate(unsigned)
    raw = canonical(unsigned) + b"\n"
    if len(raw) > MAX_REVISION_BYTES:
        field = max(unsigned, key=lambda k: len(canonical(unsigned[k])))
        raise ShelfError("REVISION_SIZE_LIMIT", field)
    return raw


def capture(*, product: str, title: str, statement: str, now: str,
            origin_key: str | None = None) -> bytes:
    """An unmeasured, untriaged idea. Does not fabricate native identities/evidence."""
    return prepare(dict(schema_version="1.0", item_id=f"RSI-{product}-{uuid4()}",
        product=product, origin_key=origin_key, parents=[], mutation_id=str(uuid4()),
        created_at=now, updated_at=now, kind="IDEA", title=title, statement=statement,
        state="OPEN", origin_refs=[], review=dict(review_at=None, review_by=None, event=None),
        next_action=None, native_links=[], last_decision=None, closure=None,
        change_reason="Capture unmeasured idea; source and return condition need triage."))


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "DUPLICATE_JSON_KEY")
        result[key] = value
    return result


def decode(raw: bytes) -> dict[str, Any]:
    require(len(raw) <= MAX_REVISION_BYTES, "REVISION_SIZE_LIMIT")
    try:
        body = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs)
    except (ValueError, UnicodeError, RecursionError):
        raise ShelfError("WIRE_JSON_INVALID") from None
    validate(body)
    require(raw == canonical(body) + b"\n", "NON_CANONICAL_BYTES")
    return body


def revision_path(body: Mapping[str, Any]) -> str:
    return f"{PREFIX}/{body['item_id']}/{body['revision_sha256']}.json"


def fold(files: Mapping[str, bytes], *, complete: bool = True) -> dict[str, Any]:
    """Fold one pinned tree; never select a head by timestamp, path order or title."""
    grouped = defaultdict(dict)
    errors = defaultdict(list)
    for path, raw in sorted(files.items()):
        parts = PurePosixPath(path).parts
        item = parts[2] if len(parts) >= 3 else "INVALID_NAMESPACE"
        try:
            require(relative_path(path) and len(parts) == 4 and path.startswith(PREFIX + "/"), "REVISION_PATH_INVALID")
            body = decode(raw)
            require(path == revision_path(body), "REVISION_PATH_MISMATCH")
            grouped[item][body["revision_sha256"]] = body
        except ShelfError as error:
            errors[item].append(error.code)
    items = {}
    origins, mutations = defaultdict(set), defaultdict(list)
    for item in sorted(set(grouped) | set(errors)):
        rows = grouped[item]
        problems = list(errors[item])
        referenced = set()
        roots = []
        for digest, row in rows.items():
            mutations[row["mutation_id"]].append((item, digest))
            if row["origin_key"]:
                origins[(row["product"], row["origin_key"])].add(item)
            if not row["parents"]:
                roots.append(row)
            for parent in row["parents"]:
                referenced.add(parent)
                if parent not in rows:
                    problems.append("MISSING_PARENT")
                    continue
                if any(row[k] != rows[parent][k] for k in IDENTITY):
                    problems.append("IMMUTABLE_IDENTITY_CHANGED")
                if clock(row["updated_at"]) < clock(rows[parent]["updated_at"]):
                    problems.append("CLOCK_REGRESSION")
        if len(roots) != 1:
            problems.append("GENESIS_COUNT_INVALID")
        # Kahn's algorithm also rejects a disconnected cycle beside a valid root.
        pending = {digest: set(row["parents"]) for digest, row in rows.items()}
        ready = [digest for digest, parents in pending.items() if not parents]
        for digest in ready:
            for child, parents in pending.items():
                if digest in parents:
                    parents.remove(digest)
                    if not parents:
                        ready.append(child)
        if len(ready) != len(rows) and "MISSING_PARENT" not in problems:
            problems.append("LINEAGE_CYCLE")
        heads = sorted(set(rows) - referenced)
        state = "ITEM_INVALID" if problems else "ITEM_CONFLICT" if len(heads) != 1 else "READY"
        items[item] = dict(status=state, reasons=sorted(set(problems)), heads=heads,
            current=copy.deepcopy(rows[heads[0]]) if state == "READY" else None,
            revisions=rows)
    for members in origins.values():
        if len(members) > 1:
            for item in members:
                items[item].update(status="ITEM_CONFLICT", current=None)
                items[item]["reasons"].append("DUPLICATE_ORIGIN_KEY")
    for entries in mutations.values():
        if len(entries) > 1:
            for item, _ in entries:
                items[item].update(status="ITEM_INVALID", current=None)
                items[item]["reasons"].append("MUTATION_ID_CONFLICT")
    return dict(status="READY" if complete else "INCOMPLETE", items=items,
                complete=complete)


def revise(snapshot: Mapping[str, Any], item_id: str, changes: Mapping[str, Any], *,
           now: str, mutation_id: str, reconcile: bool = False) -> bytes:
    require(snapshot.get("complete"), "INCOMPLETE")
    require(isinstance(changes, dict), "CHANGES_OBJECT_REQUIRED")
    item = snapshot["items"].get(item_id)
    require(item is not None, "ITEM_NOT_FOUND")
    require(item["status"] == "READY" or (reconcile and item["status"] == "ITEM_CONFLICT"
            and not item["reasons"]), "ITEM_NOT_WRITABLE")
    require(not any(k in changes for k in (*IDENTITY, "revision_sha256", "parents", "mutation_id", "updated_at", "schema_version")),
            "IMMUTABLE_OR_TOOL_FIELD_UPDATE")
    reason = changes.get("change_reason")
    require(isinstance(reason, str) and bool(reason.strip()), "CHANGE_REASON_REQUIRED")
    # A conflict needs a complete explicit resolution; no automatic merge.
    base = item["current"]
    if reconcile:
        require(len(item["heads"]) > 1, "NO_CONFLICT_TO_RECONCILE")
        base = item["revisions"][item["heads"][0]]
        editable = set(base) - set(IDENTITY) - {"revision_sha256", "parents", "mutation_id", "updated_at", "schema_version"}
        require(set(changes) == editable, "RECONCILIATION_FULL_CONTENT_REQUIRED")
    body = copy.deepcopy(base)
    body.pop("revision_sha256")
    body.update(copy.deepcopy(changes), parents=item["heads"], mutation_id=mutation_id, updated_at=now)
    raw = prepare(body)
    result = fold({revision_path(row): canonical(row) + b"\n" for row in item["revisions"].values()}
                  | {revision_path(decode(raw)): raw})
    require(result["items"][item_id]["status"] == "READY", "REVISION_LINEAGE_INVALID")
    return raw


def attention(snapshot: Mapping[str, Any], *, now: str, limit: int | None = 5) -> dict[str, Any]:
    """Local date review only. Native/event adapters are a separate integration stage."""
    at = clock(now)
    require(limit is None or (isinstance(limit, int) and limit >= 0), "LIMIT_INVALID")
    rows, counts = [], Counter()
    for item_id, item in sorted(snapshot.get("items", {}).items()):
        current = item["current"]
        if current is None:
            state = item["status"]
        elif current["state"] == "CLOSED":
            counts["CLOSED"] += 1
            continue
        else:
            review = current["review"]
            event = review["event"]
            if review["review_by"] and at >= clock(review["review_by"]):
                state = "OVERDUE_REVIEW"
            elif review["review_at"] and at >= clock(review["review_at"]):
                state = "DUE_REVIEW"
            elif not review["review_at"] and ((event is None and not review["review_by"]) or
                                              (event is not None and event["kind"] == "MANUAL")):
                state = "NEEDS_TRIAGE"
            elif event is not None and event["kind"] != "MANUAL":
                state = "SOURCE_READBACK_REQUIRED"
            else:
                state = "WAITING"
        counts[state] += 1
        rows.append(dict(item_id=item_id, status=state, title=current["title"] if current else None,
            revision_sha256=current["revision_sha256"] if current else None, heads=list(item["heads"]),
            review=copy.deepcopy(current["review"]) if current else None,
            source_status="UNKNOWN" if current and current["review"]["event"] else None))
    priority = {s: n for n, s in enumerate(("ITEM_INVALID", "ITEM_CONFLICT", "OVERDUE_REVIEW", "DUE_REVIEW",
                                           "NEEDS_TRIAGE", "SOURCE_READBACK_REQUIRED", "WAITING"))}
    rows.sort(key=lambda row: (priority[row["status"]], (row["review"] or {}).get("review_at") or "", row["item_id"]))
    visible = rows if limit is None else rows[:limit]
    dates = [value for row in rows if row["review"] for value in
             (row["review"]["review_at"], row["review"]["review_by"]) if value and clock(value) > at]
    return dict(status=snapshot["status"], attention_as_of=now,
                snapshot_commit=snapshot.get("commit"), snapshot_complete=snapshot["complete"],
                source_freshness=snapshot.get("source_freshness", "UNVERIFIED_PINNED"),
                source_checked_at=snapshot.get("source_checked_at"), reason=snapshot.get("reason"),
                totals=dict(sorted(counts.items())),
                items=visible, omitted_count=len(rows) - len(visible),
                next_review_at=min(dates, key=clock) if dates else None,
                scientific_admission="NOT_EVALUATED")
