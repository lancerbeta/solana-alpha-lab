"""Authority-gated PathRisk live window glue. Zero-network unless a fixture opener is supplied."""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

import pyarrow.parquet as pq
import yaml

from solana_alpha_lab.factory.commissioning_fixture import COMMISSIONING_DATASET_MANIFEST_ID
from solana_alpha_lab.factory.forward_h900_quote_capture import consumed_mints_from_git
from solana_alpha_lab.factory.hfic_preflight import (
    enumerate_rdp_datasets,
    evidence_epoch_material,
)
from solana_alpha_lab.factory.hfic_session import evidence_epoch_sha256
from solana_alpha_lab.factory.observation_panel_publisher import (
    rebuild_observation_panel_from_rdp,
)
from solana_alpha_lab.factory.observation_primitive_registry import (
    load_observation_primitive_registry,
)
from solana_alpha_lab.factory.observation_primitives import (
    HTTP_CLASS_401,
    HTTP_CLASS_403,
    HTTP_CLASS_429,
    HTTP_CLASS_5XX,
    HTTP_CLASS_NO_RESPONSE,
    HTTP_CLASS_OK,
    HTTP_CLASS_OTHER_4XX,
    HTTP_CLASS_TIMEOUT,
    HTTP_CLASS_TRANSPORT,
    RECENT_URL,
    call_occurrence_id,
    execute_primitive,
    parse_anchor,
    request_sha256,
    search_url,
)
from solana_alpha_lab.factory.observation_schedule_runtime import JupiterReadonlyOpener
from solana_alpha_lab.factory.observation_schedule import (
    canonical_sha256,
    load_observation_schedule,
    parse_utc,
    render_utc,
)
from solana_alpha_lab.factory.observation_schedule_compiler import compile_schedule_document
from solana_alpha_lab.factory.observation_schedule_lifecycle import (
    _authority_policy,
    _minimum_expiry,
    _used_provider_route_ids,
    authorize_schedule,
    expected_authority_phrase,
)
from solana_alpha_lab.factory.observation_schedule_store import ObservationScheduleStore
from solana_alpha_lab.factory.observation_scheduler import (
    DISCOVERY,
    SCHEMA_REQUIRED_KEYS,
    _Accounting,
    _primitive_credit_cost,
    _result_completion,
    tick_once,
)
from solana_alpha_lab.factory.pathrisk_calibration import (
    ATOM_ID,
    NOTIONAL_10M,
    NOTIONAL_1M,
    TERMINAL_BELOW_FLOOR,
    TERMINAL_INFORMATIVE,
    build_readout,
    load_policy,
    proposed_capture_packet,
    require_exact_main_sha,
    select_r0_sample,
)

CALL_CAP = 26
SEARCH_PRIMITIVE = "PRIM-JUPITER-TOKENS-V2-SEARCH-001"
R0_RECENT_DUE = "PATHRISK-R0-RECENT"
R0_SEARCH_DUE = "PATHRISK-R0-SEARCH"
UNKNOWN_NOT_RECORDED_AT_TIME = "UNKNOWN_NOT_RECORDED_AT_TIME"
R0_RECENT_HTTP_TERMINALS = {
    HTTP_CLASS_401: "R0_RECENT_HTTP_401_UNAUTHORIZED",
    HTTP_CLASS_403: "R0_RECENT_HTTP_403_FORBIDDEN",
    HTTP_CLASS_429: "R0_RECENT_HTTP_429_RATE_LIMITED",
    HTTP_CLASS_OTHER_4XX: "R0_RECENT_HTTP_OTHER_4XX",
    HTTP_CLASS_5XX: "R0_RECENT_HTTP_5XX",
    HTTP_CLASS_TIMEOUT: "R0_RECENT_TIMEOUT",
    HTTP_CLASS_TRANSPORT: "R0_RECENT_TRANSPORT_ERROR",
    HTTP_CLASS_NO_RESPONSE: "R0_RECENT_NO_HTTP_RESPONSE",
}
LIVE_SCHEDULE_RELATIVE = "tests/fixtures/observation_schedule/pathrisk_live_window.yaml"
FORBIDDEN_SEARCH_BUNDLE = "BUNDLE-JUPITER-TOKEN-SEARCH-SNAPSHOT-001"
CREDENTIAL_ENV_NAME = "JUPITER_API_KEY"
TERMINAL_CREDENTIAL_MISSING = "CREDENTIAL_ENV_MISSING_BEFORE_PROVIDER"
ADMISSION_SECONDS = 180
RUNTIME_SCHEDULE_NAME = "runtime_schedule.yaml"
RUNTIME_BINDING_NAME = "runtime_binding.json"
REPLACEMENT_REASON_PRE_EVIDENCE_OPERATIONAL_FAILURE = (
    "PRE_EVIDENCE_OPERATIONAL_FAILURE"
)
SUCCESSOR_REASON_MARKET_SUPPLY_RETRY = "MARKET_SUPPLY_RETRY_AFTER_BELOW_FLOOR"
LIVE_IDENTITY_NAMESPACE = "ACT-PATHRISK-LIVE"
LIVE_IDENTITY_RE = re.compile(r"^ACT-PATHRISK-LIVE-(\d{3})$")
OWNER_PHRASE_PREFIX = "OK PATHRISK_SUCCESSOR_WINDOW_IDENTITY_LIVE_V1"
CONSUMED_LIVE_OWNER_PHRASE = (
    "OK EARLY_QUOTE_SURFACE_PATHRISK_CALIBRATION_LIVE_V1: one bounded Jupiter "
    "Free-key read-only PathRisk calibration using a local process-environment "
    "key only; exactly one Tokens V2 /recent and exactly one bulk "
    "/tokens/v2/search R0 snapshot plus quote-only /swap/v2/order; no recurring "
    "/recent; x-api-key header only; no .env read; no key in URL/log/receipt/Git; "
    "no taker, /build, /execute, wallet, signer, transaction, paid plan, second "
    "provider, retry or fallback; cash cap $0; call cap 26; ICP-EARLY-PUMPFUN-V1; "
    "first 4 fresh unconsumed eligible mints or CALIBRATION_ELIGIBLE_BELOW_FLOOR "
    "with quote calls 0; notionals 10000000 and 1000000 lamports; T0 BUY + T0 "
    "reverse + H900 dependent SELL of the same T0 BUY token amount; one window "
    "only; no third notional; Factory runner unchanged; Hypothesis Forge, Paper, "
    "Strategy, Shadow, alpha and NetReturn forbidden."
)
CONSUMED_ACT002_LIVE_OWNER_PHRASE = (
    "OK PATHRISK_FRESH_ACTIVATION_IDENTITY_LIVE_V1: exactly one replacement "
    "prospective PathRisk window ACT-PATHRISK-LIVE-002; predecessor "
    "ACT-PATHRISK-LIVE-001 remains immutable; replacement_reason "
    "PRE_EVIDENCE_OPERATIONAL_FAILURE; not a resume of ACT-PATHRISK-LIVE-001; "
    "Jupiter Free-key; JUPITER_API_KEY process env only; exactly one /recent; "
    "exactly one bulk /tokens/v2/search; quote-only /swap/v2/order; no recurring "
    "/recent; x-api-key header only; no .env / secret leakage; no taker, /build, "
    "/execute, wallet, signer, transaction; no paid plan / second provider; no "
    "retry / fallback; cash cap $0; call cap 26; ICP-EARLY-PUMPFUN-V1; first 4 "
    "fresh unconsumed eligible mints or CALIBRATION_ELIGIBLE_BELOW_FLOOR with "
    "quote_calls=0; notionals 10000000 and 1000000 lamports; T0 BUY + T0 reverse "
    "+ H900 dependent SELL of the same T0 BUY token amount; no third notional; "
    "Factory runner unchanged; Hypothesis Forge, Paper, Strategy, Shadow, alpha "
    "and NetReturn forbidden inside the live window."
)
CONSUMED_OWNER_PHRASES = frozenset(
    {CONSUMED_LIVE_OWNER_PHRASE, CONSUMED_ACT002_LIVE_OWNER_PHRASE}
)


class PathRiskLiveError(ValueError):
    """Typed live-window glue failure."""


INCOMPLETE_WINDOW_STAGES = frozenset(
    {
        "START",
        "RECENT_DONE",
        "R0_BOUND",
        "SAMPLED",
        "T0_COMPLETE",
        "H900_PARTIAL",
    }
)
GIT_PER_WINDOW_IDENTITY_KEYS = (
    "activation_id",
    "predecessor_activation_id",
    "replacement_reason",
)


