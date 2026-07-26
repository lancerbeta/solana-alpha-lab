# tests/test_baton_cursorignore.py
from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class CursorIgnoreTests(unittest.TestCase):
    def test_cursorignore_blocks_secrets_allows_env_example(self) -> None:
        text = (ROOT / ".cursorignore").read_text(encoding="utf-8")
        self.assertIn(".env", text)
        self.assertIn(".env.*", text)
        self.assertIn("!.env.example", text)
        self.assertIn(".smial-handoff/**", text)
        self.assertIn("wallet/**", text)
        self.assertIn("secrets/**", text)
        # Ordering: negation after .env.* so placeholder remains visible when supported.
        env_star = text.index(".env.*")
        allow = text.index("!.env.example")
        self.assertGreater(allow, env_star)
        # Must not block contracts/tests/AGENTS
        for forbidden_block in ["AGENTS.md", "docs/contracts/", "tests/", "catalog/"]:
            self.assertNotIn(forbidden_block + "\n", text)


if __name__ == "__main__":
    unittest.main()
