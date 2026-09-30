"""Owner question -> semantic route -> binding -> contract -> ordinary read command.

A Markdown file existing is not navigation. This walks the real Catalog CLI.
"""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CATALOG_CLI = ROOT / "scripts" / "catalog_cli.py"
FORGE_CLI = ROOT / "scripts" / "hypothesis_forge.py"


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-B", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )


class DispositionNavigationTests(unittest.TestCase):
    def test_owner_phrasings_reach_the_read_command(self) -> None:
        for question in (
            "Что уже заключили по этой работе, почему остановились?",
            "What did we already conclude about this question or search scope?",
            "прошлый вывод по вопросу",
        ):
            with self.subTest(question=question):
                found = _run(str(CATALOG_CLI), "search-routes", "--text", question, "--limit", "3", "--json")
                self.assertEqual(found.returncode, 0, found.stderr)
                self.assertEqual(json.loads(found.stdout)[0]["semantic_route_id"], "SEM-PRIOR-WORK")
        resolved = _run(str(CATALOG_CLI), "resolve-route", "SEM-PRIOR-WORK", "--json")
        self.assertEqual(resolved.returncode, 0, resolved.stderr)
        route = json.loads(resolved.stdout)
        self.assertFalse(route["authority_granted"])
        bindings = {item["binding_id"]: item for item in route["root_bindings"]}
        doc = bindings["ACTIVE-SCIENTIFIC-DISPOSITION-CONTINUITY"]
        self.assertEqual(doc["target_asset_id"], "DOC-HFIC-SCIENTIFIC-DISPOSITION-CONTINUITY-001")
        text = (ROOT / doc["path"]).read_text(encoding="utf-8")
        self.assertIn("scripts/hypothesis_forge.py disposition-show --owner-focus", text)
        self.assertIn("scripts/hypothesis_forge.py disposition-record --input", text)
        helped = _run(str(FORGE_CLI), "disposition-show", "--help")
        self.assertEqual(helped.returncode, 0, helped.stderr)
        self.assertIn("--owner-focus", helped.stdout)

    def test_route_limits_and_prior_recipes_are_unchanged(self) -> None:
        config = yaml.safe_load((ROOT / "configs/factory_semantic_operability_v1.yaml").read_text(encoding="utf-8"))
        limits = config["limits"]
        self.assertEqual(
            (limits["max_routes"], limits["max_root_bindings_per_route"], limits["max_root_assets_per_route"], limits["max_query_recipes_per_route"], limits["max_search_terms_per_route"]),
            (13, 2, 3, 4, 16),
        )
        routes = {item["semantic_route_id"]: item for item in config["routes"]}
        prior = routes["SEM-PRIOR-WORK"]
        self.assertEqual(
            prior["query_recipe_ids"],
            [
                "QUERY-HFIC-EXACT-RELATED-PRIOR-001",
                "QUERY-HYPOTHESIS-FAST-LANE-SEARCH-PRIOR-WORK-001",
                "QUERY-HFIC-SESSION-BY-SEARCH-KEY-001",
                "QUERY-HFIC-PENDING-SESSION-001",
            ],
        )
        self.assertEqual(len(prior["root_asset_ids"]), 3)
        self.assertEqual(len(config["routes"]), 13)


if __name__ == "__main__":
    unittest.main()
