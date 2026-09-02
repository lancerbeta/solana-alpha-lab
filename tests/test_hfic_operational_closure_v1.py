from __future__ import annotations

import json
import re
import unittest
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "configs/hypothesis_forge_independent_critic_v1.yaml"
OPERATOR_PATH = ROOT / "docs/operator/HYPOTHESIS_FORGE_AND_INDEPENDENT_CRITIC_OPERATOR_V1.md"
FORGE_SKILL_PATH = ROOT / ".agents/skills/hypothesis-forge/SKILL.md"
CRITIC_SKILL_PATH = ROOT / ".agents/skills/independent-hypothesis-critic/SKILL.md"
FORGE_COMMAND_PATH = ROOT / ".cursor/commands/hypothesis-forge.md"
DRAFT_SCHEMA = ROOT / "catalog/schemas/hypothesis_forge_draft_v1.schema.json"
CRITIC_RESULT_SCHEMA = ROOT / "catalog/schemas/hypothesis_critic_result_v1.schema.json"
SESSION_RECEIPT_SCHEMA = ROOT / "catalog/schemas/hypothesis_forge_session_receipt_v1.schema.json"
HANDOFF_V11_SCHEMA = ROOT / "catalog/schemas/hypothesis_forge_synthesis_handoff_v1_1.schema.json"
HANDOFF_V10_SCHEMA = ROOT / "catalog/schemas/hypothesis_forge_synthesis_handoff_v1.schema.json"
CRITIC_INPUT_SCHEMA = ROOT / "catalog/schemas/hypothesis_critic_input_v1.schema.json"
PROJECTION_SQL = ROOT / "schemas/research_memory_projection_v1.sql"
FAST_LANE_CLI = ROOT / "scripts/hypothesis_fast_lane.py"
QUERY_RECIPES = ROOT / "catalog/query_recipes.yaml"
C3_C4_FIXTURE = ROOT / "tests/fixtures/hypothesis_forge/draft_c3_c4_mismatch_v1.json"
HANDOFF_COMPLETE_V10 = ROOT / "tests/fixtures/hypothesis_forge/synthesis_handoff_complete_v1.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def schema_errors(document: dict[str, Any], schema_path: Path) -> list[str]:
    schema = load_json(schema_path)
    return [error.message for error in Draft202012Validator(schema).iter_errors(document)]


