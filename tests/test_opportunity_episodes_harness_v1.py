"""Test-owned physical boundary for OPPORTUNITY_EPISODES proofs.

Only the transport (``opener``), the pacing/now clock and authored market
bytes are synthetic. Registration, authority, activation, ticks, admission,
publication, freeze, release, import and Forge run through production owners.
"""

from __future__ import annotations

import copy
import json
import sys
import unittest
from contextlib import redirect_stdout
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from io import StringIO
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qs, urlsplit

import yaml

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
for entry in (ROOT, SRC):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from solana_alpha_lab.factory.observation_provider_pacing import AdvancingClock  # noqa: E402
from solana_alpha_lab.factory.observation_schedule import (  # noqa: E402
    render_utc,
    validate_observation_schedule,
)
from solana_alpha_lab.factory.observation_schedule_composition import (  # noqa: E402
    TickPhysicalOverrides,
)
from solana_alpha_lab.factory.observation_schedule_lifecycle import (  # noqa: E402
    _authority_policy,
    _minimum_expiry,
    _used_provider_route_ids,
    activate_schedule,
    authorize_schedule,
    expected_authority_phrase,
    register_schedule,
)
from solana_alpha_lab.factory.observation_schedule_runtime import (  # noqa: E402
    DEFAULT_RUNTIME_RELATIVE,
)
from solana_alpha_lab.factory.observation_schedule_store import (  # noqa: E402
    ObservationScheduleStore,
)
from solana_alpha_lab.factory.opportunity_episodes import (  # noqa: E402
    ASSIGNMENT_DIR,
    ASSIGNMENT_SCHEMA,
    assignment_document_sha256,
)
from solana_alpha_lab.factory.observation_schedule import canonical_sha256  # noqa: E402

TEMPLATE = ROOT / "configs" / "opportunity_episodes_jupiter_core_v1.yaml"
PRODUCER = "a" * 40
ACTIVATION_ID = "ACT-OPPORTUNITY-EPISODES-SYNTH-V1"
ASSIGNMENT_ID = "SYNTH-PROTECTION-ASSIGNMENT-V1"
CATEGORIES = ("toporganicscore", "toptraded", "toptrending")


def synth_mint(label: str) -> str:
    """Synthetic, syntactically valid identity. Never a real selected market."""

    text = ("Synth" + "".join(ch for ch in label if ch.isalnum()))[:30]
    return (text + "1" * 44)[:44]


def token_object(
    mint: str,
    *,
    price: float | None,
    liquidity: float | None,
    holders: int | None,
    tags: list[str] | None = None,
    pool_created_at: str = "2025-01-10T08:00:00Z",
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "id": mint,
        "name": f"Synthetic {mint[:8]}",
        "symbol": mint[5:9].upper(),
        "decimals": 6,
        "tags": list(tags if tags is not None else ["community"]),
        "firstPool": {"createdAt": pool_created_at, "source": "synthetic-amm"},
        "stats5m": {"buyVolume": 1234.5, "sellVolume": 999.0, "numBuys": 10, "numSells": 7},
        "mcap": 250000.0,
    }
    if price is not None:
        body["usdPrice"] = price
    if liquidity is not None:
        body["liquidity"] = liquidity
    if holders is not None:
        body["holderCount"] = holders
    if extra:
        body.update(extra)
    return body


