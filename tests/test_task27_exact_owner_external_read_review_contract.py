from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REQUIRED_PATHS = (
    ROOT / "docs/contracts/task27_exact_owner_external_read_review_contract_v1.md",
    ROOT / "configs/task27_exact_owner_external_read_review_contract_v1.yaml",
    ROOT / "catalog/schemas/task27_exact_owner_external_read_review.schema.json",
    ROOT / "tests/fixtures/task27/exact_owner_external_read_review_v1.json",
)


class ExactOwnerExternalReadReviewContractTests(unittest.TestCase):
    def test_required_review_assets_exist(self) -> None:
        for path in REQUIRED_PATHS:
            with self.subTest(path=path):
                self.assertTrue(path.is_file(), path)


if __name__ == "__main__":
    unittest.main()
