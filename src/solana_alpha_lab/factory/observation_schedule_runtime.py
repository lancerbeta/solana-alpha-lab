"""Credential-free ObservationSchedule runtime configuration."""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any
from urllib.parse import parse_qs, urlsplit

import jsonschema
import yaml

from solana_alpha_lab.factory.observation_schedule import parse_utc

SCHEMA_RELATIVE = "catalog/schemas/observation_schedule_runtime_v1.schema.json"
DEFAULT_RUNTIME_RELATIVE = "configs/observation_schedule_runtime_v1.yaml"
SAFE_CONFIG_PREFIXES = (
    "configs/",
    "tests/fixtures/observation_schedule/",
    "local/",
)
UNIT_RELATIVE = "configs/factory_remote_ops/factory-observation-schedule.service"
ALLOWED_CREDENTIAL_ENV = frozenset({"JUPITER_FREE_API_KEY"})


class ObservationRuntimeError(ValueError):
    """Typed runtime-config failure."""


def _safe_relative(root: Path, relative: str) -> Path:
    path = Path(relative)
    posix = PurePosixPath(relative)
    windows = PureWindowsPath(relative)
    if (
        path.is_absolute()
        or posix.is_absolute()
        or windows.is_absolute()
        or bool(windows.drive)
        or ".." in posix.parts
        or ".." in windows.parts
    ):
        raise ObservationRuntimeError("PATH_UNSAFE")
    normalized = relative.replace("\\", "/")
    if not normalized.startswith(SAFE_CONFIG_PREFIXES):
        raise ObservationRuntimeError("PATH_UNSAFE")
    root_resolved = root.resolve()
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root_resolved)
    except ValueError as exc:
        raise ObservationRuntimeError("PATH_UNSAFE") from exc
    return candidate


def parse_unit_exec_start(unit_text: str) -> list[str]:
    match = re.search(r"^ExecStart=(.+)$", unit_text, re.MULTILINE)
    if match is None:
        raise ObservationRuntimeError("EXECSTART_MISSING")
    raw = match.group(1).strip()
    raw = raw.replace(
        "${OBSERVATION_SCHEDULE_RUNTIME_CONFIG}",
        os.environ.get("OBSERVATION_SCHEDULE_RUNTIME_CONFIG", ""),
    )
    return raw.split()


def load_runtime_config(root: Path, relative: str) -> dict[str, Any]:
    path = _safe_relative(root, relative.replace("\\", "/"))
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, Mapping):
        raise ObservationRuntimeError("RUNTIME_CONFIG_INVALID")
    schema = json.loads((root / SCHEMA_RELATIVE).read_text(encoding="utf-8"))
    jsonschema.validate(dict(loaded), schema)
    credential_env = str(loaded["credential_env"])
    if credential_env not in ALLOWED_CREDENTIAL_ENV:
        raise ObservationRuntimeError("CREDENTIAL_ENV_NOT_ALLOWLISTED")
    if loaded.get("publish_fault_after") and not relative.replace("\\", "/").startswith(
        "tests/fixtures/"
    ):
        raise ObservationRuntimeError("PUBLISH_FAULT_NOT_A_TEST_FIXTURE")
    return dict(loaded)


def resolve_data_root(root: Path, data_root: str) -> Path:
    candidate = Path(data_root)
    if candidate.is_absolute():
        return candidate
    return (root / data_root).resolve()


def resolve_clock(config: Mapping[str, Any]) -> datetime:
    env = os.environ.get("OBSERVATION_SCHEDULE_CLOCK_UTC")
    if env:
        return parse_utc(env)
    raw = config.get("clock_utc")
    if raw:
        return parse_utc(raw)
    return datetime.now(UTC)


def load_credential_after_activation(config: Mapping[str, Any]) -> str:
    name = str(config["credential_env"])
    if name not in ALLOWED_CREDENTIAL_ENV:
        raise ObservationRuntimeError("CREDENTIAL_ENV_NOT_ALLOWLISTED")
    value = os.environ.get(name)
    if not value:
        raise ObservationRuntimeError("CREDENTIAL_ENV_MISSING")
    return value


