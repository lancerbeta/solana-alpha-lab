"""Real public entry + pinned freshness and public/private boundaries, no science."""
from __future__ import annotations

import copy
import io
import importlib.util
import json
import os
import subprocess
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from solana_alpha_lab.factory import research_shelf as wire
from solana_alpha_lab.factory import research_shelf_context as ctx
from solana_alpha_lab.factory import research_shelf_native as native
from solana_alpha_lab.factory.research_shelf_git import ShelfGit, ScopedShelfGit

ROOT = Path(__file__).resolve().parents[1]
NOW = "2026-10-24T00:00:00Z"
RAW = (ROOT / "tests/fixtures/research_shelf_v1/genesis.json").read_bytes()
ITEM = wire.decode(RAW)["item_id"]


def snapshot(raw=RAW):
    body = wire.decode(raw)
    return dict(wire.fold({wire.revision_path(body): raw}), files={wire.revision_path(body): raw},
                commit="a" * 40, source_checked_at=NOW, source_freshness="REMOTE_VERIFIED")


class ShelfEntryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / "local", prefix="shelf-entry-")
        self.addCleanup(self.temp.cleanup)
        self.work = Path(self.temp.name)

    def test_freshness_witness_survives_export_without_a_registry(self):
        raw = ctx.export_snapshot(snapshot())
        read = ctx.read_snapshot(raw, now=NOW)
        self.assertEqual((read["source_freshness"], read["source_checked_at"], read["commit"]), ("REMOTE_VERIFIED", NOW, "a" * 40))
        expired = ctx.read_snapshot(raw, now="2026-10-25T00:00:01Z")
        self.assertEqual((expired["status"], expired["source_freshness"]), ("STALE_AS_OF", "STALE_AS_OF"))
        self.assertEqual(len(expired["items"]), 1)
        body = json.loads(raw)
        body["observation"]["commit"] = "b" * 40
        with self.assertRaisesRegex(wire.ShelfError, "SNAPSHOT_HASH_MISMATCH"):
            ctx.read_snapshot(wire.canonical(body), now=NOW)

    def test_disposable_snapshot_recovers_from_an_abandoned_pending_file(self):
        path = self.work / "snapshot.json"
        path.with_name(path.name + ".pending").write_bytes(b"abandoned")
        raw = ctx.export_snapshot(snapshot())
        ctx.write_snapshot(path, raw)
        self.assertEqual(path.read_bytes(), raw)

    def test_direct_experiment_entry_reads_metadata_before_native_start(self):
        path = self.work / "snapshot.json"
        ctx.write_snapshot(path, ctx.export_snapshot(snapshot()))
        spec = importlib.util.spec_from_file_location("shelf_direct_entry", ROOT / "scripts/run_factory_experiment.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        observed = []
        native_model = dict(status="COMPLETE", run_id="SYNTHETIC-ENTRY-ONLY")
        class App:
            def __init__(self, **kwargs):
                observed.append(kwargs)
            def start(self):
                return copy.deepcopy(native_model)
        output, error = io.StringIO(), io.StringIO()
        with patch.dict(os.environ, {"SMIAL_RESEARCH_SHELF_SNAPSHOT": str(path)}), patch.object(module, "FactoryApplication", App), \
             patch("sys.argv", ["run_factory_experiment.py", "--root", str(ROOT)]), redirect_stdout(output), redirect_stderr(error):
            self.assertEqual(module.main(), 0)
        result = json.loads(output.getvalue())
        self.assertEqual({k: v for k, v in result.items() if k != "shelf_summary"}, native_model)
        self.assertNotIn("shelf_summary", observed[0])
        self.assertIn("Полка", error.getvalue())

    def test_real_refresh_export_then_pinned_glance_has_proven_freshness(self):
        remote = self.work / "remote.git"
        ShelfGit._run(None, "init", "--bare", "--quiet", str(remote))
        git = ShelfGit.init_local(self.work / "cache.git", remote)
        receipt = git.publish({wire.revision_path(wire.decode(RAW)): RAW}, expected_heads={ITEM: []})
        refreshed = git.refresh()
        path = self.work / "snapshot.json"
        ctx.write_snapshot(path, ctx.export_snapshot(refreshed))
        refs = git._git("show-ref").stdout
        with patch.object(ShelfGit, "_run", side_effect=AssertionError("Pinned entry must never run Git")):
            summary = ctx.glance(ROOT, snapshot_path=path, now=refreshed["source_checked_at"])
        self.assertEqual((summary["snapshot_commit"], summary["source_freshness"]), (receipt["commit"], "REMOTE_VERIFIED"))
        self.assertEqual(git._git("show-ref").stdout, refs)

    def test_missing_branch_and_invalid_snapshot_are_not_an_empty_shelf(self):
        empty = dict(status="NOT_INITIALIZED", complete=False, items={}, commit=None)
        read = ctx.read_snapshot(ctx.export_snapshot(empty), now=NOW)
        self.assertEqual(read["status"], "NOT_INITIALIZED")
        missing = ctx.glance(ROOT, snapshot_path=self.work / "missing.json", now=NOW)
        self.assertEqual((missing["status"], missing["snapshot_complete"]), ("UNAVAILABLE", False))
        self.assertIn("UNAVAILABLE", ctx.readout(missing))

    def test_actual_forge_blocked_entry_preserves_native_receipt_and_next_action(self):
        from scripts.hypothesis_forge import cmd_forge_run
        path = self.work / "snapshot.json"
        ctx.write_snapshot(path, ctx.export_snapshot(snapshot()))
        def run():
            output = io.StringIO()
            with redirect_stdout(output), redirect_stderr(io.StringIO()):
                exit_code = cmd_forge_run(ROOT, explicit_data_root=self.work / "missing-rdp")
            self.assertEqual(exit_code, 2)
            return json.loads(output.getvalue())
        with patch.dict(os.environ, {"SMIAL_RESEARCH_SHELF_SNAPSHOT": str(path)}):
            first = run()
            before = path.read_bytes()
            body = wire.decode(RAW)
            body.pop("revision_sha256")
            body.update(title="Другая метадата", state="CLOSED", closure=dict(reason="ADMINISTRATIVE", evidence_refs=[], successor=None))
            ctx.write_snapshot(path, ctx.export_snapshot(snapshot(wire.prepare(body))))
            second = run()
        self.assertNotEqual(before, path.read_bytes())
        self.assertNotEqual(first["shelf_summary"]["totals"], second["shelf_summary"]["totals"])
        for key in ("next_action", "receipt_sha256", "run_identity_sha256", "writes", "owner_class"):
            self.assertEqual(first[key], second[key], key)
        self.assertEqual(second["shelf_summary"]["receipt_hash_domain"], "EXCLUDED_DERIVED_OVERLAY")

    def test_event_unknown_manual_acknowledgement_and_expiry_have_no_science_effect(self):
        body = wire.decode(RAW)
        body.pop("revision_sha256")
        body["review"] = dict(review_at=None, review_by=None, event=dict(kind="NATIVE_STATUS", source=None, condition="COMPLETE", acknowledged_ref=None))
        snap = snapshot(wire.prepare(body))
        unknown = native.read_events(snap, now=NOW)
        self.assertEqual(unknown[ITEM]["status"], "UNKNOWN")
        self.assertEqual(wire.attention(snap, now=NOW, source_states=unknown)["totals"], {"SOURCE_READBACK_REQUIRED": 1})
        evidence = dict(kind="NATIVE", owner="SMIAL", entity_kind="RESEARCH_ARTIFACT", entity_id="RF-ART-SYNTHETIC", payload_sha256="c" * 64, locator="smial-data://research/records/RF-ART-SYNTHETIC")
        met = {ITEM: dict(status="MET", evidence_ref=evidence, as_of=NOW)}
        self.assertEqual(wire.attention(snap, now=NOW, source_states=met)["totals"], {"EVENT_REVIEW": 1})
        snap["items"][ITEM]["current"]["review"]["event"]["acknowledged_ref"] = evidence
        self.assertEqual(wire.attention(snap, now=NOW, source_states=met)["totals"], {"WAITING": 1})
        met[ITEM]["execution_deadline"] = "2026-10-23T23:59:59Z"
        self.assertEqual(wire.attention(snap, now=NOW, source_states=met)["totals"], {"EXPIRED_REVIEW_REQUIRED": 1})
        self.assertEqual(wire.attention(snap, now=NOW, source_states=met)["scientific_admission"], "NOT_EVALUATED")

    def test_scout_adapter_reads_only_exact_saved_status_without_importing_scout(self):
        source = dict(kind="GIT_PATH", repository="lancerbeta/marcopolo-scout", ref="d" * 40, path="saved/feasibility.json")
        raw = wire.canonical(dict(schema="marcopolo.concurrent-choice-feasibility", status="PASS", private_note="PRIVATE_SENTINEL"))
        ref = dict(kind="GIT", repository=source["repository"], commit=source["ref"], path=source["path"], sha256=wire.sha256(raw))
        sources = {wire.canonical(source).decode(): dict(evidence_ref=ref, raw=raw.decode())}
        event = dict(kind="NATIVE_STATUS", source=source, condition="PASS", acknowledged_ref=None)
        result = native.event_read(event, now=NOW, saved_sources=sources)
        self.assertEqual(result["status"], "MET")
        self.assertNotIn("PRIVATE_SENTINEL", json.dumps(result))
        event["kind"] = "SOURCE_CHANGED"
        self.assertEqual(native.event_read(event, now=NOW, saved_sources=sources)["status"], "UNKNOWN")
        event["acknowledged_ref"] = ref
        self.assertEqual(native.event_read(event, now=NOW, saved_sources=sources)["status"], "NOT_MET")
        sources[next(iter(sources))]["raw"] += " "
        self.assertEqual(native.event_read(event, now=NOW, saved_sources=sources)["status"], "UNKNOWN")
        raw = wire.canonical(dict(schema="marcopolo.concurrent-choice-feasibility", status="FUTURE_UNKNOWN"))
        sources[next(iter(sources))] = dict(evidence_ref=dict(ref, sha256=wire.sha256(raw)), raw=raw.decode())
        self.assertEqual(native.event_read(event, now=NOW, saved_sources=sources)["status"], "UNKNOWN")

    def test_native_source_baseline_covers_plan_and_monitor_independently(self):
        from solana_alpha_lab.factory import research_fragments
        records = [SimpleNamespace(record_id=name, record_kind="RESEARCH_ARTIFACT", payload_json="{}",
            payload_sha256=wire.sha256(b"{}"), first_reliable_available_at=wire.clock(NOW))
            for name in ("CARD", "PLAN-1", "PLAN-2", "CHECK-1", "CHECK-2")]
        class Store:
            root = self.work
            def iter_committed_records(self):
                return iter(records)
        view = dict(fragment_version_id="RFV-SYNTHETIC", source_ref="CARD", check=dict(status="COMPLETE"),
            plan=dict(_record_id="PLAN-1", execution_deadline="2026-11-10T00:00:00Z"),
            evidence_blocks=[dict(source_ref="CHECK-1")])
        event = dict(kind="SOURCE_CHANGED", condition=None, acknowledged_ref=None, source=dict(kind="NATIVE_ENTITY",
            owner="SMIAL", entity_kind="RESEARCH_FRAGMENT", entity_id="RFV-SYNTHETIC"))
        with patch.object(research_fragments, "source_snapshot", side_effect=lambda *a, **k: [view]):
            original = native.event_read(event, now=NOW, store=Store())
            event["acknowledged_ref"] = original["evidence_ref"]
            self.assertEqual(native.event_read(event, now=NOW, store=Store())["status"], "NOT_MET")
            view["plan"] = dict(_record_id="PLAN-2", execution_deadline="2026-11-20T00:00:00Z")
            changed_plan = native.event_read(event, now=NOW, store=Store())
            self.assertEqual(changed_plan["status"], "MET")
            event["acknowledged_ref"] = changed_plan["evidence_ref"]
            view["evidence_blocks"] = [dict(source_ref="CHECK-2")]
            changed_check = native.event_read(event, now=NOW, store=Store())
            self.assertEqual(changed_check["status"], "MET")
            self.assertEqual({r["entity_id"] for r in changed_check["source_refs"]}, {"CARD", "PLAN-2", "CHECK-2"})

    def test_bad_scout_source_is_isolated_and_moving_ref_is_unknown(self):
        files, sources, ids = {}, {}, []
        for index, raw in enumerate((b"[]", wire.canonical(dict(schema="marcopolo.concurrent-choice-feasibility", status="PASS")))):
            body = wire.decode(RAW)
            body.pop("revision_sha256")
            body["item_id"] = body["item_id"][:-1] + str(index + 3)
            body["mutation_id"] = f"00000000-0000-4000-8000-{index + 30:012d}"
            source = dict(kind="GIT_PATH", repository="lancerbeta/marcopolo-scout", ref="d" * 40, path=f"saved/status-{index}.json")
            body["review"]["event"] = dict(kind="NATIVE_STATUS", source=source, condition="PASS", acknowledged_ref=None)
            encoded = wire.prepare(body)
            files[wire.revision_path(wire.decode(encoded))] = encoded
            ids.append(body["item_id"])
            sources[wire.canonical(source).decode()] = dict(raw=raw.decode(), evidence_ref=dict(kind="GIT", repository=source["repository"],
                commit=source["ref"], path=source["path"], sha256=wire.sha256(raw)))
        states = native.read_events(wire.fold(files), now=NOW, saved_sources=sources)
        self.assertEqual([states[i]["status"] for i in ids], ["UNKNOWN", "MET"])
        moving = dict(source, ref="research-log")
        sources[wire.canonical(moving).decode()] = sources[wire.canonical(source).decode()]
        event = dict(kind="SOURCE_CHANGED", source=moving, condition=None, acknowledged_ref=None)
        self.assertEqual(native.event_read(event, now="2030-01-01T00:00:00Z", saved_sources=sources)["status"], "UNKNOWN")

    def test_owner_glance_and_missing_snapshot_recovery_remain_actionable(self):
        state = snapshot()
        state.update(source_freshness="REMOTE_VERIFIED")
        summary = wire.attention(state, now="2026-10-31T00:00:00Z")
        summary.update(next_review_at="2026-11-20T00:00:00Z", omitted_count=2)
        text = ctx.readout(summary)
        for expected in ("Synthetic deferred observation", ITEM, "2026-11-20", "Ещё 2", "review --snapshot"):
            self.assertIn(expected, text)
        missing = ctx.load_snapshot(self.work / "missing.json", now=NOW)
        result = native.resolve_item(missing, ITEM)
        self.assertEqual(result["status"], "UNAVAILABLE")
        self.assertIn("REFRESH", result["next_action"])
        self.assertIsNotNone(native.find_native(missing, {})["reason"])

    def test_partial_link_enriches_same_target_without_changing_adoption(self):
        from uuid import uuid4
        target = dict(kind="NATIVE", owner="SMIAL", entity_kind="HYPOTHESIS_VERSION", entity_id="CANDIDATE-ONE",
            payload_sha256="a" * 64, locator="smial-data://research/records/CANDIDATE-ONE")
        partial = dict(destination_refs=[target], candidate_record_refs=[target], gaps=["CRITIC_RESULT_UNAVAILABLE"])
        extra = dict(target, entity_id="CRITIC-ONE", entity_kind="RESEARCH_ARTIFACT", locator="smial-data://research/records/CRITIC-ONE")
        complete = dict(destination_refs=[target, extra], candidate_record_refs=[target], gaps=[])
        args = dict(store=None, identity=dict(session_id="SESSION", candidate_id="CANDIDATE", definition_sha256="b" * 64),
            request_id="EXACT-REQUEST", now=NOW, mutation_id=str(uuid4()))
        with patch.object(native, "native_dossier", return_value=partial):
            first = native.prepare_link(snapshot(), ITEM, wire.decode(RAW)["revision_sha256"], **args)
        files = dict(snapshot()["files"])
        files[wire.revision_path(wire.decode(first["prepared"]))] = first["prepared"]
        linked = dict(wire.fold(files), files=files, commit="c" * 40)
        with patch.object(native, "native_dossier", return_value=complete):
            enriched = native.prepare_link(linked, ITEM, wire.decode(RAW)["revision_sha256"], **dict(args, mutation_id=str(uuid4())))
        link = wire.decode(enriched["prepared"])["native_links"][0]
        self.assertEqual(link["verification"], "VERIFIED")
        self.assertEqual(link["adopted_item_revision"]["commit"], "a" * 40)
        self.assertEqual(link["adoption_key"], first["adoption_key"])
        files[wire.revision_path(wire.decode(enriched["prepared"]))] = enriched["prepared"]
        final = wire.fold(files)
        inverse = native.find_native(final, target)
        self.assertEqual(inverse["status"], "FOUND")
        self.assertEqual(inverse["matches"][0]["status"], "CURRENT_SOURCE_LINK")
        self.assertEqual(len(inverse["matches"][0]["historical_relations"]), 1)
        duplicate = wire.revise(final, ITEM, dict(native_links=[link, dict(link, adoption_key="independent-association")],
            change_reason="Two genuinely independent synthetic associations."), now=NOW, mutation_id=str(uuid4()))
        files[wire.revision_path(wire.decode(duplicate))] = duplicate
        self.assertEqual(native.find_native(wire.fold(files), target)["status"], "AMBIGUOUS_SOURCE_LINK")
        correction = wire.revise(wire.fold(files), ITEM, dict(native_links=[dict(link, adoption_key="independent-association")],
            change_reason="Explicitly retract the first association; retain its audit history."), now=NOW, mutation_id=str(uuid4()))
        files[wire.revision_path(wire.decode(correction))] = correction
        corrected = native.find_native(wire.fold(files), target)
        self.assertEqual(corrected["status"], "FOUND")
        self.assertEqual(sum(row["status"] == "CURRENT_SOURCE_LINK" for row in corrected["matches"]), 1)
        with patch.object(native, "native_dossier", return_value=dict(complete, candidate_record_refs=[extra])):
            with self.assertRaisesRegex(wire.ShelfError, "ADOPTION_KEY_CONFLICT"):
                native.prepare_link(linked, ITEM, wire.decode(RAW)["revision_sha256"], **args)

    def test_private_sentinel_in_every_free_text_field_cannot_use_clean_disclosure(self):
        body = wire.decode(RAW)
        body["origin_refs"] = [dict(kind="GIT", repository="lancerbeta/marcopolo-scout", commit="a" * 40, path="saved/protocol.json", sha256="b" * 64)]
        body["last_decision"] = dict(at=NOW, disposition="REVIEW", reason="Minimal public wording", evidence_refs=[])
        review = dict(disposition="EXPLICIT_MINIMAL_PUBLIC_DISCLOSURE", payload_sha256=wire.sha256(wire.canonical(body)))
        with self.assertRaisesRegex(wire.ShelfError, "PRIVATE_SOURCE_PUBLIC_DISCLOSURE_REQUIRED"):
            ctx.public_payload_guard(body)
        ctx.public_payload_guard(body, disclosure=review)
        paths = [("title",), ("statement",), ("next_action", "intent"), ("last_decision", "reason"), ("change_reason",)]
        for path in paths:
            changed = copy.deepcopy(body)
            target = changed
            for part in path[:-1]:
                target = target[part]
            target[path[-1]] = "PRIVATE_SENTINEL"
            with self.subTest(path=path):
                with self.assertRaisesRegex(wire.ShelfError, "PRIVATE_SOURCE_PUBLIC_DISCLOSURE_REQUIRED"):
                    ctx.public_payload_guard(changed, disclosure=review)
        dossier = dict(origin_refs=body["origin_refs"], native=dict(parameters=dict(secret_formula="PRIVATE_SENTINEL")))
        with self.assertRaisesRegex(wire.ShelfError, "PRIVATE_SOURCE_PUBLIC_DISCLOSURE_REQUIRED"):
            ctx.public_payload_guard(dossier, disclosure=review)

    def test_shared_history_preserves_adopted_revision_and_retracted_link(self):
        fixture = json.loads((ROOT / "tests/fixtures/research_shelf_v1/history.json").read_bytes())
        files = {}
        for vector in fixture["revisions"]:
            raw = vector["raw"].encode("utf-8")
            body = wire.decode(raw)
            self.assertEqual(wire.sha256(raw), vector["file_sha256"])
            self.assertEqual(body["revision_sha256"], vector["revision_sha256"])
            files[wire.revision_path(body)] = raw
        folded = wire.fold(files)
        item = folded["items"][fixture["expected"]["item_id"]]
        self.assertEqual(item["current"]["revision_sha256"], fixture["expected"]["current_revision"])
        self.assertEqual(item["current"]["state"], "CLOSED")
        self.assertEqual(item["revisions"][fixture["expected"]["adopted_revision"]]["statement"], fixture["expected"]["adopted_statement"])
        target = next(link["destination_refs"][0] for row in item["revisions"].values() for link in row["native_links"])
        self.assertEqual(native.find_native(folded, target)["matches"][0]["status"], "RETRACTED_SOURCE_LINK")
        for case in fixture["projection_cases"]:
            selected = {wire.revision_path(wire.decode(fixture["revisions"][i]["raw"].encode())):
                        fixture["revisions"][i]["raw"].encode() for i in case["revision_indices"]}
            state = wire.fold(selected)
            row = state["items"][fixture["expected"]["item_id"]]
            review = wire.attention(state, now=case["now"], source_states=case["source_states"])
            with self.subTest(projection=case["name"]):
                self.assertEqual(row["status"], case["expected"]["item_status"])
                self.assertEqual(row["heads"], case["expected"]["heads"])
                self.assertEqual(review["totals"], case["expected"]["totals"])
                self.assertEqual(review["items"][0]["status"] if review["items"] else None, case["expected"]["attention_status"])

    def test_real_semantic_route_exposes_cloud_recipe_without_workstation(self):
        env = dict(os.environ, PYTHONUTF8="1")
        found = subprocess.run([os.sys.executable, "-B", str(ROOT / "scripts/catalog_cli.py"), "search-routes",
            "--text", "полка исследований", "--limit", "1", "--json"], cwd=ROOT, env=env, capture_output=True, check=True)
        self.assertEqual(json.loads(found.stdout)[0]["semantic_route_id"], "SEM-RESEARCH-SHELF")
        result = subprocess.run([os.sys.executable, "-B", str(ROOT / "scripts/catalog_cli.py"), "resolve-route", "SEM-RESEARCH-SHELF", "--json"],
                                cwd=ROOT, env=env, capture_output=True, check=True)
        route = json.loads(result.stdout)
        self.assertFalse(route["authority_granted"])
        self.assertEqual(route["forge_visibility"], "EXCLUDE")
        doc = next(r for r in route["root_assets"] if r["asset_id"] == "DOC-RESEARCH-SHELF-001")
        text = (ROOT / doc["path"]).read_text(encoding="utf-8")
        for required in ("lancerbeta/solana-alpha-lab", "research-log", "capsules/research_shelf_v1/", "NOT_INITIALIZED", "git/trees/H?recursive=1", "contents/<path>?ref=H"):
            self.assertIn(required, text)

    def test_network_wrapper_requires_accepted_main_policy_before_any_transport(self):
        scope = dict(schema="smial.research-shelf-metadata-scope", schema_version="1.0", repository="lancerbeta/solana-alpha-lab",
            branch="research-log", prefix=wire.PREFIX, allowed_actions=["READ", "APPEND"], owner_scope_ref="SYNTHETIC_ONLY",
            accepted_code_commit="0" * 40, accepted_policy_sha256="a" * 64)
        with patch.object(ScopedShelfGit, "_git", side_effect=AssertionError("No metadata transport before code acceptance")):
            with self.assertRaisesRegex(wire.ShelfError, "METADATA_CAPABILITY_NOT_ACCEPTED_ON_MAIN"):
                ScopedShelfGit(self.work / "never-created.git", scope=scope)
        for changes in (dict(branch="main"), dict(prefix="src"), dict(allowed_actions=["DELETE"])):
            with self.assertRaises(wire.ShelfError):
                ScopedShelfGit._scope_shape(dict(scope, **changes), "APPEND")
        with self.assertRaisesRegex(wire.ShelfError, "PUBLIC_METADATA_ENDPOINT_REFUSED"):
            ScopedShelfGit.init_scoped(self.work / "never-created.git", remote="https://example.invalid/other.git", scope=scope)

    def test_network_append_enforces_public_guard_without_reimplementing_transport(self):
        body = wire.decode(RAW)
        body.pop("revision_sha256")
        body.update(product="SMIAL", item_id=body["item_id"].replace("SCOUT", "SMIAL"), origin_refs=[dict(kind="GIT",
            repository="lancerbeta/marcopolo-scout", commit="b" * 40, path="private/source.json", sha256="c" * 64)], statement="PRIVATE_SENTINEL")
        raw = wire.prepare(body)
        writer = object.__new__(ScopedShelfGit)
        writer.scope = {}
        with patch.object(writer, "_accepted_policy"), patch.object(ShelfGit, "publish", side_effect=AssertionError("No append before public guard")):
            with self.assertRaisesRegex(wire.ShelfError, "PRIVATE_SOURCE_PUBLIC_DISCLOSURE_REQUIRED"):
                writer.publish({wire.revision_path(wire.decode(raw)): raw}, expected_heads={body["item_id"]: []})
        disclosure = dict(disposition="EXPLICIT_MINIMAL_PUBLIC_DISCLOSURE", payload_sha256=wire.sha256(wire.canonical(wire.decode(raw))))
        with patch.object(writer, "_accepted_policy"), patch.object(ShelfGit, "publish", return_value=dict(status="PUBLISHED")) as kernel:
            writer.publish({wire.revision_path(wire.decode(raw)): raw}, expected_heads={body["item_id"]: []},
                disclosures={disclosure["payload_sha256"]: disclosure})
            kernel.assert_called_once()

    def test_cli_passes_exact_disclosure_to_the_mandatory_writer_guard(self):
        spec = importlib.util.spec_from_file_location("shelf_cli_approval", ROOT / "scripts/research_shelf.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        body = wire.decode(RAW)
        body.pop("revision_sha256")
        body.update(product="SMIAL", item_id=body["item_id"].replace("SCOUT", "SMIAL"))
        body["origin_refs"] = [dict(kind="GIT", repository="lancerbeta/marcopolo-scout", commit="a" * 40,
            path="saved/source.json", sha256="b" * 64)]
        raw = wire.prepare(body)
        request, scope, approval = (self.work / name for name in ("prepared.json", "scope.json", "approval.json"))
        request.write_bytes(raw)
        scope.write_text("{}")
        approval.write_text(json.dumps(dict(disposition="EXPLICIT_MINIMAL_PUBLIC_DISCLOSURE",
            payload_sha256=wire.sha256(wire.canonical(wire.decode(raw))))))
        args = ["apply", "--cache", str(self.work / "cache.git"), "--input", str(request), "--metadata-scope", str(scope)]
        with patch.object(ScopedShelfGit, "__init__", return_value=None), patch.object(ScopedShelfGit, "_accepted_policy"), \
             patch.object(ShelfGit, "publish", return_value=dict(status="PUBLISHED")) as kernel, redirect_stdout(io.StringIO()):
            self.assertEqual(module.main(args + ["--disclosure", str(approval)]), 0)
            self.assertEqual(module.main(args), 2)
            kernel.assert_called_once()


if __name__ == "__main__":
    unittest.main()