class HficOperationalClosureContractTests(unittest.TestCase):
    def test_config_is_hfic_v1_2_without_breaking_manual_fallback(self) -> None:
        config = load_yaml(CONFIG_PATH)
        self.assertEqual(config["prompt_version"], "HFIC-V1.2")
        self.assertEqual(config["generator_mode"], "MANUAL_FALLBACK_UNTIL_GENERATOR")
        self.assertEqual(config["runtime_mode"], "EXPLICIT_SLASH_ONLY")
        self.assertTrue(config["commissioning_gate"]["auto_commission_offline_when_safe"])
        self.assertEqual(
            config["commissioning_gate"]["required_owner_terminal"],
            "NO_GIT_FAST_LANE_PROVEN",
        )
        self.assertEqual(config["search_budget"]["auto_sessions_per_evidence_epoch"], 1)
        self.assertEqual(config["search_budget"]["distinct_focus_sessions_per_evidence_epoch"], 3)
        self.assertEqual(config["candidate_policy"]["min_candidates"], 4)
        self.assertEqual(config["candidate_policy"]["max_candidates"], 6)
        schemas = config["schemas"]
        self.assertTrue(str(schemas["forge_draft"]).endswith("hypothesis_forge_draft_v1_2.schema.json"))
        self.assertTrue(str(schemas["forge_draft_v1_1"]).endswith("hypothesis_forge_draft_v1.schema.json"))
        self.assertTrue(
            str(schemas["session_receipt"]).endswith("hypothesis_forge_session_receipt_v1_2.schema.json")
        )
        self.assertTrue(
            str(schemas["session_receipt_v1_1"]).endswith("hypothesis_forge_session_receipt_v1.schema.json")
        )

    def test_v1_0_handoff_fixture_remains_readable(self) -> None:
        handoff = load_json(HANDOFF_COMPLETE_V10)
        self.assertEqual(schema_errors(handoff, HANDOFF_V10_SCHEMA), [])

    def test_c3_c4_fixture_exists_as_negative_draft(self) -> None:
        draft = load_json(C3_C4_FIXTURE)
        self.assertEqual(draft["generator_prompt_version"], "HFIC-V1.1")
        self.assertNotEqual(
            draft["runner_up_candidate_ref"],
            draft["strongest_rejected_alternative"],
        )
        self.assertIn("C3", draft["runner_up_candidate_ref"])
        self.assertIn("C4", draft["strongest_rejected_alternative"])

    def test_new_schemas_exist_and_are_objects(self) -> None:
        for path in (
            DRAFT_SCHEMA,
            CRITIC_RESULT_SCHEMA,
            SESSION_RECEIPT_SCHEMA,
            HANDOFF_V11_SCHEMA,
        ):
            schema = load_json(path)
            self.assertEqual(schema["type"], "object")
            self.assertFalse(schema.get("additionalProperties", True))

    def test_critic_input_accepts_v1_1_writes_and_v1_0_reads(self) -> None:
        schema = load_json(CRITIC_INPUT_SCHEMA)
        version = schema["properties"]["generator_prompt_version"]
        allowed = version.get("enum") or [version.get("const")]
        self.assertIn("HFIC-V1.0", allowed)
        self.assertIn("HFIC-V1.1", allowed)
        self.assertIn("HFIC-V1.2", allowed)
        self.assertIn("session_id", schema["properties"])
        self.assertEqual(
            schema["properties"]["session_id"]["pattern"],
            "^HFIC-SESS-[A-Z0-9]+$",
        )

    def test_projection_declares_hfic_views(self) -> None:
        sql = PROJECTION_SQL.read_text(encoding="utf-8")
        for view in (
            "hfic_sessions",
            "hfic_candidates",
            "hfic_candidate_decisions",
            "hfic_search_budget",
            "hfic_pending_sessions",
        ):
            self.assertIn(view, sql)

    def test_fast_lane_cli_imports_shared_data_root(self) -> None:
        text = FAST_LANE_CLI.read_text(encoding="utf-8")
        self.assertIn("from solana_alpha_lab.factory.data_root import", text)
        self.assertNotIn("def resolve_data_root(", text)

    def test_query_recipes_register_hfic_lookups(self) -> None:
        recipes = load_yaml(QUERY_RECIPES)
        by_id = {item["recipe_id"]: item for item in recipes["recipes"]}
        self.assertIn("QUERY-HFIC-SESSION-BY-SEARCH-KEY-001", by_id)
        self.assertIn("QUERY-HFIC-PENDING-SESSION-001", by_id)
        self.assertIn("QUERY-HFIC-PLACEHOLDER-TIME-INVENTORY-001", by_id)
        self.assertIn("--search-key", by_id["QUERY-HFIC-SESSION-BY-SEARCH-KEY-001"]["command"])
        self.assertIn("pending", by_id["QUERY-HFIC-PENDING-SESSION-001"]["command"])

    def test_forge_skill_is_executable_preflight_freeze_finalize(self) -> None:
        text = FORGE_SKILL_PATH.read_text(encoding="utf-8")
        self.assertIn("hypothesis_forge.py", text)
        self.assertIn("preflight", text)
        self.assertIn("freeze", text)
        self.assertIn("finalize", text)
        self.assertIn("HFIC-V1.1", text)
        self.assertIn("HFIC-V1.2", text)
        self.assertIn("RETURN_EXISTING_SESSION", text)
        self.assertIn("RESUME_CRITIC", text)
        self.assertIn("FORGE_DRAFT", text)
        self.assertIn("RESUME_REVISE", text)
        self.assertIn("RESUME_CLASSIFY", text)
        self.assertIn("hypothesis_forge.py revise", text)
        self.assertIn("hypothesis_forge.py classify", text)
        self.assertNotRegex(text, re.compile(r"Execute \*\*PROMPT A\*\* from the operator pack \(`HFIC-V1\.0`\)"))

    def test_critic_skill_returns_result_schema_and_does_not_persist(self) -> None:
        text = CRITIC_SKILL_PATH.read_text(encoding="utf-8")
        self.assertIn("hypothesis_critic_result_v1", text)
        self.assertIn("does not persist", text.casefold())
        self.assertIn("finalize", text.casefold())
        self.assertIn("copied/bound", text.casefold())
        operator = OPERATOR_PATH.read_text(encoding="utf-8")
        self.assertIn("copied/bound", operator)
        self.assertIn("HFIC-UNBOUND", operator)
        self.assertIn("INCOMPLETE_CRITIC_INPUT_PACKET", operator)
        self.assertIn("CRITIC_SESSION_MISMATCH", operator)

    def test_slash_command_happy_path_is_single_owner_action(self) -> None:
        text = FORGE_COMMAND_PATH.read_text(encoding="utf-8")
        self.assertIn("preflight", text)
        self.assertIn("revise", text)
        self.assertIn("classify", text)
        self.assertIn("no owner copy/paste", text.casefold())
        self.assertIn("ZERO_MID_CYCLE_OWNER_INTERVENTION", text)
        self.assertIn("PASS_TO_CLASSIFICATION", text)
        self.assertIn("REVISE_ONCE", text)
        self.assertIn("AUTO_HANDOFF_UNAVAILABLE", text)

    def test_slash_skill_operator_config_zero_mid_cycle_authority(self) -> None:
        config = load_yaml(CONFIG_PATH)
        authority = config["slash_session_authority"]
        self.assertEqual(authority["mid_cycle_owner_interventions"], 0)
        self.assertEqual(authority["token"], "ZERO_MID_CYCLE_OWNER_INTERVENTION")
        self.assertIn("PASS_TO_CLASSIFICATION", authority["auto_continue"])
        self.assertIn("REVISE_ONCE", authority["auto_continue"])
        self.assertEqual(authority["isolated_critic_unavailable"], "AUTO_HANDOFF_UNAVAILABLE")
        for path in (FORGE_SKILL_PATH, OPERATOR_PATH, FORGE_COMMAND_PATH):
            text = path.read_text(encoding="utf-8")
            self.assertIn("ZERO_MID_CYCLE_OWNER_INTERVENTION", text)
            self.assertIn("PASS_TO_CLASSIFICATION", text)
            self.assertIn("REVISE_ONCE", text)
            self.assertIn("AUTO_HANDOFF_UNAVAILABLE", text)

    def test_operator_pack_mentions_v1_1_and_keeps_prompts(self) -> None:
        text = OPERATOR_PATH.read_text(encoding="utf-8")
        self.assertIn("HFIC-V1.1", text)
        self.assertIn("HFIC-V1.2", text)
        self.assertIn("BEGIN PROMPT A", text)
        self.assertIn("END PROMPT A", text)
        self.assertIn("BEGIN PROMPT B", text)
        self.assertIn("display-only", text.casefold())
        self.assertIn("FORGE_DRAFT", text)
        self.assertIn("hypothesis_forge_draft_v1", text)
        self.assertIn("hypothesis_forge.py revise", text)
        self.assertIn("hypothesis_forge.py classify", text)

    def test_prompt_a_fixture_is_schema_valid_forge_draft(self) -> None:
        draft = load_json(ROOT / "tests/fixtures/hypothesis_forge/prompt_a_forge_draft_v1.json")
        self.assertEqual(schema_errors(draft, DRAFT_SCHEMA), [])
        self.assertEqual(draft["generator_prompt_version"], "HFIC-V1.1")

    def test_hfic_python_tests_do_not_nest_uv(self) -> None:
        for path in (
            ROOT / "tests/test_hfic_cli.py",
            ROOT / "tests/test_hfic_session.py",
            ROOT / "tests/test_hfic_preflight.py",
            ROOT / "tests/test_hfic_provenance_clock.py",
            ROOT / "tests/test_hfic_forge_context_and_no_worthy.py",
            ROOT / "tests/test_hfic_discovery_prospects_and_next_action.py",
        ):
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("uv run", text)
            if path.name in {
                "test_hfic_cli.py",
                "test_hfic_forge_context_and_no_worthy.py",
                "test_hfic_discovery_prospects_and_next_action.py",
            }:
                self.assertIn("sys.executable", text)
                self.assertIn("-B", text)

    def test_operator_hfic_commands_use_canonical_managed_python_prefix(self) -> None:
        config = load_yaml(CONFIG_PATH)
        prefix = " ".join(config["cli"]["operator_invocation_prefix"])
        self.assertEqual(
            prefix,
            "uv run --locked --managed-python python -B scripts/hypothesis_forge.py",
        )
        self.assertEqual(config["cli"]["required_python"], "3.13.14")
        bare = re.compile(r"(?<!managed-python )python -B scripts/hypothesis_forge\.py")
        for path in (FORGE_SKILL_PATH, FORGE_COMMAND_PATH, OPERATOR_PATH):
            text = path.read_text(encoding="utf-8")
            self.assertIn(prefix, text)
            self.assertIsNone(bare.search(text), path)

    def test_runtime_python_pin_is_aligned(self) -> None:
        pin = (ROOT / ".python-version").read_text(encoding="utf-8").strip()
        self.assertEqual(pin, "3.13.14")
        pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn('exact_python_pin = "3.13.14"', pyproject)
        self.assertIn('requires-python = ">=3.13,<3.14"', pyproject)
        cli = (ROOT / "scripts/hypothesis_forge.py").read_text(encoding="utf-8")
        self.assertIn('HFIC_REQUIRED_PYTHON = "3.13.14"', cli)
        self.assertLess(
            cli.index("enforce_hfic_runtime_python()"),
            cli.index("from solana_alpha_lab.factory"),
        )