class FakeProviderOpener:
    """Fixture HTTP surface. Never opens a network socket."""

    def __init__(self, fixture: Mapping[str, Any]) -> None:
        self.fixture = dict(fixture)
        self.urls: list[str] = []

    def open(self, url: str) -> dict[str, Any]:
        self.urls.append(url)
        parsed = urlsplit(url)
        omitted = {str(item) for item in self.fixture.get("omit") or []}
        if parsed.path == "/tokens/v2/recent":
            return {
                "http_status": 200,
                "body": list(self.fixture.get("recent") or []),
                "url_has_api_key": False,
            }
        if parsed.path == "/tokens/v2/search":
            query = parse_qs(parsed.query).get("query", [""])[0]
            mints = [item for item in query.split(",") if item]
            rows = []
            by_id = {
                str(row.get("id") or row.get("mint")): row
                for row in list(self.fixture.get("search") or [])
                if isinstance(row, Mapping)
            }
            for mint in mints:
                if mint in omitted:
                    continue
                row = by_id.get(mint)
                if row is not None:
                    rows.append(row)
            return {"http_status": 200, "body": rows, "url_has_api_key": False}
        if parsed.path == "/swap/v2/order":
            return {
                "http_status": 200,
                "body": dict(self.fixture.get("quote") or {"outAmount": "9900000"}),
                "url_has_api_key": False,
            }
        raise ObservationRuntimeError("FAKE_PROVIDER_PATH_UNKNOWN")


class JupiterReadonlyOpener:
    """The sole production transport: GET-only Jupiter readonly routes."""

    def __init__(self, api_key: str, *, timeout_seconds: float = 20.0) -> None:
        if not api_key:
            raise ObservationRuntimeError("CREDENTIAL_ENV_MISSING")
        self._api_key = api_key
        self._timeout_seconds = timeout_seconds

    def open(self, url: str) -> dict[str, Any]:
        request = urllib.request.Request(
            url,
            method="GET",
            headers={"x-api-key": self._api_key, "Accept": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=self._timeout_seconds) as response:
                body_bytes = response.read()
                body = json.loads(body_bytes.decode("utf-8"))
                return {
                    "http_status": int(response.status),
                    "body": body,
                    "url_has_api_key": False,
                }
        except urllib.error.HTTPError as exc:
            return {
                "http_status": int(exc.code),
                "body": None,
                "url_has_api_key": False,
            }
        except (urllib.error.URLError, TimeoutError, OSError):
            raise OSError("JUPITER_TRANSPORT_ERROR") from None


def build_opener(
    root: Path,
    config: Mapping[str, Any],
    *,
    credential: str | None = None,
) -> object | None:
    fixture_rel = config.get("fake_provider_fixture")
    if not fixture_rel:
        return JupiterReadonlyOpener(credential) if credential is not None else None
    path = _safe_relative(root, str(fixture_rel))
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, Mapping):
        raise ObservationRuntimeError("FAKE_PROVIDER_FIXTURE_INVALID")
    return FakeProviderOpener(loaded)


def git_sha(root: Path, configured: str | None) -> str:
    if configured:
        return configured
    import subprocess

    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=str(root),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        shell=False,
    )
    if completed.returncode != 0:
        raise ObservationRuntimeError("PRODUCER_GIT_SHA_UNAVAILABLE")
    value = completed.stdout.decode("ascii").strip()
    if len(value) != 40:
        raise ObservationRuntimeError("PRODUCER_GIT_SHA_UNAVAILABLE")
    return value


__all__ = [
    "ALLOWED_CREDENTIAL_ENV",
    "DEFAULT_RUNTIME_RELATIVE",
    "FakeProviderOpener",
    "JupiterReadonlyOpener",
    "ObservationRuntimeError",
    "UNIT_RELATIVE",
    "build_opener",
    "git_sha",
    "load_credential_after_activation",
    "load_runtime_config",
    "parse_unit_exec_start",
    "resolve_clock",
    "resolve_data_root",
]