@dataclass
class SyntheticMarket:
    """Authored vendor bytes keyed by wall time. Test-owned, never production."""

    # round_start -> category -> list of token objects
    nominations: dict[datetime, dict[str, list[dict[str, Any]]]] = field(default_factory=dict)
    # mint -> callable(now) -> token object or None (absent)
    series: dict[str, Callable[[datetime], dict[str, Any] | None]] = field(default_factory=dict)
    # category failures: (round_start, category) -> http status
    category_failures: dict[tuple[datetime, str], int] = field(default_factory=dict)
    # search failures by assigned slot time -> http status
    search_failures: dict[datetime, int] = field(default_factory=dict)
    # per-call latency seconds (default 1)
    latency: Callable[[str, datetime], float] = lambda _kind, _now: 1.0

    def round_for(self, now: datetime) -> datetime:
        day = datetime(now.year, now.month, now.day, tzinfo=UTC)
        elapsed = int((now - day).total_seconds())
        return day + timedelta(seconds=(elapsed // 900) * 900)

    def slot_for(self, now: datetime) -> datetime:
        epoch = datetime(1970, 1, 1, tzinfo=UTC)
        seconds = int((now - epoch).total_seconds())
        return epoch + timedelta(seconds=(seconds // 300) * 300)


class SyntheticJupiter:
    """Physical HTTP boundary. Advances the shared clock by authored latency."""

    def __init__(self, market: SyntheticMarket, clock: AdvancingClock) -> None:
        self.market = market
        self.clock = clock
        self.urls: list[str] = []
        self.calls: list[dict[str, Any]] = []

    def open(self, url: str) -> dict[str, Any]:
        now = self.clock.now()
        self.urls.append(url)
        parsed = urlsplit(url)
        parts = [item for item in parsed.path.split("/") if item]
        if len(parts) == 4 and parts[:2] == ["tokens", "v2"] and parts[2] in CATEGORIES:
            kind = "category"
            category = parts[2]
            round_start = self.market.round_for(now)
            status = self.market.category_failures.get((round_start, category))
            body = copy.deepcopy(self.market.nominations.get(round_start, {}).get(category, []))
        elif parsed.path == "/tokens/v2/search":
            kind = "search"
            status = self.market.search_failures.get(self.market.slot_for(now))
            mints = [item for item in parse_qs(parsed.query).get("query", [""])[0].split(",") if item]
            body = []
            for mint in mints:
                maker = self.market.series.get(mint)
                row = maker(now) if maker is not None else None
                if row is not None:
                    body.append(copy.deepcopy(row))
        else:
            raise AssertionError(f"UNEXPECTED_PROVIDER_PATH:{parsed.path}")
        self.clock.sleep(float(self.market.latency(kind, now)))
        self.calls.append({"kind": kind, "at": render_utc(now), "url": url, "status": status or 200})
        if status is not None:
            return {"http_status": int(status), "body": {"error": "synthetic failure"}, "url_has_api_key": False}
        return {"http_status": 200, "body": body, "url_has_api_key": False}


def write_assignment(data_root: Path, entries: list[dict[str, Any]], *, complete: bool = True) -> dict[str, str]:
    document = {
        "schema": ASSIGNMENT_SCHEMA,
        "schema_version": "1.0",
        "assignment_id": ASSIGNMENT_ID,
        "owner": "SYNTHETIC_TEST_FIXTURE",
        "interpretation_version": "1.0",
        "completeness": {"complete": complete, "proof": "SYNTHETIC_REGISTERED_INVENTORY"},
        "entries": entries,
    }
    path = Path(data_root) / ASSIGNMENT_DIR / f"{ASSIGNMENT_ID}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(json.dumps(document, sort_keys=True).encode("utf-8"))
    return {"assignment_id": ASSIGNMENT_ID, "sha256": assignment_document_sha256(document)}


def build_schedule(
    *,
    starts_at: datetime,
    stops_at: datetime,
    assignment: dict[str, str],
    daily_ceiling: int = 96,
    active_cap: int = 400,
    schedule_key: str = "OBS-OPPORTUNITY-EPISODES-SYNTH-V1",
    budgets: dict[str, Any] | None = None,
    observation_overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    document = yaml.safe_load(TEMPLATE.read_text(encoding="utf-8"))
    document["schedule_key"] = schedule_key
    document["activation"] = {"starts_at": render_utc(starts_at), "stops_admitting_at": render_utc(stops_at)}
    document["protection"] = {"assignment_sources": [assignment]}
    document["sampling"]["daily_normal_ceiling"] = daily_ceiling
    document["sampling"]["rolling_24h_max"] = daily_ceiling
    document["sampling"]["active_episode_cap"] = active_cap
    if budgets:
        document["budgets"].update(budgets)
    if observation_overrides:
        document["observation_schedule"].update(observation_overrides)
    return validate_observation_schedule(document, root=ROOT)


def authority_phrase(document: dict[str, Any]) -> str:
    expires_at = render_utc(_minimum_expiry(document))
    _, routes = _used_provider_route_ids(ROOT, document)
    policy = _authority_policy(root=ROOT, document=document, schedule_key=document["schedule_key"], expires_at=expires_at)
    return expected_authority_phrase(
        schedule_sha256=document["schedule_sha256"],
        schedule_key=document["schedule_key"],
        activation_starts_at=document["activation"]["starts_at"],
        activation_stops_admitting_at=document["activation"]["stops_admitting_at"],
        provider_route_ids=routes,
        expires_at=expires_at,
        policy_digest=canonical_sha256(policy),
    )


def register_authorize_activate(data_root: Path, schedule: dict[str, Any], *, now: datetime, activation_id: str = ACTIVATION_ID) -> str:
    store = ObservationScheduleStore(Path(data_root) / "observation_schedule_state.sqlite")
    try:
        registered = register_schedule(root=ROOT, data_root=data_root, store=store, document=schedule, now=now, producer_git_sha=PRODUCER)
        assert registered["schedule_sha256"] == schedule["schedule_sha256"], registered
        authorize_schedule(
            root=ROOT,
            data_root=data_root,
            store=store,
            schedule_sha256=schedule["schedule_sha256"],
            phrase=authority_phrase(schedule),
            now=now,
            producer_git_sha=PRODUCER,
        )
        activated = activate_schedule(
            root=ROOT,
            data_root=data_root,
            store=store,
            schedule_sha256=schedule["schedule_sha256"],
            activation_id=activation_id,
            now=now,
            producer_git_sha=PRODUCER,
        )
        assert activated["terminal"] in {"ACTIVATED", "ACTIVATE_REPLAY"}, activated
    finally:
        store.close()
    return activation_id


def cli_tick(data_root: Path, market: SyntheticMarket, at: datetime, *, env_fault: str | None = None) -> dict[str, Any]:
    """The production entry with complete process-local physical overrides."""

    import os

    from scripts.observation_schedule import main as cli_main

    clock = AdvancingClock(at)
    opener = SyntheticJupiter(market, clock)
    buf = StringIO()
    previous = os.environ.get("OBSERVATION_SCHEDULE_PUBLISH_FAULT")
    try:
        if env_fault is not None:
            os.environ["OBSERVATION_SCHEDULE_PUBLISH_FAULT"] = env_fault
        with redirect_stdout(buf):
            code = cli_main(
                ["tick", "--once", "--runtime-config", DEFAULT_RUNTIME_RELATIVE, "--data-root", str(data_root)],
                physical_overrides=TickPhysicalOverrides(now=at, opener=opener, pacing_clock=clock),
            )
    finally:
        if env_fault is not None:
            if previous is None:
                os.environ.pop("OBSERVATION_SCHEDULE_PUBLISH_FAULT", None)
            else:
                os.environ["OBSERVATION_SCHEDULE_PUBLISH_FAULT"] = previous
    text = buf.getvalue().strip().splitlines()
    payload = json.loads(text[-1]) if text else {}
    payload["_exit_code"] = code
    payload["_calls"] = opener.calls
    return payload


class EpisodeScenario:
    """One isolated producer root driven only through the production entry."""

    def __init__(
        self,
        root: Path,
        *,
        start: datetime,
        stops: datetime,
        assignment_entries: list[dict[str, Any]] | None = None,
        daily_ceiling: int = 96,
        active_cap: int = 400,
        budgets: dict[str, Any] | None = None,
        schedule_key: str = "OBS-OPPORTUNITY-EPISODES-SYNTH-V1",
        observation_overrides: dict[str, Any] | None = None,
    ) -> None:
        self.data_root = Path(root)
        self.data_root.mkdir(parents=True, exist_ok=True)
        self.assignment = write_assignment(self.data_root, list(assignment_entries or []))
        self.schedule = build_schedule(
            starts_at=start,
            stops_at=stops,
            assignment=self.assignment,
            daily_ceiling=daily_ceiling,
            active_cap=active_cap,
            budgets=budgets,
            schedule_key=schedule_key,
            observation_overrides=observation_overrides,
        )
        self.activation_id = register_authorize_activate(self.data_root, self.schedule, now=start)
        self.market = SyntheticMarket()
        self.ticks: list[dict[str, Any]] = []

    @property
    def ops_path(self) -> Path:
        return self.data_root / "observation_schedule_state.sqlite"

    def tick(self, at: datetime, *, fault: str | None = None) -> dict[str, Any]:
        result = cli_tick(self.data_root, self.market, at, env_fault=fault)
        self.ticks.append(result)
        return result

    def query(self, sql: str, params: tuple = ()) -> list[tuple]:
        import sqlite3

        connection = sqlite3.connect(f"file:{self.ops_path.as_posix()}?mode=ro", uri=True)
        try:
            return list(connection.execute(sql, params).fetchall())
        finally:
            connection.close()

    def admissions(self) -> list[dict[str, Any]]:
        rows = self.query("SELECT record_json FROM episode_admissions ORDER BY t0, episode_id")
        return [json.loads(row[0]) for row in rows]

    def slot_states(self, episode_id: str) -> dict[str, tuple[str, str | None]]:
        rows = self.query(
            "SELECT point_id, state, payload_json FROM due_observations WHERE entity_id = ?",
            (episode_id,),
        )
        return {row[0]: (row[1], json.loads(row[2]).get("missing_reason")) for row in rows}

    def unpublished(self) -> int:
        return int(self.query("SELECT COUNT(*) FROM episode_outbox WHERE published_content_sha256 IS NULL")[0][0])

    def rounds(self) -> list[dict[str, Any]]:
        rows = self.query("SELECT round_id, state, frame_json FROM episode_rounds ORDER BY round_started_at")
        return [{"round_id": r[0], "state": r[1], "frame": json.loads(r[2])} for r in rows]

    def published_text(self) -> str:
        """Concatenated published member/observation bytes as text (search only)."""

        import pyarrow.parquet as pq

        chunks: list[str] = []
        for path in sorted((self.data_root / "datasets").rglob("*.parquet")):
            if "raw_evidence" in path.parts:
                continue
            chunks.append(json.dumps(pq.read_table(path).to_pylist(), default=str))
        return "\n".join(chunks)


def nominate(market: SyntheticMarket, at: datetime, mapping: dict[str, list[dict[str, Any]]]) -> None:
    market.nominations[market.round_for(at)] = {key: list(value) for key, value in mapping.items()}


class HarnessSelfTests(unittest.TestCase):
    def test_synthetic_mints_are_valid_identities(self) -> None:
        mint = synth_mint("A")
        self.assertEqual(len(mint), 44)
        self.assertTrue(mint.isalnum())


if __name__ == "__main__":
    unittest.main()
