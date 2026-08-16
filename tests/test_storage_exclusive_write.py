from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.storage.exclusive import (  # noqa: E402
    CREATED,
    REPLAY_IDENTICAL,
    ExclusiveWriteConflict,
    ExclusiveWriteError,
    write_exclusive_bytes,
    write_exclusive_text,
)


class ExclusiveWriteTests(unittest.TestCase):
    def test_create_replay_and_conflict_leave_original_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "raw_response.json"
            first, outcome = write_exclusive_bytes(path, b'{"ok":true}')
            self.assertEqual(outcome, CREATED)
            self.assertEqual(path.read_bytes(), b'{"ok":true}')
            replay, replay_outcome = write_exclusive_bytes(path, b'{"ok":true}')
            self.assertEqual(replay_outcome, REPLAY_IDENTICAL)
            self.assertEqual(replay, first)
            with self.assertRaisesRegex(ExclusiveWriteConflict, "EXCLUSIVE_WRITE_CONFLICT"):
                write_exclusive_bytes(path, b'{"ok":false}')
            self.assertEqual(path.read_bytes(), b'{"ok":true}')

    def test_text_replay_and_reject_non_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "raw_manifest_v1.json"
            write_exclusive_text(path, '{"n":1}\n')
            digest, outcome = write_exclusive_text(path, '{"n":1}\n')
            self.assertEqual(outcome, REPLAY_IDENTICAL)
            self.assertEqual(len(digest), 64)
            with self.assertRaisesRegex(ExclusiveWriteError, "BODY_NOT_BYTES"):
                write_exclusive_bytes(path, "not-bytes")  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
