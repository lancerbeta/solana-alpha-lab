from __future__ import annotations

import importlib.util
import re
import shutil
import tempfile
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
AGENTS = ROOT / "AGENTS.md"
DOMAIN_POLICY = ROOT / "delivery-harness/policies/solana-alpha-lab.md"
CURSOR = ROOT / ".cursor"
SCRIPT = ROOT / "scripts/delivery_harness.py"


def load_module():
    spec = importlib.util.spec_from_file_location("delivery_harness", SCRIPT)
    if spec is None or spec.loader is None:
        raise AssertionError("delivery harness import unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def frontmatter(path: Path) -> dict[str, object]:
    text = path.read_text(encoding="utf-8")
    match = re.match(r"\A---\n(.*?)\n---\n", text, flags=re.DOTALL)
    if match is None:
        raise AssertionError(f"frontmatter missing: {path}")
    value = yaml.safe_load(match.group(1))
    if not isinstance(value, dict):
        raise AssertionError(f"frontmatter mapping required: {path}")
    return value


class DeliveryHarnessAdapterTests(unittest.TestCase):
    def test_root_front_door_is_lean_and_reaches_exact_policy_owners(self) -> None:
        text = AGENTS.read_text(encoding="utf-8")
        self.assertLessEqual(len(AGENTS.read_bytes()), 12 * 1024)
        for path in (
            "delivery-harness/harness.yaml",
            "delivery-harness/project-profile.yaml",
            "delivery-harness/context-map.yaml",
            "delivery-harness/policies/solana-alpha-lab.md",
            "control/owner_attention_gate_v2.yaml",
            "docs/agent/DELIVERY_HARNESS_PROTOCOL.md",
        ):
            self.assertIn(path, text)
        self.assertIn("Git is the working project-memory owner", text)
        self.assertIn(".cursor/rules/10-input-routing.mdc", text)
        self.assertIn("OWNER_MANAGED_OPTIONAL_EXPORT", text)
        self.assertIn("never request its replacement or smoke", text)
        self.assertIn("never clicks GitHub Merge", text)
        self.assertNotIn("PROJECT_CHAT_PRO_GITHUB_BATON_CURSOR", text)
        self.assertNotIn("GITHUB_BATON:", text)

    def test_solana_policy_preserves_deep_invariants_reachable_from_root(self) -> None:
        self.assertTrue(DOMAIN_POLICY.is_file())
        root = AGENTS.read_text(encoding="utf-8")
        self.assertIn("delivery-harness/policies/solana-alpha-lab.md", root)
        policy = DOMAIN_POLICY.read_text(encoding="utf-8")
        required = (
            "## ACTIVE_TIME_GATE_CHECK",
            "CONFIG-PROVIDER-ROUTE-CAPABILITY-REGISTRY-010",
            "exact_role_asset_ids",
            "REGISTRY_GAP",
            "## REUSE_FIRST_RECOVERY_TRIGGER",
            "## TRACKED_ONLY_DELIVERY_PREFLIGHT",
            "## CI_OWNED_DELIVERY_PILOT",
            "## CONTROL_ONLY_TASK_CLOSE_FAST_PATH",
            "## FACTORY_LEVERAGE_INVARIANT",
            "## MODEL_EFFORT_ROUTER",
            "## FACTORY_FIT_REVIEW",
            "## IMPORTED_BYTES_AND_ADVISORY_CONTEXT",
        )
        for marker in required:
            self.assertIn(marker, policy)
        self.assertIn("HISTORICAL_OPTIONAL_EXPORT_NON_TRIGGERING", policy)
        self.assertIn("first_reliable_available_at", policy)
        self.assertIn("Import or backfill never creates retroactive availability", policy)
        self.assertIn("External analytical context such as AOT/ALBS is advisory only", policy)
        self.assertIn("cannot command", policy)
        self.assertIn("bypass holdout, risk, execution, inventory", policy)
        self.assertIn("MUST NOT", AGENTS.read_text(encoding="utf-8"))

    def test_cursor_rules_are_native_scoped_and_within_always_context_budget(self) -> None:
        rules = sorted((CURSOR / "rules").glob("*.mdc"))
        self.assertEqual(
            {path.name for path in rules},
            {
                "00-authority.mdc",
                "05-language-and-reporting.mdc",
                "10-input-routing.mdc",
                "20-validation.mdc",
                "30-security-and-secrets.mdc",
                "40-catalog-and-evidence.mdc",
                "50-factory-remote-host.mdc",
            },
        )
        always = []
        for path in rules:
            metadata = frontmatter(path)
            self.assertEqual(set(metadata), {"description", "globs", "alwaysApply"})
            self.assertIs(type(metadata["alwaysApply"]), bool)
            if metadata["alwaysApply"] is True:
                always.append(path)
            else:
                self.assertTrue(metadata["description"])
        self.assertEqual(
            {path.name for path in always},
            {
                "00-authority.mdc",
                "10-input-routing.mdc",
                "30-security-and-secrets.mdc",
                "50-factory-remote-host.mdc",
            },
        )
        self.assertLessEqual(sum(path.stat().st_size for path in always), 6 * 1024)

    def test_input_routing_discriminates_orientation_from_execute(self) -> None:
        authority = (CURSOR / "rules/00-authority.mdc").read_text(encoding="utf-8")
        routing = (CURSOR / "rules/10-input-routing.mdc").read_text(encoding="utf-8")
        agents = AGENTS.read_text(encoding="utf-8")
        self.assertIn("Mutate, deliver and merge only from an exact task contract", authority)
        self.assertIn("Orientation may inspect Git truth without a new contract", authority)
        self.assertIn("## ORIENTATION", routing)
        self.assertIn("## EXECUTE", routing)
        self.assertIn("## NEITHER", routing)
        self.assertIn("OWNER_DECISION", routing)
        self.assertIn(".agents/skills/delivery-harness/SKILL.md", routing)
        self.assertIn("scripts/delivery_harness.py check", routing)
        self.assertIn("`ORIENTATION` versus `EXECUTE`", agents)
        self.assertIn("On `ORIENTATION`, do not start that workflow.", agents)
        self.assertNotRegex(
            routing,
            r"\A---\n.*\n---\nUse `.agents/skills/delivery-harness/SKILL.md`",
        )

    def test_no_active_cursor_adapter_can_reactivate_baton(self) -> None:
        self.assertFalse((CURSOR / "rules/50-github-baton.mdc").exists())
        self.assertFalse((CURSOR / "commands/baton-preflight.md").exists())
        forbidden = (
            "GITHUB_BATON",
            "PROJECT_CHAT_PRO_GITHUB_BATON_CURSOR",
            "baton-preflight",
            "Cursor never merges",
        )
        for path in CURSOR.rglob("*"):
            if path.is_file():
                text = path.read_text(encoding="utf-8")
                for phrase in forbidden:
                    self.assertNotIn(phrase, text, f"{path}: {phrase}")
        for historical in (
            "scripts/baton_preflight.py",
            "scripts/baton_receipt.py",
            "tests/test_baton_contract.py",
            "docs/agent/GITHUB_BATON_PROTOCOL.md",
        ):
            self.assertTrue((ROOT / historical).is_file(), historical)

    def test_machine_check_rejects_baton_reactivation_in_any_active_adapter(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            shutil.copytree(ROOT / ".cursor", target / ".cursor")
            shutil.copytree(ROOT / ".agents", target / ".agents")
            shutil.copytree(ROOT / "delivery-harness", target / "delivery-harness")
            shutil.copytree(ROOT / "catalog/schemas", target / "catalog/schemas")
            (target / "AGENTS.md").write_bytes(AGENTS.read_bytes())
            injected = target / ".cursor/commands/delivery-start.md"
            injected.write_text(
                injected.read_text(encoding="utf-8")
                + "\nRun python -m scripts.baton_preflight as an active transport.\n",
                encoding="utf-8",
            )
            result = module.check_harness(target)
            self.assertIn("ACTIVE_BATON_REFERENCE", result["errors"])

    def test_commands_are_thin_exact_task_adapters(self) -> None:
        delivery_names = {
            "delivery-start.md",
            "delivery-status.md",
            "delivery-review.md",
            "delivery-finish.md",
        }
        product_names = {
            "hypothesis-forge.md",
            "independent-hypothesis-critic.md",
        }
        commands = {path.name: path for path in (CURSOR / "commands").glob("*.md")}
        self.assertEqual(set(commands), delivery_names | product_names)
        for name in delivery_names:
            path = commands[name]
            text = path.read_text(encoding="utf-8")
            self.assertIn("DELIVERY_HARNESS_V1", text, name)
            self.assertIn("scripts/delivery_harness.py", text, name)
            self.assertIn("exact task contract", text.casefold(), name)
            self.assertNotRegex(text.casefold(), r"search (the )?(latest|newest|current)")

    def test_product_slash_commands_are_explicit_manual_contours(self) -> None:
        product = {
            "hypothesis-forge.md": {
                "skill": ".agents/skills/hypothesis-forge/SKILL.md",
                "required": (
                    "MANUAL_FALLBACK_UNTIL_GENERATOR",
                    "auto-launch",
                    "incomplete",
                ),
            },
            "independent-hypothesis-critic.md": {
                "skill": ".agents/skills/independent-hypothesis-critic/SKILL.md",
                "required": (
                    "CRITIC_INPUT_PACKET",
                    "new chat",
                ),
            },
        }
        for name, spec in product.items():
            path = CURSOR / "commands" / name
            text = path.read_text(encoding="utf-8")
            self.assertIn(spec["skill"], text, name)
            for phrase in spec["required"]:
                self.assertIn(phrase.casefold(), text.casefold(), name)
            self.assertNotIn("DELIVERY_HARNESS_V1", text, name)
            self.assertNotIn("GITHUB_BATON", text, name)

    def test_custom_critics_are_read_only_and_have_deterministic_fallback(self) -> None:
        expected = {
            "code-reviewer",
            "goal-dod-critic",
            "architecture-critic",
            "refactor-critic",
            "owner-ux-critic",
        }
        paths = sorted((CURSOR / "agents").glob("*.md"))
        self.assertEqual({frontmatter(path)["name"] for path in paths}, expected)
        for path in paths:
            metadata = frontmatter(path)
            self.assertEqual(metadata["model"], "inherit")
            self.assertIs(metadata["readonly"], True)
            text = path.read_text(encoding="utf-8")
            self.assertIn("exact task contract", text.casefold())
            self.assertIn("exact diff", text.casefold())
            self.assertIn("SINGLE_AGENT_REVIEW_FALLBACK", text)
            self.assertIn("merge is denied", text.casefold())

    def test_agents_front_door_denies_fallback_at_merge(self) -> None:
        text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("SINGLE_AGENT_REVIEW_FALLBACK", text)
        self.assertIn("`NOT_READY` for merge", text)
        module = load_module()
        self.assertEqual(
            module.detect_multi_root_context_duplication(
                [ROOT, ROOT / ".worktrees/example"]
            ),
            ["MULTI_ROOT_CONTEXT_DUPLICATION_WARNING"],
        )
        receipt = {"route": "DIRECT_CURSOR_DELIVERY"}
        self.assertEqual(module.validate_route_continuity(receipt, "DIRECT_CURSOR_DELIVERY"), [])
        self.assertEqual(
            module.validate_route_continuity(receipt, "DIRECT_CODEX_DELIVERY"),
            ["ACTIVE_ROUTE_CHANGED"],
        )

    def test_owner_facing_bootstrap_keeps_cloud_export_optional(self) -> None:
        paths = (
            ROOT / "docs/agent/DELIVERY_HARNESS_BOOTSTRAP.md",
            ROOT / "docs/agent/DELIVERY_HARNESS_PROTOCOL.md",
            ROOT / "docs/agent/PROJECT_INSTRUCTION_V3_6.md",
            ROOT / "delivery-harness/templates/bootstrap-prompt.md",
        )
        for path in paths:
            text = path.read_text(encoding="utf-8")
            self.assertIn("OWNER_MANAGED_OPTIONAL_EXPORT", text, path)
            self.assertNotIn("SMOKE=PASS", text, path)
            self.assertNotIn("send smoke", text.casefold(), path)
        self.assertLessEqual(
            len((ROOT / "docs/agent/PROJECT_INSTRUCTION_V3_6.md").read_text(encoding="utf-8")),
            8000,
        )


if __name__ == "__main__":
    unittest.main()
