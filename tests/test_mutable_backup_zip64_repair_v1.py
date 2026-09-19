"""Regression: streamed backup ZIP entries must request ZIP64-safe writes."""

from __future__ import annotations

import hashlib
import inspect
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.remote_ops import _stream_zip_entry  # noqa: E402


class Zip64RequiredFile(zipfile.ZipFile):
    """Reproduce the live close-time ZIP64 miss without a 2 GiB fixture."""

    def open(self, name, mode="r", pwd=None, *, force_zip64=False):
        if mode in {"w", "x"} and force_zip64 is not True:
            raise RuntimeError("File size too large, try using force_zip64")
        return super().open(name, mode, pwd, force_zip64=force_zip64)


class MutableBackupZip64RepairTests(unittest.TestCase):
    def test_stream_zip_entry_requests_force_zip64(self) -> None:
        source_text = inspect.getsource(_stream_zip_entry)
        self.assertIn("force_zip64=True", source_text)
        self.assertNotIn("read_bytes()", source_text)

        payload = b"zip64-safe-small-payload"
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "small.bin"
            source.write_bytes(payload)
            dest = Path(tmp) / "out.zip"
            with Zip64RequiredFile(
                dest,
                mode="w",
                compression=zipfile.ZIP_STORED,
                allowZip64=True,
            ) as archive:
                digest, size = _stream_zip_entry(archive, "small.bin", source)
            self.assertEqual(size, len(payload))
            self.assertEqual(digest, hashlib.sha256(payload).hexdigest())
            with zipfile.ZipFile(dest) as archive:
                self.assertEqual(archive.read("small.bin"), payload)
                self.assertNotIn("BACKUP_MANIFEST.json", archive.namelist())


if __name__ == "__main__":
    unittest.main()
