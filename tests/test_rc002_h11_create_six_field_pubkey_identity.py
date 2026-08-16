from __future__ import annotations

import ast
import base64
import json
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.pump_event_decoder import (  # noqa: E402
    PROGRAM_DATA_PREFIX,
    PUMP_PROGRAM_ID,
    load_pinned_pump_event_plan,
)
from solana_alpha_lab.rc002_h11_create_early_six_field_layout import (  # noqa: E402
    GETTX_FIXTURE_RELATIVE,
)
from solana_alpha_lab.rc002_h11_create_six_field_pubkey_identity import (  # noqa: E402
    ATOM_ID,
    EXPECTED_BONDING_CURVE,
    EXPECTED_NAMED_MINT,
    TASK40_ACCEPTANCE_RELATIVE,
    TERMINAL_OUTCOMES,
    classify_gettransaction_fixture_identity,
    decide_identity_terminal,
    encode_solana_base58,
    identify_create_payloads,
    load_task40_named_identities,
    parse_six_field_create_payload,
    scan_retained_a4_create_pubkey_identity,
)

IDL_PATH = ROOT / "tests/fixtures/task08/pump_event_idl_subset_v1.json"
CONTRACT_PATH = ROOT / (
    "docs/tasks/RC002-H11-CREATE-SIX-FIELD-PUBKEY-IDENTITY-OFFLINE-V1.md"
)
PINNED_DECODER = ROOT / "src/solana_alpha_lab/pump_event_decoder.py"
MODULE_PATH = ROOT / "src/solana_alpha_lab/rc002_h11_create_six_field_pubkey_identity.py"
PRIVATE_DECODER_NAMES = {
    "_BorshReader",
    "_base58_encode",
    "_EXPECTED_CREATE_FIELDS",
    "_decode_type",
    "decode_pump_program_data",
}


def _b58_decode(text: str) -> bytes:
    alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    number = 0
    for char in text:
        number = number * 58 + alphabet.index(char)
    raw = number.to_bytes(32, "big")
    return raw


def _string_bytes(value: str) -> bytes:
    encoded = value.encode("utf-8")
    return struct.pack("<I", len(encoded)) + encoded


def _six_field_body(
    *,
    name: str,
    symbol: str,
    uri: str,
    mint: bytes,
    bonding_curve: bytes,
    user: bytes,
    extra: bytes = b"",
) -> bytes:
    return (
        _string_bytes(name)
        + _string_bytes(symbol)
        + _string_bytes(uri)
        + mint
        + bonding_curve
        + user
        + extra
    )


def _program_data_line(payload: bytes) -> str:
    return PROGRAM_DATA_PREFIX + base64.b64encode(payload).decode("ascii")


def _pump_logs(*payloads: bytes) -> list[str]:
    logs = [f"Program {PUMP_PROGRAM_ID} invoke [1]"]
    logs.extend(_program_data_line(payload) for payload in payloads)
    logs.append(f"Program {PUMP_PROGRAM_ID} success")
    return logs


class CreateSixFieldPubkeyIdentityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.pinned = load_pinned_pump_event_plan(IDL_PATH)
        cls.create = next(event for event in cls.pinned.events if event.name == "CreateEvent")
        cls.discriminator = cls.create.discriminator
        identities = load_task40_named_identities(ROOT)
        cls.named_mint = identities["named_mint"]
        cls.bonding_curve = identities["bonding_curve"]
        cls.mint_raw = _b58_decode(cls.named_mint)
        cls.curve_raw = _b58_decode(cls.bonding_curve)
        cls.user_raw = bytes(range(32))

    def test_contract_names_identity_atom_and_offline_caps(self) -> None:
        text = CONTRACT_PATH.read_text(encoding="utf-8")
        self.assertIn(
            "task_id: RC002-H11-CREATE-SIX-FIELD-PUBKEY-IDENTITY-OFFLINE-V1",
            text,
        )
        self.assertIn("network: false", text)
        self.assertIn("CREATE_PUBKEYS_MATCH_NAMED_MINT_AND_BONDING_CURVE", text)
        self.assertIn("CREATE_PUBKEYS_MISMATCH", text)
        self.assertIn("CREATE_BODY_NOT_SIX_FIELD", text)
        self.assertIn("CREATE_BODY_ABSENT", text)
        self.assertIn("PINNED_PUMP_DECODER_MUTATION", text)
        self.assertIn("CREATE_AT_FROM_BLOCKTIME", text)
        self.assertIn("DMwbVy48dWVKGe9z1pcVnwF3HLMLrqWdDLfbvx8RchhK", text)
        self.assertIn("ENz3D4ZoarzHZCsGeFTfswAKrSo5sHX9UUut1FLS6WgC", text)
        self.assertEqual(ATOM_ID, "RC002-H11-CREATE-SIX-FIELD-PUBKEY-IDENTITY-OFFLINE-V1")
        self.assertEqual(
            TERMINAL_OUTCOMES,
            (
                "CREATE_PUBKEYS_MATCH_NAMED_MINT_AND_BONDING_CURVE",
                "CREATE_PUBKEYS_MISMATCH",
                "CREATE_BODY_NOT_SIX_FIELD",
                "CREATE_BODY_ABSENT",
            ),
        )
        self.assertTrue(PINNED_DECODER.is_file())

    def test_task40_named_identities_are_fail_closed(self) -> None:
        identities = load_task40_named_identities(ROOT)
        self.assertEqual(identities["named_mint"], EXPECTED_NAMED_MINT)
        self.assertEqual(identities["bonding_curve"], EXPECTED_BONDING_CURVE)
        self.assertEqual(
            identities["named_mint"],
            "DMwbVy48dWVKGe9z1pcVnwF3HLMLrqWdDLfbvx8RchhK",
        )
        self.assertEqual(
            identities["bonding_curve"],
            "ENz3D4ZoarzHZCsGeFTfswAKrSo5sHX9UUut1FLS6WgC",
        )
        receipt = json.loads((ROOT / TASK40_ACCEPTANCE_RELATIVE).read_text(encoding="utf-8"))
        self.assertEqual(receipt["named_mint"], identities["named_mint"])
        self.assertEqual(receipt["bonding_curve"], identities["bonding_curve"])

    def test_module_does_not_use_pinned_decoder_or_private_apis(self) -> None:
        source = MODULE_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "solana_alpha_lab.pump_event_decoder":
                imported.update(alias.name for alias in node.names)
            if isinstance(node, ast.Attribute) and node.attr in PRIVATE_DECODER_NAMES:
                self.fail(f"private_decoder_attr:{node.attr}")
        self.assertTrue({"PROGRAM_DATA_PREFIX", "MAX_STRING_BYTES", "load_pinned_pump_event_plan"} <= imported)
        self.assertNotIn("decode_pump_program_data", imported)
        self.assertTrue(imported.isdisjoint(PRIVATE_DECODER_NAMES))
        self.assertNotIn("from solana_alpha_lab.pump_event_decoder import _", source)

    def test_matching_six_field_payload_hits_match_terminal(self) -> None:
        payload = self.discriminator + _six_field_body(
            name="Cope",
            symbol="Cope",
            uri="https://example.invalid/uri",
            mint=self.mint_raw,
            bonding_curve=self.curve_raw,
            user=self.user_raw,
        )
        parsed = parse_six_field_create_payload(payload, discriminator=self.discriminator)
        self.assertEqual(parsed["status"], "OK")
        self.assertEqual(parsed["mint"], self.named_mint)
        self.assertEqual(parsed["bonding_curve"], self.bonding_curve)
        self.assertEqual(parsed["user"], encode_solana_base58(self.user_raw))
        result = identify_create_payloads(
            [payload],
            discriminator=self.discriminator,
            named_mint=self.named_mint,
            bonding_curve=self.bonding_curve,
        )
        self.assertEqual(
            decide_identity_terminal(result),
            "CREATE_PUBKEYS_MATCH_NAMED_MINT_AND_BONDING_CURVE",
        )

    def test_wrong_mint_is_mismatch(self) -> None:
        payload = self.discriminator + _six_field_body(
            name="Cope",
            symbol="Cope",
            uri="https://example.invalid/uri",
            mint=bytes([9]) * 32,
            bonding_curve=self.curve_raw,
            user=self.user_raw,
        )
        result = identify_create_payloads(
            [payload],
            discriminator=self.discriminator,
            named_mint=self.named_mint,
            bonding_curve=self.bonding_curve,
        )
        self.assertEqual(decide_identity_terminal(result), "CREATE_PUBKEYS_MISMATCH")
        self.assertNotEqual(result["observed"][0]["mint"], self.named_mint)

    def test_trailing_or_truncated_is_not_six_field(self) -> None:
        trailing = self.discriminator + _six_field_body(
            name="Cope",
            symbol="Cope",
            uri="https://example.invalid/uri",
            mint=self.mint_raw,
            bonding_curve=self.curve_raw,
            user=self.user_raw,
            extra=b"\x00",
        )
        truncated = self.discriminator + _six_field_body(
            name="Cope",
            symbol="Cope",
            uri="https://example.invalid/uri",
            mint=self.mint_raw,
            bonding_curve=self.curve_raw,
            user=self.user_raw,
        )[:-8]
        trailing_parsed = parse_six_field_create_payload(
            trailing, discriminator=self.discriminator
        )
        truncated_parsed = parse_six_field_create_payload(
            truncated, discriminator=self.discriminator
        )
        self.assertEqual(trailing_parsed["status"], "TRAILING")
        self.assertEqual(truncated_parsed["status"], "TRUNCATED")
        trailing_result = identify_create_payloads(
            [trailing],
            discriminator=self.discriminator,
            named_mint=self.named_mint,
            bonding_curve=self.bonding_curve,
        )
        truncated_result = identify_create_payloads(
            [truncated],
            discriminator=self.discriminator,
            named_mint=self.named_mint,
            bonding_curve=self.bonding_curve,
        )
        self.assertEqual(decide_identity_terminal(trailing_result), "CREATE_BODY_NOT_SIX_FIELD")
        self.assertEqual(
            decide_identity_terminal(truncated_result), "CREATE_BODY_NOT_SIX_FIELD"
        )

    def test_no_create_payload_is_absent(self) -> None:
        result = identify_create_payloads(
            [],
            discriminator=self.discriminator,
            named_mint=self.named_mint,
            bonding_curve=self.bonding_curve,
        )
        self.assertEqual(decide_identity_terminal(result), "CREATE_BODY_ABSENT")

    def test_git_gettransaction_fixture_matches_named_mint_and_curve(self) -> None:
        self.assertTrue((ROOT / GETTX_FIXTURE_RELATIVE).is_file())
        result = classify_gettransaction_fixture_identity(ROOT)
        self.assertEqual(result["payload_len"], [195])
        self.assertEqual(
            result["terminal"],
            "CREATE_PUBKEYS_MATCH_NAMED_MINT_AND_BONDING_CURVE",
        )
        observed = result["observed"][0]
        self.assertEqual(observed["name"], "Cope")
        self.assertEqual(observed["symbol"], "Cope")
        self.assertEqual(
            observed["uri"],
            "https://cf-ipfs.com/ipfs/QmdnBymuNUqWtCfvxqtitCXntkxKndcbeZnnLN279ywCtJ",
        )
        self.assertEqual(observed["mint"], EXPECTED_NAMED_MINT)
        self.assertEqual(observed["bonding_curve"], EXPECTED_BONDING_CURVE)
        self.assertEqual(observed["user"], "BFx6LQHkgcvdQ3ySxZBDBigii4fDQvn7yw5pfWRdVAgm")
        self.assertIsNone(result.get("create_at"))
        self.assertNotIn("blockTime", result)

    def test_retained_a4_absent_or_same_identity(self) -> None:
        result = scan_retained_a4_create_pubkey_identity(ROOT)
        self.assertEqual(
            result["gettransaction_fixture"]["terminal"],
            "CREATE_PUBKEYS_MATCH_NAMED_MINT_AND_BONDING_CURVE",
        )
        if result["pages_status"] == "RETAINED_A4_PAGES_NOT_IN_CHECKOUT":
            self.assertIsNone(result["scan"])
            return
        self.assertEqual(result["pages_status"], "SCANNED")
        scan = result["scan"]
        assert scan is not None
        self.assertEqual(scan["payload_len"], [195])
        self.assertEqual(
            scan["terminal"],
            "CREATE_PUBKEYS_MATCH_NAMED_MINT_AND_BONDING_CURVE",
        )
        observed = scan["observed"][0]
        self.assertEqual(observed["mint"], EXPECTED_NAMED_MINT)
        self.assertEqual(observed["bonding_curve"], EXPECTED_BONDING_CURVE)

    def test_acceptance_receipt_is_json_object(self) -> None:
        path = ROOT / (
            "docs/evidence/rc002_h11_create_six_field_pubkey_identity/"
            "a1_create_six_field_pubkey_identity_acceptance_v1.json"
        )
        receipt = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(receipt["atom_id"], ATOM_ID)
        self.assertEqual(
            receipt["gettransaction_fixture"]["terminal"],
            "CREATE_PUBKEYS_MATCH_NAMED_MINT_AND_BONDING_CURVE",
        )
        self.assertEqual(
            receipt["gettransaction_fixture"]["observed"]["mint"],
            EXPECTED_NAMED_MINT,
        )
        self.assertEqual(
            receipt["gettransaction_fixture"]["observed"]["bonding_curve"],
            EXPECTED_BONDING_CURVE,
        )
        self.assertIsNone(receipt.get("create_at"))
        self.assertIn("NO_CREATE_AT_FROM_BLOCKTIME", receipt["non_claims"])
        self.assertIn("NO_PINNED_DECODER_MUTATION", receipt["non_claims"])
        self.assertFalse(receipt["live_PIT_claim"])
        self.assertFalse(receipt["pinned_decoder_mutated"])


if __name__ == "__main__":
    unittest.main()
