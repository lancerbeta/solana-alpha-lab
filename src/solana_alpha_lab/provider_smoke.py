"""Fail-closed offline runtime boundary for TASK-07 provider smoke."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, TypeAlias

import yaml
from solders.pubkey import Pubkey
from solders.signature import Signature

from solana_alpha_lab.contracts.schema_v1 import RawApiEvent, RawResponseStatus
from solana_alpha_lab.storage.raw_envelope import (
    build_raw_api_event,
    canonical_redacted_bytes,
)

JsonValue: TypeAlias = (
    None | bool | int | float | str | list["JsonValue"] | dict[str, "JsonValue"]
)

RUNTIME_CONTRACT_VERSION = "1.0"
RUNTIME_EVIDENCE_AS_OF = "2026-07-24T03:42:09.018Z"
FROZEN_SPEC_SHA256 = (
    "a42c8a20dc31101ce134e277e1a612539f7161411ea8261bb109e5cc64d24ddc"
)
NETWORK_DISABLED_BY_DEFAULT = True

EXPECTED_CASE_COUNT = 34
EXPECTED_ATTEMPT_COUNT = 35
EXPECTED_HARD_ATTEMPT_CAP = 50
EXPECTED_STOP_HEADROOM = 5
EXPECTED_MAX_RESPONSE_BYTES = 2_000_000
EXPECTED_MAX_TOTAL_RESPONSE_BYTES = 20_000_000
EXPECTED_HELIUS_CREDIT_CAP = 25
EXPECTED_TERMINAL_CLASSES = frozenset(
    {
        "SUCCESS",
        "TIMEOUT",
        "DNS_OR_TLS",
        "AUTH",
        "RATE_LIMIT_429",
        "PROVIDER_4XX",
        "PROVIDER_5XX",
        "INVALID_REQUEST",
        "NO_ROUTE",
        "EMPTY_VALID",
        "MALFORMED_PAYLOAD",
        "SCHEMA_DRIFT",
        "RESPONSE_TOO_LARGE",
        "PROHIBITED_PAYLOAD",
        "STOP_CAP",
    }
)

_DYNAMIC_REFERENCE_RE = re.compile(r"\$\{([A-Z][A-Z0-9_]*)\}")


class SmokeContractError(ValueError):
    """The frozen design or runtime claim violates the bounded contract."""


class NetworkDisabledError(SmokeContractError):
    """A caller attempted execution without the separate runtime gate."""


class ProhibitedPayloadError(SmokeContractError):
    """A request or response reached a transaction, payment or secret path."""


class StopConditionError(SmokeContractError):
    """A deterministic run cap or provider stop condition was reached."""


@dataclass(frozen=True, slots=True)
class ProviderRuntimePolicy:
    provider: str
    pacing_group: str
    minimum_interval_seconds: float
    account_required: bool
    auth_mode: str
    role: str
    credit_cap: int | None = None


PROVIDER_POLICIES: dict[str, ProviderRuntimePolicy] = {
    "HELIUS_RPC": ProviderRuntimePolicy(
        provider="HELIUS_RPC",
        pacing_group="HELIUS",
        minimum_interval_seconds=0.2,
        account_required=True,
        auth_mode="LOCAL_ENV_API_KEY",
        role="READ_ONLY_RPC",
        credit_cap=EXPECTED_HELIUS_CREDIT_CAP,
    ),
    "HELIUS_WSS": ProviderRuntimePolicy(
        provider="HELIUS_WSS",
        pacing_group="HELIUS",
        minimum_interval_seconds=0.2,
        account_required=True,
        auth_mode="LOCAL_ENV_API_KEY",
        role="BOUNDED_READ_ONLY_WSS",
        credit_cap=EXPECTED_HELIUS_CREDIT_CAP,
    ),
    "SOLANA_TRACKER_DATA": ProviderRuntimePolicy(
        provider="SOLANA_TRACKER_DATA",
        pacing_group="SOLANA_TRACKER",
        minimum_interval_seconds=0.4,
        account_required=True,
        auth_mode="LOCAL_HEADER_X_API_KEY",
        role="INDEXED_COMPARISON",
    ),
    "JUPITER_SWAP": ProviderRuntimePolicy(
        provider="JUPITER_SWAP",
        pacing_group="JUPITER",
        minimum_interval_seconds=2.2,
        account_required=False,
        auth_mode="KEYLESS",
        role="QUOTE_ONLY_PRIMARY",
    ),
    "RAPTOR_HOSTED": ProviderRuntimePolicy(
        provider="RAPTOR_HOSTED",
        pacing_group="RAPTOR",
        minimum_interval_seconds=1.0,
        account_required=False,
        auth_mode="KEYLESS_RECHECK_AT_RUNTIME",
        role="COMPARATOR_ONLY",
    ),
}


def _normalize_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.casefold())


_FORBIDDEN_REQUEST_KEYS = frozenset(
    _normalize_key(value)
    for value in (
        "taker",
        "payer",
        "receiver",
        "referralAccount",
        "feeAccount",
        "tipAccount",
        "jitoTipLamports",
        "priorityFeeLamports_override",
        "signedTransaction",
        "transaction",
        "privateKey",
        "seed",
    )
)
_TRANSACTION_RESPONSE_KEYS = frozenset(
    _normalize_key(value)
    for value in (
        "transaction",
        "signedTransaction",
        "swapTransaction",
    )
)
_PAYMENT_RESPONSE_KEYS = frozenset(
    _normalize_key(value)
    for value in (
        "paymentRecipient",
        "paymentSignature",
        "paymentChallenge",
        "x402",
        "payTo",
    )
)
_SECRET_REQUEST_KEYS = frozenset(
    _normalize_key(value)
    for value in (
        "authorization",
        "x-api-key",
        "api_key",
        "token",
        "cookie",
        "private_endpoint",
    )
)


@dataclass(frozen=True, slots=True)
class SmokeCase:
    case_id: str
    provider: str
    request_class: str
    method: str
    path: str
    template: dict[str, JsonValue]
    dependencies: tuple[str, ...]
    output_binding: str | None
    planned_attempts: int
    assertion_sets: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SmokePlan:
    cases: tuple[SmokeCase, ...]
    attempt_ids: tuple[str, ...]
    public_bindings: dict[str, JsonValue]
    output_producers: dict[str, str]
    spec_sha256: str
    hard_attempt_cap: int
    stop_headroom_attempts: int
    max_response_bytes_per_attempt: int
    max_total_response_bytes: int

    @property
    def case_by_id(self) -> dict[str, SmokeCase]:
        return {case.case_id: case for case in self.cases}


def _mapping(name: str, value: object) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise SmokeContractError(f"{name}_must_be_mapping")
    if not all(isinstance(key, str) for key in value):
        raise SmokeContractError(f"{name}_keys_must_be_text")
    return value


def _sequence(name: str, value: object) -> Sequence[Any]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise SmokeContractError(f"{name}_must_be_sequence")
    return value


def _integer(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise SmokeContractError(f"{name}_must_be_integer")
    return value


def _json_value(name: str, value: object) -> JsonValue:
    try:
        encoded = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        decoded = json.loads(encoded)
    except (TypeError, ValueError) as exc:
        raise SmokeContractError(f"{name}_must_be_json") from exc
    return decoded


def _dynamic_references(value: JsonValue) -> set[str]:
    if isinstance(value, str):
        return set(_DYNAMIC_REFERENCE_RE.findall(value))
    if isinstance(value, list):
        result: set[str] = set()
        for item in value:
            result.update(_dynamic_references(item))
        return result
    if isinstance(value, dict):
        result = set()
        for key, item in value.items():
            result.update(_DYNAMIC_REFERENCE_RE.findall(key))
            result.update(_dynamic_references(item))
        return result
    return set()


def _contains_dependency(
    case_id: str,
    dependency: str,
    cases: Mapping[str, SmokeCase],
    seen: frozenset[str] = frozenset(),
) -> bool:
    if case_id in seen:
        raise SmokeContractError("dependency_cycle")
    case = cases[case_id]
    if dependency in case.dependencies:
        return True
    return any(
        _contains_dependency(
            candidate,
            dependency,
            cases,
            seen | {case_id},
        )
        for candidate in case.dependencies
    )


def load_frozen_smoke_plan(path: Path) -> SmokePlan:
    """Verify and compile the exact historical design without external I/O."""

    if not isinstance(path, Path):
        raise SmokeContractError("spec_path_must_be_path")
    payload = path.read_bytes()
    actual_hash = hashlib.sha256(payload).hexdigest()
    if actual_hash != FROZEN_SPEC_SHA256:
        raise SmokeContractError("frozen_spec_hash_mismatch")
    try:
        document = yaml.safe_load(payload)
    except yaml.YAMLError as exc:
        raise SmokeContractError("frozen_spec_yaml_invalid") from exc
    return compile_smoke_spec(document, spec_sha256=actual_hash)


def compile_smoke_spec(
    document: object,
    *,
    spec_sha256: str = FROZEN_SPEC_SHA256,
) -> SmokePlan:
    """Compile the frozen mapping into one exact deterministic attempt plan."""

    root = _mapping("spec", document)
    if root.get("schema_version") != "1.0.0":
        raise SmokeContractError("unexpected_spec_schema_version")
    artifact = _mapping("artifact", root.get("artifact"))
    if artifact.get("artifact_id") != "SMIAL_TASK_01_PROVIDER_SMOKE_SPEC":
        raise SmokeContractError("unexpected_artifact_id")
    if artifact.get("artifact_status") != "VALIDATED_FROZEN_DESIGN":
        raise SmokeContractError("frozen_design_not_validated")
    if artifact.get("execution_owner_task") != "TASK-07":
        raise SmokeContractError("unexpected_execution_owner")
    if artifact.get("execution_status") != "NOT_EXECUTED":
        raise SmokeContractError("historical_design_already_executed")

    budget = _mapping("global_budget", root.get("global_budget"))
    expected_budget = {
        "planned_case_count": EXPECTED_CASE_COUNT,
        "planned_attempt_count": EXPECTED_ATTEMPT_COUNT,
        "hard_attempt_cap": EXPECTED_HARD_ATTEMPT_CAP,
        "cash_cap_usd": 0,
        "paid_requests_allowed": False,
        "concurrency": 1,
        "max_retries_per_case": 0,
        "max_response_bytes_per_attempt": EXPECTED_MAX_RESPONSE_BYTES,
        "max_total_response_bytes": EXPECTED_MAX_TOTAL_RESPONSE_BYTES,
        "stop_before_cap_headroom_attempts": EXPECTED_STOP_HEADROOM,
        "default_timeout_seconds": 10,
        "max_timeout_seconds": 20,
        "rate_limit_probe_by_intent": "prohibited",
        "websocket_max_connections": 1,
        "websocket_max_open_seconds": 10,
        "websocket_max_data_messages": 1,
    }
    for key, expected in expected_budget.items():
        if budget.get(key) != expected:
            raise SmokeContractError(f"unexpected_budget_{key}")

    security = _mapping("security_boundary", root.get("security_boundary"))
    methods = tuple(
        str(item)
        for item in _sequence(
            "allowed_http_methods",
            security.get("allowed_http_methods"),
        )
    )
    if set(methods) != {"GET", "POST_JSON_RPC_READ_ONLY"}:
        raise SmokeContractError("unexpected_allowed_method_set")
    frozen_forbidden = {
        _normalize_key(str(item))
        for item in _sequence(
            "forbidden_request_fields",
            security.get("forbidden_request_fields"),
        )
    }
    if frozen_forbidden != _FORBIDDEN_REQUEST_KEYS:
        raise SmokeContractError("forbidden_request_fields_drift")

    failure_taxonomy = _mapping(
        "failure_taxonomy",
        root.get("failure_taxonomy"),
    )
    terminal_classes = frozenset(
        str(item)
        for item in _sequence(
            "failure_taxonomy.terminal_classes",
            failure_taxonomy.get("terminal_classes"),
        )
    )
    if terminal_classes != EXPECTED_TERMINAL_CLASSES:
        raise SmokeContractError("failure_taxonomy_drift")
    if failure_taxonomy.get("persist_every_attempt") is not True:
        raise SmokeContractError("failure_persistence_disabled")
    if failure_taxonomy.get("missing_is_zero") is not False:
        raise SmokeContractError("missing_zero_conflation")
    if failure_taxonomy.get("provider_failure_is_market_no_route") is not False:
        raise SmokeContractError("provider_failure_no_route_conflation")

    safe_samples = _mapping("safe_samples", root.get("safe_samples"))
    public_bindings: dict[str, JsonValue] = {}
    declared_bindings: set[str] = set()
    for name, raw_sample in safe_samples.items():
        sample = _mapping(f"safe_samples.{name}", raw_sample)
        declared_bindings.add(name)
        if sample.get("state") == "FROZEN":
            public_bindings[name] = _json_value(
                f"safe_samples.{name}.value",
                sample.get("value"),
            )

    raw_cases = _sequence("cases", root.get("cases"))
    if len(raw_cases) != EXPECTED_CASE_COUNT:
        raise SmokeContractError("case_count_mismatch")

    cases_by_id: dict[str, SmokeCase] = {}
    case_declaration_order: list[str] = []
    output_producers: dict[str, str] = {}
    for raw_case in raw_cases:
        item = _mapping("case", raw_case)
        case_id = item.get("case_id")
        provider = item.get("provider")
        request_class = item.get("request_class")
        method = item.get("method")
        path = item.get("path")
        if not all(
            isinstance(value, str) and value
            for value in (case_id, provider, request_class, method, path)
        ):
            raise SmokeContractError("case_identity_invalid")
        assert isinstance(case_id, str)
        assert isinstance(provider, str)
        assert isinstance(request_class, str)
        assert isinstance(method, str)
        assert isinstance(path, str)
        if case_id in cases_by_id:
            raise SmokeContractError("duplicate_case_id")
        if provider not in PROVIDER_POLICIES:
            raise SmokeContractError("unknown_provider")
        if method not in methods:
            raise SmokeContractError("method_not_allowed")
        if not path.startswith("/") or "://" in path:
            raise SmokeContractError("path_must_be_relative")

        template_keys = (
            "rpc_method",
            "rpc_method_sequence",
            "params",
            "query",
            "limits",
            "expected_terminal",
        )
        template: dict[str, JsonValue] = {
            key: _json_value(f"{case_id}.{key}", item[key])
            for key in template_keys
            if key in item
        }
        template.update(
            {
                "case_id": case_id,
                "method": method,
                "path": path,
                "provider": provider,
                "request_class": request_class,
            }
        )
        dependencies = tuple(
            str(value)
            for value in _sequence(
                f"{case_id}.depends_on",
                item.get("depends_on"),
            )
        )
        assertions = tuple(
            str(value)
            for value in _sequence(
                f"{case_id}.assertion_sets",
                item.get("assertion_sets"),
            )
        )
        planned_attempts = _integer(
            f"{case_id}.planned_attempts",
            item.get("planned_attempts", 1),
        )
        if planned_attempts < 1:
            raise SmokeContractError("planned_attempts_must_be_positive")
        output_binding = item.get("output_binding")
        if output_binding is not None:
            if not isinstance(output_binding, str) or not output_binding:
                raise SmokeContractError("output_binding_invalid")
            if output_binding in output_producers:
                raise SmokeContractError("duplicate_output_binding")
            output_producers[output_binding] = case_id
        case = SmokeCase(
            case_id=case_id,
            provider=provider,
            request_class=request_class,
            method=method,
            path=path,
            template=template,
            dependencies=dependencies,
            output_binding=output_binding,
            planned_attempts=planned_attempts,
            assertion_sets=assertions,
        )
        _assert_request_template_safe(template)
        cases_by_id[case_id] = case
        case_declaration_order.append(case_id)

    run_order_groups = _sequence("run_order", root.get("run_order"))
    run_order = tuple(
        str(case_id)
        for group in run_order_groups
        for case_id in _sequence("run_order_group", group)
    )
    if run_order != tuple(case_declaration_order):
        raise SmokeContractError("run_order_mismatch")
    if len(set(run_order)) != len(run_order):
        raise SmokeContractError("run_order_duplicate")

    positions = {case_id: index for index, case_id in enumerate(run_order)}
    for case in cases_by_id.values():
        for dependency in case.dependencies:
            if dependency not in cases_by_id:
                raise SmokeContractError("unknown_case_dependency")
            if positions[dependency] >= positions[case.case_id]:
                raise SmokeContractError("dependency_not_before_consumer")

    derived_bindings = {"RECENT_PUMP_SELL_AMOUNT_ATOMIC"}
    known_bindings = declared_bindings | set(output_producers) | derived_bindings
    for case in cases_by_id.values():
        references = _dynamic_references(case.template)
        if not references.issubset(known_bindings):
            raise SmokeContractError("unknown_dynamic_binding")
        for reference in references & set(output_producers):
            producer = output_producers[reference]
            if not _contains_dependency(case.case_id, producer, cases_by_id):
                raise SmokeContractError("dynamic_binding_dependency_missing")
        if "RECENT_PUMP_SELL_AMOUNT_ATOMIC" in references:
            decimals_producer = output_producers.get("RECENT_PUMP_DECIMALS")
            if decimals_producer is None or not _contains_dependency(
                case.case_id,
                decimals_producer,
                cases_by_id,
            ):
                raise SmokeContractError("sell_amount_dependency_missing")

    attempt_ids = tuple(
        f"{case_id}#{index}"
        for case_id in run_order
        for index in range(1, cases_by_id[case_id].planned_attempts + 1)
    )
    if len(attempt_ids) != EXPECTED_ATTEMPT_COUNT:
        raise SmokeContractError("attempt_count_mismatch")
    h12 = cases_by_id["H12"]
    if h12.planned_attempts != 2 or h12.template.get("limits") != {
        "max_data_messages": 1,
        "max_open_seconds": 10,
    }:
        raise SmokeContractError("wss_case_limits_drift")

    return SmokePlan(
        cases=tuple(cases_by_id[case_id] for case_id in run_order),
        attempt_ids=attempt_ids,
        public_bindings=public_bindings,
        output_producers=output_producers,
        spec_sha256=spec_sha256,
        hard_attempt_cap=_integer(
            "hard_attempt_cap",
            budget.get("hard_attempt_cap"),
        ),
        stop_headroom_attempts=_integer(
            "stop_headroom_attempts",
            budget.get("stop_before_cap_headroom_attempts"),
        ),
        max_response_bytes_per_attempt=_integer(
            "max_response_bytes_per_attempt",
            budget.get("max_response_bytes_per_attempt"),
        ),
        max_total_response_bytes=_integer(
            "max_total_response_bytes",
            budget.get("max_total_response_bytes"),
        ),
    )


def _assert_request_template_safe(value: JsonValue) -> None:
    if isinstance(value, list):
        for item in value:
            _assert_request_template_safe(item)
        return
    if not isinstance(value, dict):
        return
    for key, item in value.items():
        normalized = _normalize_key(key)
        if normalized in _FORBIDDEN_REQUEST_KEYS:
            raise ProhibitedPayloadError("forbidden_request_field")
        if normalized in _SECRET_REQUEST_KEYS:
            raise ProhibitedPayloadError("credential_field_in_request_template")
        _assert_request_template_safe(item)


def _materialize_value(
    value: JsonValue,
    bindings: Mapping[str, JsonValue],
) -> JsonValue:
    if isinstance(value, str):
        exact = _DYNAMIC_REFERENCE_RE.fullmatch(value)
        if exact is not None:
            name = exact.group(1)
            if name not in bindings:
                raise SmokeContractError(f"binding_missing:{name}")
            return _json_value(f"binding.{name}", bindings[name])

        def replace(match: re.Match[str]) -> str:
            name = match.group(1)
            if name not in bindings:
                raise SmokeContractError(f"binding_missing:{name}")
            replacement = bindings[name]
            if isinstance(replacement, (dict, list)) or replacement is None:
                raise SmokeContractError(f"binding_not_scalar:{name}")
            return str(replacement)

        return _DYNAMIC_REFERENCE_RE.sub(replace, value)
    if isinstance(value, list):
        return [_materialize_value(item, bindings) for item in value]
    if isinstance(value, dict):
        return {
            key: _materialize_value(item, bindings)
            for key, item in value.items()
        }
    return value


def materialize_case(
    plan: SmokePlan,
    case_id: str,
    *,
    produced_bindings: Mapping[str, JsonValue] | None = None,
) -> dict[str, JsonValue]:
    """Resolve one planned request using only frozen or produced bindings."""

    if not isinstance(plan, SmokePlan):
        raise SmokeContractError("plan_must_be_smoke_plan")
    try:
        case = plan.case_by_id[case_id]
    except KeyError as exc:
        raise SmokeContractError("unknown_case_id") from exc
    bindings = dict(plan.public_bindings)
    if produced_bindings is not None:
        for name, value in produced_bindings.items():
            if name not in plan.output_producers:
                raise SmokeContractError(f"undeclared_produced_binding:{name}")
            safe_value = _json_value(f"binding.{name}", value)
            if name == "RECENT_PUMP_MINT":
                if not isinstance(safe_value, str):
                    raise SmokeContractError("recent_pump_mint_must_be_text")
                try:
                    Pubkey.from_string(safe_value)
                except ValueError as exc:
                    raise SmokeContractError(
                        "recent_pump_mint_invalid"
                    ) from exc
            elif name == "RAPTOR_RECENT_SIGNATURE":
                if not isinstance(safe_value, str):
                    raise SmokeContractError(
                        "raptor_recent_signature_must_be_text"
                    )
                try:
                    Signature.from_string(safe_value)
                except ValueError as exc:
                    raise SmokeContractError(
                        "raptor_recent_signature_invalid"
                    ) from exc
            elif name == "RECENT_PUMP_DECIMALS":
                if (
                    isinstance(safe_value, bool)
                    or not isinstance(safe_value, int)
                    or not 0 <= safe_value <= 18
                ):
                    raise SmokeContractError(
                        "recent_pump_decimals_out_of_range"
                    )
            bindings[name] = safe_value

    if (
        "RECENT_PUMP_SELL_AMOUNT_ATOMIC" not in bindings
        and "RECENT_PUMP_DECIMALS" in bindings
    ):
        decimals = bindings["RECENT_PUMP_DECIMALS"]
        if isinstance(decimals, bool) or not isinstance(decimals, int):
            raise SmokeContractError("recent_pump_decimals_must_be_integer")
        if not 0 <= decimals <= 18:
            raise SmokeContractError("recent_pump_decimals_out_of_range")
        bindings["RECENT_PUMP_SELL_AMOUNT_ATOMIC"] = max(1, 10**decimals)

    materialized = _materialize_value(case.template, bindings)
    assert isinstance(materialized, dict)
    _assert_request_template_safe(materialized)
    if _dynamic_references(materialized):
        raise SmokeContractError("unresolved_dynamic_binding")
    return materialized


def _payload_bytes(payload: bytes | str | Mapping[str, Any]) -> bytes:
    if isinstance(payload, bytes):
        return payload
    if isinstance(payload, str):
        return payload.encode("utf-8")
    if isinstance(payload, Mapping):
        return json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    raise SmokeContractError("response_payload_type_invalid")


def _parse_response(payload: bytes) -> JsonValue | None:
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ProhibitedPayloadError("response_not_utf8") from exc
    stripped = text.strip()
    if not stripped:
        return None
    if not stripped.startswith(("{", "[")):
        return text
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        return text


def _typed_error_present(mapping: Mapping[str, JsonValue]) -> bool:
    for key, value in mapping.items():
        if _normalize_key(key) == "errorcode":
            return isinstance(value, (str, int)) and not isinstance(value, bool) and (
                str(value).strip() != ""
            )
    return False


def _assert_response_safe(value: JsonValue, *, quote_only: bool) -> None:
    if isinstance(value, list):
        for item in value:
            _assert_response_safe(item, quote_only=quote_only)
        return
    if isinstance(value, str):
        if re.search(
            r"(?i)(paymentRecipient|paymentSignature|paymentChallenge|x402|payTo)"
            r"[\"']?\s*[:=]",
            value,
        ):
            raise ProhibitedPayloadError("payment_or_x402_payload")
        if quote_only and re.search(
            r"(?i)(transaction|signedTransaction|swapTransaction)"
            r"[\"']?\s*[:=]",
            value,
        ):
            raise ProhibitedPayloadError(
                "uninspectable_transaction_payload"
            )
        return
    if not isinstance(value, dict):
        return
    typed_error = _typed_error_present(value)
    for key, item in value.items():
        normalized = _normalize_key(key)
        if normalized in _PAYMENT_RESPONSE_KEYS and item not in (None, ""):
            raise ProhibitedPayloadError("payment_or_x402_payload")
        if quote_only and normalized in _TRANSACTION_RESPONSE_KEYS:
            if item is None:
                continue
            if isinstance(item, str) and item == "" and typed_error:
                continue
            raise ProhibitedPayloadError("nonempty_transaction_payload")
        _assert_response_safe(item, quote_only=quote_only)


def validate_response_payload(
    plan: SmokePlan,
    case_id: str,
    payload: bytes | str | Mapping[str, Any],
    *,
    explicit_secret_values: Sequence[str | bytes] = (),
) -> bytes:
    """Apply size, transaction/payment and TASK-06 redaction gates."""

    if case_id not in plan.case_by_id:
        raise SmokeContractError("unknown_case_id")
    original = _payload_bytes(payload)
    if len(original) > plan.max_response_bytes_per_attempt:
        raise StopConditionError("response_too_large")
    parsed = _parse_response(original)
    if parsed is not None:
        case = plan.case_by_id[case_id]
        _assert_response_safe(
            parsed,
            quote_only="QUOTE_BASE" in case.assertion_sets,
        )
    redacted = canonical_redacted_bytes(
        original,
        explicit_secret_values=explicit_secret_values,
    )
    if len(redacted) > plan.max_response_bytes_per_attempt:
        raise StopConditionError("redacted_response_too_large")
    return redacted


def build_attempt_raw_event(
    plan: SmokePlan,
    *,
    case_id: str,
    materialized_request: Mapping[str, Any],
    response_body: bytes | str | Mapping[str, Any],
    response_status: RawResponseStatus | str,
    error_class: str | None,
    observed_at: datetime,
    available_to_strategy_at: datetime,
    ingested_at: datetime,
    first_reliable_available_at: datetime,
    event_time: datetime | None = None,
    explicit_secret_values: Sequence[str | bytes] = (),
) -> RawApiEvent:
    """Prepare one TASK-06 raw event without persisting or calling a provider."""

    try:
        case = plan.case_by_id[case_id]
    except KeyError as exc:
        raise SmokeContractError("unknown_case_id") from exc
    expected_request = _json_value("materialized_request", materialized_request)
    assert isinstance(expected_request, dict)
    _assert_request_template_safe(expected_request)
    if set(expected_request) != set(case.template):
        raise SmokeContractError("request_shape_mismatch")
    expected_identity = {
        "case_id": case.case_id,
        "method": case.method,
        "path": case.path,
        "provider": case.provider,
        "request_class": case.request_class,
    }
    for name, value in expected_identity.items():
        if expected_request.get(name) != value:
            raise SmokeContractError(f"request_{name}_mismatch")
    if _dynamic_references(expected_request):
        raise SmokeContractError("request_contains_unresolved_binding")
    safe_body = validate_response_payload(
        plan,
        case_id,
        response_body,
        explicit_secret_values=explicit_secret_values,
    )
    return build_raw_api_event(
        source=case.provider,
        source_version=f"task07-runtime-{RUNTIME_CONTRACT_VERSION}",
        endpoint_or_method=f"{case.method} {case.path}",
        request_identity=expected_request,
        response_body=safe_body,
        response_status=response_status,
        error_class=error_class,
        observed_at=observed_at,
        available_to_strategy_at=available_to_strategy_at,
        ingested_at=ingested_at,
        first_reliable_available_at=first_reliable_available_at,
        event_time=event_time,
        provider_version=f"evidence-as-of-{RUNTIME_EVIDENCE_AS_OF}",
        schema_version="1.0",
        protocol_version="task07-smoke-1.0",
        quality_flags="task07_controlled_smoke",
        explicit_secret_values=explicit_secret_values,
    )


class SmokeRunGuard:
    """Offline state machine for attempt, pacing, byte, cash and credit caps."""

    def __init__(
        self,
        plan: SmokePlan,
        *,
        network_authorized: bool = False,
    ) -> None:
        if not isinstance(plan, SmokePlan):
            raise SmokeContractError("plan_must_be_smoke_plan")
        self.plan = plan
        self.network_authorized = network_authorized
        self._started: dict[str, float] = {}
        self._completed: set[str] = set()
        self._last_started_by_group: dict[str, float] = {}
        self._response_bytes_total = 0
        self._helius_credits = 0
        self._cash_spend_usd = 0.0
        self._consecutive_failures: dict[str, int] = {}
        self._stopped_groups: set[str] = set()

    @property
    def attempt_count(self) -> int:
        return len(self._started)

    @property
    def response_bytes_total(self) -> int:
        return self._response_bytes_total

    @property
    def helius_credits(self) -> int:
        return self._helius_credits

    @property
    def cash_spend_usd(self) -> float:
        return self._cash_spend_usd

    def authorize_attempt(
        self,
        attempt_id: str,
        *,
        monotonic_seconds: float,
    ) -> SmokeCase:
        if not self.network_authorized:
            raise NetworkDisabledError("network_disabled_by_default")
        if attempt_id not in self.plan.attempt_ids:
            raise SmokeContractError("unplanned_attempt")
        if attempt_id in self._started:
            raise StopConditionError("retry_or_duplicate_attempt_forbidden")
        if len(self._started) != len(self._completed):
            raise StopConditionError("concurrency_one_attempt_still_open")
        if self.attempt_count >= len(self.plan.attempt_ids):
            raise StopConditionError("planned_attempts_exhausted")
        expected_attempt_id = self.plan.attempt_ids[self.attempt_count]
        if attempt_id != expected_attempt_id:
            raise StopConditionError("attempt_order_mismatch")
        effective_cap = (
            self.plan.hard_attempt_cap - self.plan.stop_headroom_attempts
        )
        if self.attempt_count >= effective_cap:
            raise StopConditionError("attempt_headroom_reached")
        if not isinstance(monotonic_seconds, (int, float)):
            raise SmokeContractError("monotonic_seconds_must_be_numeric")

        case_id = attempt_id.rsplit("#", 1)[0]
        case = self.plan.case_by_id[case_id]
        policy = PROVIDER_POLICIES[case.provider]
        group = policy.pacing_group
        if group in self._stopped_groups:
            raise StopConditionError("provider_group_stopped")
        previous = self._last_started_by_group.get(group)
        if (
            previous is not None
            and monotonic_seconds - previous + 1e-12
            < policy.minimum_interval_seconds
        ):
            raise StopConditionError("provider_pacing_interval_not_met")

        self._started[attempt_id] = float(monotonic_seconds)
        self._last_started_by_group[group] = float(monotonic_seconds)
        return case

    def record_attempt(
        self,
        attempt_id: str,
        *,
        response_size_bytes: int,
        terminal_class: str,
        credit_cost: int = 0,
        cash_cost_usd: float = 0.0,
    ) -> None:
        if attempt_id not in self._started:
            raise SmokeContractError("attempt_not_authorized")
        if attempt_id in self._completed:
            raise StopConditionError("attempt_already_recorded")
        if (
            isinstance(response_size_bytes, bool)
            or not isinstance(response_size_bytes, int)
            or response_size_bytes < 0
        ):
            raise SmokeContractError("response_size_invalid")
        if response_size_bytes > self.plan.max_response_bytes_per_attempt:
            raise StopConditionError("response_too_large")
        if (
            self._response_bytes_total + response_size_bytes
            > self.plan.max_total_response_bytes
        ):
            raise StopConditionError("total_response_bytes_exceeded")
        if (
            isinstance(credit_cost, bool)
            or not isinstance(credit_cost, int)
            or credit_cost < 0
        ):
            raise SmokeContractError("credit_cost_invalid")
        if not isinstance(cash_cost_usd, (int, float)) or isinstance(
            cash_cost_usd,
            bool,
        ):
            raise SmokeContractError("cash_cost_invalid")
        if terminal_class not in EXPECTED_TERMINAL_CLASSES:
            raise SmokeContractError("unknown_terminal_class")
        if cash_cost_usd != 0:
            raise StopConditionError("cash_spend_forbidden")

        case_id = attempt_id.rsplit("#", 1)[0]
        case = self.plan.case_by_id[case_id]
        group = PROVIDER_POLICIES[case.provider].pacing_group
        if group == "HELIUS":
            if self._helius_credits + credit_cost > EXPECTED_HELIUS_CREDIT_CAP:
                raise StopConditionError("helius_credit_cap_exceeded")
            self._helius_credits += credit_cost
        elif credit_cost != 0:
            raise SmokeContractError("credit_cost_unmodeled_for_provider")

        self._response_bytes_total += response_size_bytes
        self._cash_spend_usd += float(cash_cost_usd)
        self._completed.add(attempt_id)
        if terminal_class == "SUCCESS":
            self._consecutive_failures[group] = 0
            return
        failures = self._consecutive_failures.get(group, 0) + 1
        self._consecutive_failures[group] = failures
        if failures >= 3:
            self._stopped_groups.add(group)
            raise StopConditionError("three_consecutive_provider_failures")