@dataclass(frozen=True, slots=True)
class LiveWindowIdentity:
    """Immutable PathRisk live identity bound at runtime, never stored as Git current-window ids."""

    activation_id: str
    predecessor_activation_id: str
    replacement_reason: str

    def binding_fields(self) -> dict[str, str]:
        return {
            "activation_id": self.activation_id,
            "predecessor_activation_id": self.predecessor_activation_id,
            "replacement_reason": self.replacement_reason,
        }


def parse_live_activation_id(value: str) -> tuple[str, int]:
    text = str(value or "").strip()
    match = LIVE_IDENTITY_RE.fullmatch(text)
    if match is None:
        raise PathRiskLiveError("LIVE_IDENTITY_NAMESPACE_MISMATCH")
    return text, int(match.group(1))


def format_live_activation_id(sequence: int) -> str:
    if sequence < 1 or sequence > 999:
        raise PathRiskLiveError("LIVE_IDENTITY_SEQUENCE_OUT_OF_RANGE")
    return f"ACT-PATHRISK-LIVE-{sequence:03d}"


def load_successor_identity_policy(policy: Mapping[str, Any]) -> dict[str, Any]:
    live = policy.get("live_window")
    if not isinstance(live, Mapping):
        raise PathRiskLiveError("LIVE_WINDOW_IDENTITY_MISSING")
    raw = live.get("identity")
    if not isinstance(raw, Mapping):
        raise PathRiskLiveError("LIVE_WINDOW_IDENTITY_MISSING")
    for key in GIT_PER_WINDOW_IDENTITY_KEYS:
        if key in raw:
            raise PathRiskLiveError("GIT_PER_WINDOW_IDENTITY_FORBIDDEN")
    namespace = str(raw.get("namespace") or "").strip()
    if namespace != LIVE_IDENTITY_NAMESPACE:
        raise PathRiskLiveError("LIVE_IDENTITY_NAMESPACE_MISMATCH")
    reason = str(raw.get("successor_reason") or "").strip()
    if reason != SUCCESSOR_REASON_MARKET_SUPPLY_RETRY:
        raise PathRiskLiveError("SUCCESSOR_REASON_UNSUPPORTED")
    terminals = raw.get("successor_after_terminal")
    if not isinstance(terminals, list) or [str(item) for item in terminals] != [
        TERMINAL_BELOW_FLOOR
    ]:
        raise PathRiskLiveError("SUCCESSOR_AFTER_TERMINAL_UNSUPPORTED")
    try:
        step = int(raw.get("sequence_step"))
    except (TypeError, ValueError) as exc:
        raise PathRiskLiveError("SUCCESSOR_SEQUENCE_STEP_INVALID") from exc
    if step != 1:
        raise PathRiskLiveError("SUCCESSOR_SEQUENCE_STEP_INVALID")
    if raw.get("predecessor_required") is not True:
        raise PathRiskLiveError("PREDECESSOR_REQUIRED")
    if raw.get("immutable_identity") is not True:
        raise PathRiskLiveError("IMMUTABLE_IDENTITY_REQUIRED")
    if raw.get("one_window_per_owner_phrase") is not True:
        raise PathRiskLiveError("ONE_WINDOW_PER_OWNER_PHRASE_REQUIRED")
    if raw.get("branching_forbidden") is not True:
        raise PathRiskLiveError("BRANCHING_FORBIDDEN_REQUIRED")
    return {
        "namespace": namespace,
        "successor_reason": reason,
        "sequence_step": step,
        "successor_after_terminal": [TERMINAL_BELOW_FLOOR],
    }


def resolve_live_window_identity(
    policy: Mapping[str, Any],
    activation_id: str,
    predecessor_activation_id: str,
) -> LiveWindowIdentity:
    rules = load_successor_identity_policy(policy)
    activation, act_seq = parse_live_activation_id(activation_id)
    predecessor, pred_seq = parse_live_activation_id(predecessor_activation_id)
    if activation == predecessor:
        raise PathRiskLiveError("PREDECESSOR_CANNOT_BE_CURRENT_ACTIVATION")
    if act_seq != pred_seq + int(rules["sequence_step"]):
        raise PathRiskLiveError("SUCCESSOR_SEQUENCE_MUST_BE_PLUS_ONE")
    return LiveWindowIdentity(
        activation_id=activation,
        predecessor_activation_id=predecessor,
        replacement_reason=str(rules["successor_reason"]),
    )


def render_successor_owner_phrase(
    policy: Mapping[str, Any],
    identity: LiveWindowIdentity,
) -> str:
    rules = load_successor_identity_policy(policy)
    if identity.replacement_reason != rules["successor_reason"]:
        raise PathRiskLiveError("SUCCESSOR_REASON_UNSUPPORTED")
    max_calls = int(policy["runtime_limits"]["max_calls"])
    icp = str(policy["population"]["icp_id"])
    return (
        f"{OWNER_PHRASE_PREFIX}: exactly one successor prospective PathRisk window "
        f"{identity.activation_id}; predecessor {identity.predecessor_activation_id} "
        f"remains immutable; successor_reason {identity.replacement_reason}; not a resume of "
        f"{identity.predecessor_activation_id}; Jupiter Free-key; JUPITER_API_KEY process env only; "
        "exactly one /recent; exactly one bulk /tokens/v2/search; quote-only /swap/v2/order; "
        "no recurring /recent; x-api-key header only; no .env / secret leakage; no taker, /build, "
        "/execute, wallet, signer, transaction; no paid plan / second provider; no retry / fallback; "
        f"cash cap $0; call cap {max_calls}; {icp}; first 4 fresh unconsumed eligible mints or "
        "CALIBRATION_ELIGIBLE_BELOW_FLOOR with quote_calls=0; notionals "
        f"{NOTIONAL_10M} and {NOTIONAL_1M} lamports; T0 BUY + T0 reverse + H900 dependent SELL of the "
        "same T0 BUY token amount; no third notional; Factory runner unchanged; Hypothesis Forge, Paper, "
        "Strategy, Shadow, alpha and NetReturn forbidden inside the live window."
    )


def journal_scientific_terminal(journal: Mapping[str, Any]) -> str | None:
    terminal = journal.get("terminal")
    if isinstance(terminal, str) and terminal.strip():
        return terminal.strip()
    if journal.get("stage") == "BELOW_FLOOR":
        return TERMINAL_BELOW_FLOOR
    return None


def list_local_activation_ids(data_root: Path) -> list[str]:
    root = Path(data_root) / "pathrisk_live"
    if not root.is_dir():
        return []
    found: list[str] = []
    for child in sorted(root.iterdir()):
        if not child.is_dir():
            continue
        if LIVE_IDENTITY_RE.fullmatch(child.name) is None:
            continue
        if (child / "journal.json").is_file():
            found.append(child.name)
    return found


def assert_predecessor_eligible(
    data_root: Path,
    identity: LiveWindowIdentity,
) -> str:
    pred_id = identity.predecessor_activation_id
    path = _journal_path(data_root, pred_id)
    if not path.is_file():
        raise PathRiskLiveError("PREDECESSOR_JOURNAL_MISSING")
    predecessor = load_journal(data_root, pred_id)
    recorded = predecessor.get("activation_id")
    if recorded not in (None, pred_id):
        raise PathRiskLiveError("PREDECESSOR_IDENTITY_MISMATCH")
    binding_path = runtime_live_dir(data_root, pred_id) / RUNTIME_BINDING_NAME
    if binding_path.is_file():
        try:
            binding = json.loads(binding_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise PathRiskLiveError("PREDECESSOR_IDENTITY_MISMATCH") from exc
        if not isinstance(binding, Mapping):
            raise PathRiskLiveError("PREDECESSOR_IDENTITY_MISMATCH")
        if binding.get("activation_id") not in (None, pred_id):
            raise PathRiskLiveError("PREDECESSOR_IDENTITY_MISMATCH")
    stage = str(predecessor.get("stage") or "")
    terminal = journal_scientific_terminal(predecessor)
    if stage == "COMPLETE" or terminal in {TERMINAL_INFORMATIVE}:
        raise PathRiskLiveError(
            "PREDECESSOR_INFORMATIVE_OR_COMPLETE_FORBIDS_ORDINARY_SUCCESSOR"
        )
    if terminal != TERMINAL_BELOW_FLOOR:
        raise PathRiskLiveError("PREDECESSOR_NOT_BELOW_FLOOR")
    return terminal


def successor_preflight(
    *,
    data_root: Path,
    policy: Mapping[str, Any],
) -> dict[str, Any]:
    rules = load_successor_identity_policy(policy)
    reason = str(rules["successor_reason"])
    payload: dict[str, Any] = {
        "predecessor_activation_id": None,
        "predecessor_terminal": None,
        "proposed_activation_id": None,
        "successor_reason": reason,
        "eligible_for_successor": False,
        "exact_future_owner_phrase": None,
        "credential_reads": False,
        "provider_calls": 0,
        "git_mutated": False,
        "rdp_mutation": 0,
    }
    sequenced: list[tuple[int, str, dict[str, Any]]] = []
    for activation_id in list_local_activation_ids(data_root):
        _, seq = parse_live_activation_id(activation_id)
        sequenced.append((seq, activation_id, load_journal(data_root, activation_id)))
    if not sequenced:
        return payload
    _, pred_id, journal = max(sequenced, key=lambda item: item[0])
    terminal = journal_scientific_terminal(journal)
    payload["predecessor_activation_id"] = pred_id
    payload["predecessor_terminal"] = terminal
    stage = str(journal.get("stage") or "")
    if stage in INCOMPLETE_WINDOW_STAGES:
        return payload
    if stage == "COMPLETE" or terminal == TERMINAL_INFORMATIVE:
        return payload
    if terminal != TERMINAL_BELOW_FLOOR:
        return payload
    _, pred_seq = parse_live_activation_id(pred_id)
    proposed = format_live_activation_id(pred_seq + int(rules["sequence_step"]))
    identity = resolve_live_window_identity(policy, proposed, pred_id)
    try:
        assert_predecessor_eligible(data_root, identity)
    except PathRiskLiveError:
        return payload
    payload["proposed_activation_id"] = proposed
    payload["eligible_for_successor"] = True
    payload["exact_future_owner_phrase"] = render_successor_owner_phrase(policy, identity)
    return payload


class HardCapOpener:
    """Count fixture/provider opens against the PathRisk 26-call cap."""

    def __init__(self, inner: object, *, cap: int = CALL_CAP) -> None:
        self.inner = inner
        self.cap = cap
        self.urls: list[str] = []

    def open(self, url: str) -> dict[str, Any]:
        if len(self.urls) >= self.cap:
            raise PathRiskLiveError("CALL_CAP_26_EXCEEDED")
        self.urls.append(url)
        return self.inner.open(url)  # type: ignore[union-attr]


class FrozenClock:
    """Injectable test clock. Forbidden on the production PathRisk path."""

    def __init__(self, now: datetime) -> None:
        self.now = now.astimezone(UTC)

    def __call__(self) -> datetime:
        return self.now

    def sleep(self, seconds: float) -> None:
        if seconds > 0:
            self.now = self.now + timedelta(seconds=seconds)

    def advance(self, seconds: int = 4) -> datetime:
        self.sleep(seconds)
        return self.now


class SystemClock:
    """UTC wall clock. No manual advance."""

    def __call__(self) -> datetime:
        return datetime.now(UTC)

    def sleep(self, seconds: float) -> None:
        if seconds > 0:
            time.sleep(seconds)


class ControllableClock:
    """Test clock that treats sleep as simulated elapsed time."""

    def __init__(self, now: datetime) -> None:
        self.now = now.astimezone(UTC)

    def __call__(self) -> datetime:
        return self.now

    def sleep(self, seconds: float) -> None:
        if seconds > 0:
            self.now = self.now + timedelta(seconds=seconds)


SOL_MINT = "So11111111111111111111111111111111111111112"


class FixtureWindowOpener:
    """Zero-network Jupiter surface for the live PathRisk window."""

    def __init__(self, fixture: Mapping[str, Any]) -> None:
        self.fixture = dict(fixture)
        self.urls: list[str] = []
        self.sell_counts: dict[tuple[str, str], int] = {}
        self.mode = str(fixture.get("mode") or "happy")

    def open(self, url: str) -> dict[str, Any]:
        self.urls.append(url)
        parsed = urlsplit(url)
        query = parse_qs(parsed.query)
        if parsed.path == "/tokens/v2/recent":
            return {
                "http_status": 200,
                "body": list(self.fixture.get("recent") or []),
                "url_has_api_key": False,
            }
        if parsed.path == "/tokens/v2/search":
            requested = [item for item in (query.get("query") or [""])[0].split(",") if item]
            by_id = {
                str(row.get("id") or row.get("mint")): row
                for row in list(self.fixture.get("search") or [])
                if isinstance(row, Mapping)
            }
            body = [by_id[mint] for mint in requested if mint in by_id]
            return {"http_status": 200, "body": body, "url_has_api_key": False}
        amount = (query.get("amount") or [""])[0]
        input_mint = (query.get("inputMint") or [""])[0]
        output_mint = (query.get("outputMint") or [""])[0]
        if input_mint == SOL_MINT:
            if self.mode == "invalid_schema":
                token_out = "not-an-integer"
            else:
                token_out = "11100000010" if amount == NOTIONAL_10M else "1110000001"
            return {
                "http_status": 200,
                "url_has_api_key": False,
                "body": {
                    "inAmount": amount,
                    "outAmount": token_out,
                    "router": "iris",
                    "mode": "ultra",
                    "inputMint": input_mint,
                    "outputMint": output_mint,
                    "priceImpactPct": "0.12",
                    "feeBps": "10",
                    "platformFee": None,
                    "routePlan": [{"swapInfo": {"feeAmount": "1"}}],
                },
            }
        key = (input_mint, amount)
        self.sell_counts[key] = self.sell_counts.get(key, 0) + 1
        visit = self.sell_counts[key]
        if self.mode == "h900_missing" and visit >= 2:
            return {"http_status": 404, "body": {"error": "NO_ROUTE"}, "url_has_api_key": False}
        if amount == "11100000010":
            out = "9800000" if (visit == 1 or self.mode == "degenerate") else "9700000"
        else:
            out = "980000" if (visit == 1 or self.mode == "degenerate") else "960000"
        return {
            "http_status": 200,
            "url_has_api_key": False,
            "body": {
                "inAmount": amount,
                "outAmount": out,
                "router": "iris",
                "mode": "ultra",
                "inputMint": input_mint,
                "outputMint": output_mint,
                "routePlan": [],
            },
        }


def _journal_path(data_root: Path, activation_id: str) -> Path:
    return Path(data_root) / "pathrisk_live" / activation_id / "journal.json"


def load_journal(data_root: Path, activation_id: str) -> dict[str, Any]:
    path = _journal_path(data_root, activation_id)
    if not path.is_file():
        return {"stage": "START"}
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise PathRiskLiveError("JOURNAL_INVALID")
    return loaded


def save_journal(data_root: Path, activation_id: str, payload: Mapping[str, Any]) -> None:
    path = _journal_path(data_root, activation_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(payload), indent=2, sort_keys=True), encoding="utf-8")


def require_owner_phrase(
    policy: Mapping[str, Any],
    phrase: str,
    identity: LiveWindowIdentity,
) -> None:
    if phrase in CONSUMED_OWNER_PHRASES:
        raise PathRiskLiveError("OWNER_PHRASE_CONSUMED")
    expected = render_successor_owner_phrase(policy, identity)
    if phrase != expected:
        raise PathRiskLiveError("OWNER_PHRASE_MISMATCH")


def transport_probe_owner_phrase(policy: Mapping[str, Any]) -> str:
    return str(policy["transport_probe"]["future_owner_phrase"])


def require_transport_probe_phrase(policy: Mapping[str, Any], phrase: str) -> None:
    if phrase != transport_probe_owner_phrase(policy):
        raise PathRiskLiveError("OWNER_PHRASE_MISMATCH")


def _http_fields(result: Mapping[str, Any]) -> dict[str, Any]:
    http_class = result.get("http_class")
    http_status = result.get("http_status")
    if isinstance(http_class, str) and http_class:
        return {"http_status": http_status, "http_class": http_class}
    return {
        "http_status": http_status,
        "http_class": UNKNOWN_NOT_RECORDED_AT_TIME,
    }


def r0_recent_operational_terminal(recent: Mapping[str, Any]) -> str | None:
    http_class = str((_http_fields(recent).get("http_class") or ""))
    if http_class == HTTP_CLASS_OK:
        return None
    return R0_RECENT_HTTP_TERMINALS.get(http_class)


def _body_kind_and_count(body: object) -> tuple[str, int]:
    if body is None:
        return "null", 0
    if isinstance(body, list):
        return "list", len(body)
    if isinstance(body, Mapping):
        return "mapping", len(body)
    return "other", 0


def run_transport_probe_recent(
    *,
    opener: object,
    clock: object | None = None,
) -> dict[str, Any]:
    tick = clock if callable(clock) else SystemClock()
    result = execute_primitive(
        primitive_id=DISCOVERY,
        primitive_version="1.0",
        method="GET",
        url=RECENT_URL,
        opener=opener,
        clock=tick,
    )
    kind, count = _body_kind_and_count(result.get("body"))
    fields = _http_fields(result)
    return {
        "provider_calls": 1,
        "http_status": fields["http_status"],
        "http_class": fields["http_class"],
        "body_kind": kind,
        "body_count": count,
        "credential_env_name": CREDENTIAL_ENV_NAME,
        "git_mutation": False,
        "rdp_mutation": 0,
        "scientific_window_started": False,
        "retry": False,
        "fallback": False,
        "activation_id": None,
    }


def _walk_mints(node: object, mints: set[str]) -> None:
    if isinstance(node, Mapping):
        mint = node.get("mint") or node.get("id")
        if isinstance(mint, str) and mint.endswith("pump"):
            mints.add(mint)
        for value in node.values():
            _walk_mints(value, mints)
    elif isinstance(node, list):
        for item in node:
            _walk_mints(item, mints)


def _rdp_consumed_mints(data_root: Path) -> tuple[set[str], list[dict[str, str]]]:
    mints: set[str] = set()
    refs: list[dict[str, str]] = []
    datasets, warnings = enumerate_rdp_datasets(Path(data_root))
    if any(item.get("code") == "DATASET_PARTITION_CORRUPT" for item in warnings):
        raise PathRiskLiveError("POPULATION_EXCLUSION_NOT_PROVEN")
    manifests_dir = Path(data_root) / "datasets" / "manifests"
    for item in datasets:
        manifest_id = str(item.get("dataset_manifest_id") or "")
        if not manifest_id or manifest_id == COMMISSIONING_DATASET_MANIFEST_ID:
            continue
        decision_path = manifests_dir / f"{manifest_id}.decision.json"
        labels_path = manifests_dir / f"{manifest_id}.labels.json"
        consumed = False
        if decision_path.is_file() and not decision_path.is_symlink():
            try:
                decision = json.loads(decision_path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise PathRiskLiveError("POPULATION_EXCLUSION_NOT_PROVEN") from exc
            if isinstance(decision, Mapping) and decision.get("outcome_consumed") is True:
                consumed = True
        if labels_path.is_file() and not labels_path.is_symlink():
            try:
                labels = json.loads(labels_path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise PathRiskLiveError("POPULATION_EXCLUSION_NOT_PROVEN") from exc
            if isinstance(labels, Mapping) and (
                labels.get("outcome_previously_consumed") is True
                or labels.get("confirmatory_reuse_forbidden") is True
            ):
                consumed = True
        if not consumed:
            continue
        partition_dir = manifests_dir / "partitions"
        found_mint_column = False
        if partition_dir.is_dir():
            for part_path in sorted(partition_dir.glob("*.json")):
                try:
                    part = json.loads(part_path.read_text(encoding="utf-8"))
                except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                    continue
                if not isinstance(part, Mapping):
                    continue
                if str(part.get("dataset_manifest_id") or "") != manifest_id:
                    continue
                parquet_path = Path(data_root) / str(part.get("logical_location") or "")
                if not parquet_path.is_file():
                    raise PathRiskLiveError("POPULATION_EXCLUSION_NOT_PROVEN")
                table = pq.read_table(parquet_path)
                if "mint" not in table.column_names:
                    continue
                found_mint_column = True
                for value in table.column("mint").to_pylist():
                    if isinstance(value, str) and value:
                        mints.add(value)
        if not found_mint_column:
            raise PathRiskLiveError("POPULATION_EXCLUSION_NOT_PROVEN")
        refs.append(
            {
                "kind": "rdp_dataset",
                "dataset_manifest_id": manifest_id,
                "dataset_fingerprint": str(item.get("dataset_fingerprint") or ""),
            }
        )
    return mints, refs


def resolve_consumed_exclusions(
    *,
    repo_root: Path,
    data_root: Path,
    policy: Mapping[str, Any],
    resolved_at: datetime,
) -> dict[str, Any]:
    try:
        git_mints = consumed_mints_from_git(repo_root, policy)
    except Exception as exc:
        raise PathRiskLiveError("POPULATION_EXCLUSION_NOT_PROVEN") from exc
    if not git_mints:
        raise PathRiskLiveError("POPULATION_EXCLUSION_NOT_PROVEN")
    rdp_mints, rdp_refs = _rdp_consumed_mints(data_root)
    union = set(git_mints) | set(rdp_mints)
    if not union:
        raise PathRiskLiveError("POPULATION_EXCLUSION_NOT_PROVEN")
    ordered = sorted(union)
    source_refs: list[dict[str, str]] = []
    source_hashes: list[str] = []
    for relative in policy.get("consumed_mint_receipts") or []:
        path = Path(repo_root) / str(relative)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        source_refs.append({"kind": "git_receipt", "path": str(relative), "sha256": digest})
        source_hashes.append(digest)
    source_refs.extend(rdp_refs)
    for item in rdp_refs:
        if item.get("dataset_fingerprint"):
            source_hashes.append(item["dataset_fingerprint"])
    packet = {
        "excluded_mint_count": len(ordered),
        "excluded_mints_sha256": hashlib.sha256("\n".join(ordered).encode("utf-8")).hexdigest(),
        "source_refs": source_refs,
        "source_hashes": source_hashes,
        "resolved_at": render_utc(resolved_at),
        "mints": ordered,
    }
    packet["exclusion_packet_sha256"] = canonical_sha256(
        {key: value for key, value in packet.items() if key != "exclusion_packet_sha256"}
    )
    return packet


def _assert_live_schedule(schedule: Mapping[str, Any]) -> None:
    if schedule.get("source_poll", {}).get("enabled") is not False:
        raise PathRiskLiveError("RECURRING_SOURCE_POLL_NOT_DISABLED")
    x_bundles = list(schedule["x_point"]["bundle_ids"])
    y_bundles = [
        bundle for point in schedule["y_points"] for bundle in point["bundle_ids"]
    ]
    if FORBIDDEN_SEARCH_BUNDLE in x_bundles or FORBIDDEN_SEARCH_BUNDLE in y_bundles:
        raise PathRiskLiveError("HIDDEN_X300_SEARCH_FORBIDDEN")
    budgets = schedule["budgets"]
    if int(budgets["provider_calls_lifetime_max"]) != CALL_CAP:
        raise PathRiskLiveError("CALL_CAP_26_NOT_ENFORCEABLE")
    if int(budgets["provider_calls_per_utc_day_max"]) != CALL_CAP:
        raise PathRiskLiveError("CALL_CAP_26_NOT_ENFORCEABLE")
    if budgets.get("retry") is not False or budgets.get("fallback") is not False:
        raise PathRiskLiveError("RETRY_OR_FALLBACK_FORBIDDEN")
    if int(budgets["min_provider_pace_seconds"]) < 3:
        raise PathRiskLiveError("PACE_BELOW_FLOOR")


def sleep_clock(clock: object, seconds: float) -> None:
    if seconds <= 0:
        return
    sleeper = getattr(clock, "sleep", None)
    if not callable(sleeper):
        raise PathRiskLiveError("CLOCK_SLEEP_UNSUPPORTED")
    sleeper(seconds)


def wait_until(clock: object, target: datetime) -> None:
    remaining = (target.astimezone(UTC) - clock()).total_seconds()
    if remaining > 0:
        sleep_clock(clock, remaining)


def prospective_band_derivable(schedule: Mapping[str, Any]) -> bool:
    x_point = schedule["x_point"]
    y_points = list(schedule["y_points"])
    if not y_points:
        return False
    x_deadline = int(x_point["due_offset_seconds"]) + int(x_point["allowed_lateness_seconds"])
    y_due = int(y_points[0]["due_offset_seconds"])
    return 0 < x_deadline < y_due


def prospective_time_admissible(
    row: Mapping[str, Any],
    *,
    schedule: Mapping[str, Any],
    as_of: datetime,
) -> bool:
    created = parse_anchor(row)
    if created is None:
        return False
    x_point = schedule["x_point"]
    y_point = schedule["y_points"][0]
    x_deadline = created + timedelta(
        seconds=int(x_point["due_offset_seconds"]) + int(x_point["allowed_lateness_seconds"])
    )
    y_due = created + timedelta(seconds=int(y_point["due_offset_seconds"]))
    if as_of > x_deadline:
        return False
    if as_of >= y_due:
        return False
    return True


def runtime_live_dir(data_root: Path, activation_id: str) -> Path:
    return Path(data_root) / "pathrisk_live" / activation_id


def _assert_identity_fields(payload: Mapping[str, Any], identity: LiveWindowIdentity) -> None:
    for key, expected in identity.binding_fields().items():
        if payload.get(key) != expected:
            raise PathRiskLiveError("INCOMPATIBLE_ACTIVATION_BINDING")
    if payload.get("resume_of_predecessor") is True:
        raise PathRiskLiveError("INCOMPATIBLE_ACTIVATION_BINDING")


def _stamp_identity(payload: dict[str, Any], identity: LiveWindowIdentity) -> None:
    payload.update(identity.binding_fields())
    payload["resume_of_predecessor"] = False


def _assert_existing_journal_identity(
    data_root: Path,
    identity: LiveWindowIdentity,
    journal: Mapping[str, Any],
) -> None:
    path = _journal_path(data_root, identity.activation_id)
    if not path.is_file():
        return
    _assert_identity_fields(journal, identity)


def materialize_runtime_schedule(
    root: Path,
    data_root: Path,
    now: datetime,
    identity: LiveWindowIdentity,
) -> dict[str, Any]:
    directory = runtime_live_dir(data_root, identity.activation_id)
    directory.mkdir(parents=True, exist_ok=True)
    yaml_path = directory / RUNTIME_SCHEDULE_NAME
    binding_path = directory / RUNTIME_BINDING_NAME
    if yaml_path.is_file():
        loaded = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
        if not isinstance(loaded, Mapping):
            raise PathRiskLiveError("RUNTIME_SCHEDULE_INVALID")
        compiled = compile_schedule_document(dict(loaded), root=root)
        if compiled.schedule is None:
            raise PathRiskLiveError(str(compiled.terminal))
        _assert_live_schedule(compiled.schedule)
        binding = json.loads(binding_path.read_text(encoding="utf-8"))
        if binding.get("schedule_sha256") != compiled.schedule["schedule_sha256"]:
            raise PathRiskLiveError("RUNTIME_SCHEDULE_BINDING_MISMATCH")
        _assert_identity_fields(binding, identity)
        return compiled.schedule
    template = load_observation_schedule(root, LIVE_SCHEDULE_RELATIVE)
    document = yaml.safe_load(yaml.safe_dump(template))
    starts = now.astimezone(UTC)
    document["activation"] = {
        **dict(template.get("activation") or {}),
        "starts_at": render_utc(starts),
        "stops_admitting_at": render_utc(starts + timedelta(seconds=ADMISSION_SECONDS)),
    }
    compiled = compile_schedule_document(document, root=root)
    if compiled.schedule is None:
        raise PathRiskLiveError(str(compiled.terminal))
    _assert_live_schedule(compiled.schedule)
    if not prospective_band_derivable(compiled.schedule):
        raise PathRiskLiveError("PROSPECTIVE_TIME_ADMISSIBILITY_REQUIRES_SCIENCE_REPLAN")
    yaml_path.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
    binding_path.write_text(
        json.dumps(
            {
                **identity.binding_fields(),
                "resume_of_predecessor": False,
                "schedule_sha256": compiled.schedule["schedule_sha256"],
                "starts_at": document["activation"]["starts_at"],
                "stops_admitting_at": document["activation"]["stops_admitting_at"],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return compiled.schedule


def load_process_credential(environ: Mapping[str, str] | None) -> str:
    env = environ if environ is not None else os.environ
    value = env.get(CREDENTIAL_ENV_NAME)
    if not isinstance(value, str) or not value.strip():
        raise PathRiskLiveError(TERMINAL_CREDENTIAL_MISSING)
    return value


def assert_rdp_ready(data_root: Path) -> None:
    _, warnings = enumerate_rdp_datasets(Path(data_root))
    if any(item.get("code") == "DATASET_PARTITION_CORRUPT" for item in warnings):
        raise PathRiskLiveError("RDP_INTEGRITY_FAILED")
    lock = Path(data_root) / "locks" / "writer.lock"
    if lock.is_file() and not lock.is_symlink():
        try:
            payload = json.loads(lock.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise PathRiskLiveError("RDP_WRITER_STATE_INVALID") from exc
        expiry_raw = payload.get("expiry") if isinstance(payload, Mapping) else None
        if isinstance(expiry_raw, str):
            try:
                expiry = parse_utc(expiry_raw)
            except Exception as exc:
                raise PathRiskLiveError("RDP_WRITER_STATE_INVALID") from exc
            if expiry > datetime.now(UTC):
                raise PathRiskLiveError("RDP_WRITER_ACTIVE")


def assert_no_completed_window(journal: Mapping[str, Any]) -> None:
    stage = journal.get("stage")
    if stage == "COMPLETE":
        raise PathRiskLiveError("PRIOR_PATHRISK_WINDOW_COMPLETED")
    if stage == "BELOW_FLOOR" or journal.get("terminal") == TERMINAL_BELOW_FLOOR:
        raise PathRiskLiveError("PRIOR_PATHRISK_WINDOW_BELOW_FLOOR")


def compile_live_schedule(root: Path, *, relative: str | None = None) -> dict[str, Any]:
    document = load_observation_schedule(root, relative or LIVE_SCHEDULE_RELATIVE)
    compiled = compile_schedule_document(document, root=root)
    if compiled.schedule is None:
        raise PathRiskLiveError(str(compiled.terminal))
    _assert_live_schedule(compiled.schedule)
    return compiled.schedule


def _activate(
    *,
    root: Path,
    data_root: Path,
    store: ObservationScheduleStore,
    schedule: Mapping[str, Any],
    now: datetime,
    producer_git_sha: str,
    activation_id: str,
) -> str:
    store.persist_registered_schedule(
        schedule_sha256=str(schedule["schedule_sha256"]),
        schedule_key=str(schedule["schedule_key"]),
        document=dict(schedule),
        clock=now,
    )
    expires_at = render_utc(_minimum_expiry(schedule))
    _, routes = _used_provider_route_ids(root, schedule)
    policy = _authority_policy(
        root=root,
        document=schedule,
        schedule_key=str(schedule["schedule_key"]),
        expires_at=expires_at,
    )
    authority = authorize_schedule(
        root=root,
        data_root=data_root,
        store=store,
        schedule_sha256=str(schedule["schedule_sha256"]),
        phrase=expected_authority_phrase(
            schedule_sha256=str(schedule["schedule_sha256"]),
            schedule_key=str(schedule["schedule_key"]),
            activation_starts_at=str(schedule["activation"]["starts_at"]),
            activation_stops_admitting_at=str(schedule["activation"]["stops_admitting_at"]),
            provider_route_ids=routes,
            expires_at=expires_at,
            policy_digest=canonical_sha256(policy),
        ),
        now=now,
        producer_git_sha=producer_git_sha,
    )
    store.upsert_activation(
        {
            "schedule_sha256": schedule["schedule_sha256"],
            "activation_id": activation_id,
            "schedule_key": schedule["schedule_key"],
            "state": "ACTIVE",
            "authority_receipt_sha256": authority["receipt_sha256"],
            "starts_at": schedule["activation"]["starts_at"],
            "stops_admitting_at": schedule["activation"]["stops_admitting_at"],
            "payload": {},
        },
        clock=now,
    )
    return activation_id


def _accounting(
    store: ObservationScheduleStore,
    schedule: Mapping[str, Any],
    now: datetime,
    root: Path,
    activation_id: str,
) -> _Accounting:
    registry = load_observation_primitive_registry(root)
    credit_costs = {
        primitive_id: int(
            (primitive.get("modeled_credit_cost") or {}).get("credits_per_request", 1)
        )
        for primitive_id, primitive in registry.primitives.items()
    }
    return _Accounting(
        store,
        schedule,
        activation_id,
        now,
        credit_costs=credit_costs,
    )


def _oneshot(
    *,
    store: ObservationScheduleStore,
    schedule: Mapping[str, Any],
    primitive_id: str,
    point_id: str,
    due_at: str,
    url: str,
    opener: object,
    clock: object,
    accounts: _Accounting,
    expected_entities: Sequence[str] | None = None,
    pace_seconds: int = 3,
) -> dict[str, Any]:
    digest = str(schedule["schedule_sha256"])
    request_digest = request_sha256(
        method="GET", url=url, body=None, primitive_version="1.0"
    )
    occurrence = call_occurrence_id(
        schedule_sha256=digest,
        activation_id=accounts.activation_id,
        primitive_id=primitive_id,
        point_id=point_id,
        due_at=due_at,
        claim_identity_set=(),
        request_digest=request_digest,
    )
    prior = store.call_state(occurrence)
    if prior == "STARTED":
        raise PathRiskLiveError("IN_FLIGHT_CALL_INDETERMINATE")
    if prior == "COMPLETED":
        payload = store.call_payload(occurrence) or {}
        return {
            "reused": True,
            "request_sha256": request_digest,
            "call_occurrence_id": occurrence,
            "response_sha256": payload.get("response_sha256"),
            "body": payload.get("body"),
            "rows": list(payload.get("rows") or []),
            **_http_fields(payload),
        }
    while True:
        blocked = accounts.gate(
            extra_credits=_primitive_credit_cost(accounts, primitive_id),
            now=clock(),
        )
        if blocked == "PACE_WAIT":
            sleep_clock(clock, max(pace_seconds, 3))
            continue
        if blocked:
            raise PathRiskLiveError(str(blocked))
        break
    attempt_id = f"ATT-{uuid4().hex[:12].upper()}"
    start_state = store.start_call(
        request_sha256=request_digest,
        call_occurrence_id=occurrence,
        attempt_id=attempt_id,
        primitive_id=primitive_id,
        payload={"url": url, "due_at": due_at},
        clock=clock(),
    )
    if start_state == "COMPLETED":
        payload = store.call_payload(occurrence) or {}
        return {
            "reused": True,
            "request_sha256": request_digest,
            "call_occurrence_id": occurrence,
            "response_sha256": payload.get("response_sha256"),
            "body": payload.get("body"),
            "rows": list(payload.get("rows") or []),
            **_http_fields(payload),
        }
    if start_state != "STARTED":
        raise PathRiskLiveError(str(start_state))
    result = execute_primitive(
        primitive_id=primitive_id,
        primitive_version="1.0",
        method="GET",
        url=url,
        opener=opener,
        clock=clock,
        schema_required_keys=SCHEMA_REQUIRED_KEYS.get(primitive_id),
        expected_entities=expected_entities,
    )
    completion = _result_completion(result, clock())
    accounts.note(
        raw_bytes=len(json.dumps(result.get("body"), default=str)),
        credits=_primitive_credit_cost(accounts, primitive_id),
        completed_at=completion,
    )
    body = result.get("body")
    rows = body if isinstance(body, list) else []
    fields = _http_fields(result)
    store.complete_call(
        request_sha256=request_digest,
        call_occurrence_id=occurrence,
        attempt_id=attempt_id,
        payload={
            "status": result.get("status"),
            "missing_reason": result.get("missing_reason"),
            "response_sha256": result.get("response_sha256"),
            "body": body,
            "rows": rows,
            "call_occurrence_id": occurrence,
            "http_status": fields["http_status"],
            "http_class": fields["http_class"],
        },
        clock=completion,
    )
    sleep_clock(clock, 4)
    return {
        "reused": False,
        "request_sha256": request_digest,
        "call_occurrence_id": occurrence,
        "response_sha256": result.get("response_sha256"),
        "body": body,
        "rows": list(rows),
        **fields,
    }


def _drain_quotes(
    *,
    root: Path,
    data_root: Path,
    store: ObservationScheduleStore,
    schedule: Mapping[str, Any],
    opener: object,
    producer_git_sha: str,
    clock: object,
    discovery: Sequence[Mapping[str, Any]] | list[Any],
    steps: int,
    wait_future: bool = False,
    activation_id: str,
) -> dict[str, Any] | None:
    last: dict[str, Any] | None = None
    injected: Sequence[Mapping[str, Any]] | list[Any] = discovery
    digest = str(schedule["schedule_sha256"])
    for _ in range(steps):
        pending = [
            row
            for row in store.due_in_states(("PENDING", "DUE", "CLAIMED"))
            if row["schedule_sha256"] == digest
        ]
        due_now = [row for row in pending if parse_utc(row["due_at"]) <= clock()]
        future = [row for row in pending if parse_utc(row["due_at"]) > clock()]
        if not injected and not due_now and future:
            if not wait_future:
                break
            wait_until(clock, min(parse_utc(row["due_at"]) for row in future))
            continue
        if not injected and not due_now and not future:
            break
        last = tick_once(
            root=root,
            data_root=data_root,
            store=store,
            schedule=schedule,
            activation_id=activation_id,
            now=clock(),
            opener=opener,
            producer_git_sha=producer_git_sha,
            discovery_rows=injected,
            clock=clock,
        )
        injected = []
        sleep_clock(clock, 4)
    return last


def _write_live_labels(
    *,
    data_root: Path,
    schedule_sha256: str,
    readout: Mapping[str, Any],
    exclusion: Mapping[str, Any],
    r0_search_sha256: str,
    selected_mints: Sequence[str],
    activation_id: str,
) -> list[str]:
    rebuilt = rebuild_observation_panel_from_rdp(
        data_root=data_root,
        schedule_sha256=schedule_sha256,
    )
    manifest_ids: list[str] = []
    for manifest_id in list(rebuilt.get("dataset_manifest_ids") or []):
        path = Path(data_root) / "datasets" / "manifests" / f"{manifest_id}.labels.json"
        if path.is_file():
            try:
                existing = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise PathRiskLiveError("INCOMPATIBLE_ACTIVATION_BINDING") from exc
            prior = existing.get("activation_id")
            if prior not in {None, activation_id}:
                raise PathRiskLiveError("INCOMPATIBLE_ACTIVATION_BINDING")
        manifest_ids.append(str(manifest_id))
    labels = {
        "activation_id": activation_id,
        "evidence_role": "PATHRISK_CALIBRATION_PANEL",
        "pathrisk_terminal": readout.get("terminal"),
        "readout_sha256": readout.get("readout_sha256"),
        "r0_search_sha256": r0_search_sha256,
        "excluded_mints_sha256": exclusion.get("excluded_mints_sha256"),
        "excluded_mint_count": exclusion.get("excluded_mint_count"),
        "selected_mints": list(selected_mints),
        "ordering": "DETERMINISTIC_MINT_ASC",
        "alpha_claim": False,
        "profitability_claim": False,
        "netreturn_claim": False,
        "outcome_consumed": False,
        "confirmatory_reuse_forbidden": False,
        "non_claims": list(readout.get("non_claims") or []),
    }
    for manifest_id in manifest_ids:
        path = Path(data_root) / "datasets" / "manifests" / f"{manifest_id}.labels.json"
        path.write_text(json.dumps(labels, indent=2, sort_keys=True), encoding="utf-8")
    readout_path = _journal_path(data_root, activation_id).parent / "readout.json"
    readout_path.parent.mkdir(parents=True, exist_ok=True)
    readout_path.write_text(
        json.dumps(dict(readout), indent=2, sort_keys=True, default=str),
        encoding="utf-8",
    )
    return manifest_ids


def _panel_readout(
    *,
    data_root: Path,
    schedule_sha256: str,
    mints: Sequence[str],
    provider_calls: int,
) -> dict[str, Any]:
    rebuilt = rebuild_observation_panel_from_rdp(
        data_root=data_root,
        schedule_sha256=schedule_sha256,
    )
    return build_readout(
        mints=list(mints),
        observations=rebuilt["observations"],
        provider_calls=provider_calls,
    )


def _lifetime_calls(
    store: ObservationScheduleStore,
    schedule: Mapping[str, Any],
    activation_id: str,
) -> int:
    life = store.load_lifetime(
        schedule_sha256=str(schedule["schedule_sha256"]),
        activation_id=activation_id,
    )
    return int(life.get("provider_calls") or 0)


def run_live_window(
    *,
    root: Path,
    data_root: Path,
    opener: object | None = None,
    producer_git_sha: str,
    owner_phrase: str,
    main_sha: str,
    activation_id: str,
    predecessor_activation_id: str,
    now: datetime | None = None,
    stop_after: str | None = None,
    store_path: Path | None = None,
    policy: Mapping[str, Any] | None = None,
    production: bool = False,
    clock: object | None = None,
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    require_exact_main_sha(main_sha)
    loaded_policy = dict(policy or load_policy(root))
    if loaded_policy.get("atom_id") != ATOM_ID:
        raise PathRiskLiveError("ATOM_DRIFT")
    if int(loaded_policy["runtime_limits"]["max_calls"]) != CALL_CAP:
        raise PathRiskLiveError("CALL_CAP_26_NOT_ENFORCEABLE")
    proposed_capture_packet(root=root, main_sha=main_sha, policy=loaded_policy)
    identity = resolve_live_window_identity(
        loaded_policy,
        activation_id,
        predecessor_activation_id,
    )
    require_owner_phrase(loaded_policy, owner_phrase, identity)
    activation_id = identity.activation_id
    if production:
        if now is not None:
            raise PathRiskLiveError("NOW_OVERRIDE_FORBIDDEN_IN_PRODUCTION")
        if stop_after is not None:
            raise PathRiskLiveError("STOP_AFTER_FORBIDDEN_IN_PRODUCTION")
        if isinstance(clock, FrozenClock):
            raise PathRiskLiveError("FROZEN_CLOCK_FORBIDDEN_IN_PRODUCTION")
        if opener is not None:
            raise PathRiskLiveError("OPENER_INJECTION_FORBIDDEN_IN_PRODUCTION")
    data_root = Path(data_root)
    data_root.mkdir(parents=True, exist_ok=True)
    assert_rdp_ready(data_root)
    if clock is None:
        if production:
            clock = SystemClock()
        elif now is not None:
            clock = ControllableClock(now)
        else:
            raise PathRiskLiveError("CLOCK_REQUIRED")
    if production and type(clock) is FrozenClock:
        raise PathRiskLiveError("FROZEN_CLOCK_FORBIDDEN_IN_PRODUCTION")
    assert_predecessor_eligible(data_root, identity)
    journal = load_journal(data_root, activation_id)
    resume_stage = str(journal.get("stage") or "START")
    _assert_existing_journal_identity(data_root, identity, journal)
    assert_no_completed_window(journal)
    exclusion = resolve_consumed_exclusions(
        repo_root=root,
        data_root=data_root,
        policy=loaded_policy,
        resolved_at=clock(),
    )
    schedule = materialize_runtime_schedule(root, data_root, clock(), identity)
    if not prospective_band_derivable(schedule):
        raise PathRiskLiveError("PROSPECTIVE_TIME_ADMISSIBILITY_REQUIRES_SCIENCE_REPLAN")
    _stamp_identity(journal, identity)
    journal["exclusion"] = {
        key: exclusion[key]
        for key in (
            "excluded_mint_count",
            "excluded_mints_sha256",
            "source_refs",
            "source_hashes",
            "resolved_at",
            "exclusion_packet_sha256",
        )
    }
    journal["schedule_sha256"] = schedule["schedule_sha256"]
    save_journal(data_root, activation_id, journal)
    if production:
        try:
            credential = load_process_credential(environ)
        except PathRiskLiveError as exc:
            if str(exc) == TERMINAL_CREDENTIAL_MISSING:
                return {
                    "terminal": TERMINAL_CREDENTIAL_MISSING,
                    "provider_calls": 0,
                    "quote_calls": 0,
                    "credential_reads": 0,
                    "git_mutated": False,
                }
            raise
        opener = JupiterReadonlyOpener(credential)
    if opener is None:
        raise PathRiskLiveError("OPENER_REQUIRED")
    ops_path = store_path or (data_root / "observation_schedule_state.sqlite")
    store = ObservationScheduleStore(ops_path)
    try:
        existing = store.get_activation(str(schedule["schedule_sha256"]), activation_id)
        if existing is None:
            _activate(
                root=root,
                data_root=data_root,
                store=store,
                schedule=schedule,
                now=clock(),
                producer_git_sha=producer_git_sha,
                activation_id=activation_id,
            )
        epoch_before = evidence_epoch_sha256(
            evidence_epoch_material(root, data_root)
        )
        accounts = _accounting(store, schedule, clock(), root, activation_id)
        pace_seconds = int(schedule["budgets"]["min_provider_pace_seconds"])
        capped = opener if isinstance(opener, HardCapOpener) else HardCapOpener(opener)
        recent = _oneshot(
            store=store,
            schedule=schedule,
            primitive_id=DISCOVERY,
            point_id="R0_RECENT",
            due_at=R0_RECENT_DUE,
            url=RECENT_URL,
            opener=capped,
            clock=clock,
            accounts=accounts,
            pace_seconds=pace_seconds,
        )
        journal["stage"] = "RECENT_DONE"
        journal["recent_sha256"] = recent.get("response_sha256")
        journal["recent_reused"] = recent.get("reused")
        save_journal(data_root, activation_id, journal)
        if stop_after == "after_recent":
            return {
                "terminal": "STOPPED_AFTER_RECENT",
                "provider_calls": _lifetime_calls(store, schedule, activation_id),
                "quote_calls": 0,
                "urls": list(capped.urls),
                "exclusion": exclusion,
                "git_mutated": False,
            }
        recent_ids = [
            str(row.get("id") or row.get("mint") or "")
            for row in recent.get("rows") or []
            if isinstance(row, Mapping)
        ]
        recent_ids = [item for item in recent_ids if item]
        if not recent_ids:
            operational = r0_recent_operational_terminal(recent)
            if operational:
                return {
                    "terminal": operational,
                    "http_status": _http_fields(recent)["http_status"],
                    "http_class": _http_fields(recent)["http_class"],
                    "provider_calls": _lifetime_calls(store, schedule, activation_id),
                    "quote_calls": 0,
                    "urls": list(capped.urls),
                    "exclusion": exclusion,
                    "git_mutated": False,
                    "retry": False,
                    "fallback": False,
                    "scientific_outcome": False,
                }
            raise PathRiskLiveError("R0_SINGLE_SNAPSHOT_BINDING_NOT_PROVEN")
        search = _oneshot(
            store=store,
            schedule=schedule,
            primitive_id=SEARCH_PRIMITIVE,
            point_id="R0_SEARCH",
            due_at=R0_SEARCH_DUE,
            url=search_url(recent_ids),
            opener=capped,
            clock=clock,
            accounts=accounts,
            expected_entities=recent_ids,
            pace_seconds=pace_seconds,
        )
        search_hash = search.get("response_sha256")
        if not isinstance(search_hash, str) or len(search_hash) != 64:
            raise PathRiskLiveError("R0_SINGLE_SNAPSHOT_BINDING_NOT_PROVEN")
        journal["stage"] = "R0_BOUND"
        journal["r0_search_sha256"] = search_hash
        journal["search_reused"] = search.get("reused")
        save_journal(data_root, activation_id, journal)
        if stop_after == "after_search":
            return {
                "terminal": "STOPPED_AFTER_SEARCH",
                "provider_calls": _lifetime_calls(store, schedule, activation_id),
                "quote_calls": 0,
                "urls": list(capped.urls),
                "r0_search_sha256": search_hash,
                "exclusion": exclusion,
                "git_mutated": False,
            }
        rows = [row for row in (search.get("rows") or []) if isinstance(row, Mapping)]
        prior_stage = resume_stage
        frozen_stages = {"SAMPLED", "T0_COMPLETE", "H900_PARTIAL"}
        frozen_mints = [
            str(item)
            for item in list(journal.get("selected_mints") or [])
            if item
        ]
        if prior_stage in frozen_stages and frozen_mints:
            sample = {
                "terminal": None,
                "mints": frozen_mints,
                "eligible_count": int(journal.get("eligible_count") or len(frozen_mints)),
            }
        else:
            admissible_rows = [
                row
                for row in rows
                if prospective_time_admissible(row, schedule=schedule, as_of=clock())
            ]
            sample = select_r0_sample(
                admissible_rows,
                policy=loaded_policy,
                as_of=clock(),
                excluded_mints=set(exclusion["mints"]),
            )
            journal["selected_mints"] = list(sample["mints"])
            journal["eligible_count"] = sample["eligible_count"]
            save_journal(data_root, activation_id, journal)
        quote_urls = lambda: [url for url in capped.urls if "/swap/v2/order" in url]
        if sample["terminal"] == TERMINAL_BELOW_FLOOR:
            journal["stage"] = "BELOW_FLOOR"
            journal["terminal"] = TERMINAL_BELOW_FLOOR
            save_journal(data_root, activation_id, journal)
            epoch_after = evidence_epoch_sha256(
                evidence_epoch_material(root, data_root)
            )
            return {
                "terminal": TERMINAL_BELOW_FLOOR,
                "eligible_count": sample["eligible_count"],
                "selected_mints": list(sample["mints"]),
                "quote_calls": 0,
                "provider_calls": _lifetime_calls(store, schedule, activation_id),
                "discovery_calls": len(
                    [
                        url
                        for url in capped.urls
                        if "/tokens/v2/recent" in url or "/tokens/v2/search" in url
                    ]
                ),
                "urls": list(capped.urls),
                "r0_search_sha256": search_hash,
                "exclusion": exclusion,
                "evidence_epoch_before": epoch_before,
                "evidence_epoch_after": epoch_after,
                "evidence_epoch_changed": epoch_after != epoch_before,
                "git_mutated": False,
                "retry": False,
                "fallback": False,
                "non_claims": [
                    "NO_ALPHA",
                    "NO_NETRETURN",
                    "PATHRISK_PROXY_NOT_PROFITABILITY",
                ],
            }
        selected_rows = []
        by_id = {str(row.get("id") or row.get("mint")): row for row in rows}
        for mint in sample["mints"]:
            row = by_id.get(str(mint))
            if not isinstance(row, Mapping):
                raise PathRiskLiveError("R0_SINGLE_SNAPSHOT_BINDING_NOT_PROVEN")
            selected_rows.append(dict(row))
        if prior_stage not in {"T0_COMPLETE", "H900_PARTIAL"}:
            journal["stage"] = "SAMPLED"
            save_journal(data_root, activation_id, journal)
        t0_steps = 4 if stop_after == "during_t0" else 48
        t0_result: dict[str, Any] | None = None
        labeled: list[str] = []
        if prior_stage not in {"T0_COMPLETE", "H900_PARTIAL"}:
            t0_result = _drain_quotes(
                root=root,
                data_root=data_root,
                store=store,
                schedule=schedule,
                opener=capped,
                producer_git_sha=producer_git_sha,
                clock=clock,
                discovery=selected_rows,
                steps=t0_steps,
                wait_future=False,
                activation_id=activation_id,
            )
            t0_readout = _panel_readout(
                data_root=data_root,
                schedule_sha256=str(schedule["schedule_sha256"]),
                mints=list(sample["mints"]),
                provider_calls=_lifetime_calls(store, schedule, activation_id),
            )
            labeled = _write_live_labels(
                data_root=data_root,
                schedule_sha256=str(schedule["schedule_sha256"]),
                readout=t0_readout,
                exclusion=exclusion,
                r0_search_sha256=str(search_hash),
                selected_mints=list(sample["mints"]),
                activation_id=activation_id,
            )
            journal["t0_readout_sha256"] = t0_readout.get("readout_sha256")
            if stop_after != "during_t0":
                journal["stage"] = "T0_COMPLETE"
            save_journal(data_root, activation_id, journal)
        if stop_after in {"after_t0", "during_t0"}:
            return {
                "terminal": (
                    "STOPPED_DURING_T0" if stop_after == "during_t0" else "STOPPED_AFTER_T0"
                ),
                "provider_calls": _lifetime_calls(store, schedule, activation_id),
                "quote_calls": len(quote_urls()),
                "urls": list(capped.urls),
                "selected_mints": list(sample["mints"]),
                "r0_search_sha256": search_hash,
                "exclusion": exclusion,
                "t0_tick": t0_result,
                "labeled_manifests": labeled,
                "git_mutated": False,
            }
        h900_steps = 4 if stop_after == "during_h900" else 48
        if production:
            sys.stderr.write("PATHRISK_LIVE_WAITING_H900\n")
            sys.stderr.flush()
        h900_result = _drain_quotes(
            root=root,
            data_root=data_root,
            store=store,
            schedule=schedule,
            opener=capped,
            producer_git_sha=producer_git_sha,
            clock=clock,
            discovery=[],
            steps=h900_steps,
            wait_future=True,
            activation_id=activation_id,
        )
        if stop_after == "during_h900":
            h900_readout = _panel_readout(
                data_root=data_root,
                schedule_sha256=str(schedule["schedule_sha256"]),
                mints=list(sample["mints"]),
                provider_calls=_lifetime_calls(store, schedule, activation_id),
            )
            labeled = _write_live_labels(
                data_root=data_root,
                schedule_sha256=str(schedule["schedule_sha256"]),
                readout=h900_readout,
                exclusion=exclusion,
                r0_search_sha256=str(search_hash),
                selected_mints=list(sample["mints"]),
                activation_id=activation_id,
            )
            journal["stage"] = "H900_PARTIAL"
            save_journal(data_root, activation_id, journal)
            return {
                "terminal": "STOPPED_DURING_H900",
                "provider_calls": _lifetime_calls(store, schedule, activation_id),
                "quote_calls": len(quote_urls()),
                "urls": list(capped.urls),
                "selected_mints": list(sample["mints"]),
                "r0_search_sha256": search_hash,
                "exclusion": exclusion,
                "labeled_manifests": labeled,
                "git_mutated": False,
            }
        readout = _panel_readout(
            data_root=data_root,
            schedule_sha256=str(schedule["schedule_sha256"]),
            mints=list(sample["mints"]),
            provider_calls=_lifetime_calls(store, schedule, activation_id),
        )
        labeled = _write_live_labels(
            data_root=data_root,
            schedule_sha256=str(schedule["schedule_sha256"]),
            readout=readout,
            exclusion=exclusion,
            r0_search_sha256=str(search_hash),
            selected_mints=list(sample["mints"]),
            activation_id=activation_id,
        )
        journal["stage"] = "COMPLETE"
        journal["terminal"] = readout["terminal"]
        journal["readout_sha256"] = readout.get("readout_sha256")
        journal["dataset_manifest_ids"] = labeled
        save_journal(data_root, activation_id, journal)
        epoch_after = evidence_epoch_sha256(evidence_epoch_material(root, data_root))
        published = list((data_root / "datasets" / "manifests").glob("dataset-*.published"))
        labeled_files = list((data_root / "datasets" / "manifests").glob("dataset-*.labels.json"))
        return {
            "terminal": readout["terminal"],
            "readout": readout,
            "non_claims": list(readout.get("non_claims") or []),
            "selected_mints": list(sample["mints"]),
            "quote_calls": len(quote_urls()),
            "provider_calls": _lifetime_calls(store, schedule, activation_id),
            "urls": list(capped.urls),
            "r0_search_sha256": search_hash,
            "recent_calls": sum(1 for url in capped.urls if "/tokens/v2/recent" in url),
            "search_calls": sum(1 for url in capped.urls if "/tokens/v2/search" in url),
            "exclusion": exclusion,
            "evidence_epoch_before": epoch_before,
            "evidence_epoch_after": epoch_after,
            "evidence_epoch_changed": epoch_after != epoch_before,
            "rdp_manifest_last": bool(published),
            "dataset_manifest_ids": labeled,
            "build_readout_live_wired": bool(readout.get("readout_sha256")),
            "retry": False,
            "fallback": False,
            "git_mutated": False,
            "h900_tick": h900_result,
            "schedule_sha256": schedule["schedule_sha256"],
            "activation_id": activation_id,
            "predecessor_activation_id": identity.predecessor_activation_id,
            "replacement_reason": identity.replacement_reason,
            "all_published_panels_labeled": bool(published)
            and len(labeled_files) >= len(published),
        }
    finally:
        store.close()


def count_url_kinds(urls: Sequence[str]) -> dict[str, int]:
    recent = sum(1 for url in urls if "/tokens/v2/recent" in url)
    search = sum(1 for url in urls if "/tokens/v2/search" in url)
    quotes = sum(1 for url in urls if "/swap/v2/order" in url)
    return {
        "recent": recent,
        "search": search,
        "quotes": quotes,
        "total": recent + search + quotes,
    }


__all__ = [
    "CALL_CAP",
    "CREDENTIAL_ENV_NAME",
    "CONSUMED_ACT002_LIVE_OWNER_PHRASE",
    "CONSUMED_LIVE_OWNER_PHRASE",
    "FORBIDDEN_SEARCH_BUNDLE",
    "SUCCESSOR_REASON_MARKET_SUPPLY_RETRY",
    "ControllableClock",
    "FixtureWindowOpener",
    "HardCapOpener",
    "LIVE_SCHEDULE_RELATIVE",
    "LiveWindowIdentity",
    "PathRiskLiveError",
    "SystemClock",
    "TERMINAL_CREDENTIAL_MISSING",
    "assert_predecessor_eligible",
    "compile_live_schedule",
    "count_url_kinds",
    "load_successor_identity_policy",
    "materialize_runtime_schedule",
    "prospective_time_admissible",
    "render_successor_owner_phrase",
    "resolve_consumed_exclusions",
    "resolve_live_window_identity",
    "runtime_live_dir",
    "run_live_window",
    "run_transport_probe_recent",
    "successor_preflight",
    "transport_probe_owner_phrase",
]
