"""Tests for L402 Lightning payment protocol."""

import hashlib
import json
import os

import pytest

from bitcoin_api_l402.l402 import (
    mint_macaroon,
    serialize_macaroon,
    deserialize_macaroon,
    verify_macaroon,
    verify_preimage,
    parse_l402_header,
    create_challenge,
    generate_root_key,
)
from bitcoin_api_l402.lightning import MockLightningClient, Invoice
from bitcoin_api_l402.pricing import get_endpoint_price, is_free_endpoint


# --- Unit tests: l402.py ---


class TestMacaroons:
    def test_mint_and_verify(self):
        root_key = generate_root_key()
        mac = mint_macaroon(root_key, "abc123", "/api/v1/fees", 10)
        valid, reason = verify_macaroon(root_key, mac)
        assert valid is True
        assert reason == "ok"

    def test_wrong_root_key(self):
        key1 = generate_root_key()
        key2 = generate_root_key()
        mac = mint_macaroon(key1, "abc123", "/api/v1/fees", 10)
        valid, reason = verify_macaroon(key2, mac)
        assert valid is False
        assert reason == "invalid signature"

    def test_expired_macaroon(self):
        root_key = generate_root_key()
        mac = mint_macaroon(root_key, "abc123", "/api/v1/fees", 10, expiry_seconds=-10)
        valid, reason = verify_macaroon(root_key, mac)
        assert valid is False
        assert reason == "macaroon expired"

    def test_serialize_deserialize(self):
        root_key = generate_root_key()
        mac = mint_macaroon(root_key, "abc123", "/api/v1/fees", 10)
        b64 = serialize_macaroon(mac)
        mac2 = deserialize_macaroon(b64)
        assert mac.identifier == mac2.identifier
        assert mac.signature == mac2.signature

    def test_identifier_contains_expected_fields(self):
        root_key = generate_root_key()
        mac = mint_macaroon(root_key, "hash123", "/api/v1/blocks/latest", 20)
        ident = json.loads(mac.identifier)
        assert ident["payment_hash"] == "hash123"
        assert ident["endpoint"] == "/api/v1/blocks/latest"
        assert ident["amount_sats"] == 20
        assert ident["version"] == 1
        assert "expires" in ident


class TestPreimageVerification:
    def test_valid_preimage(self):
        preimage = os.urandom(32)
        preimage_hex = preimage.hex()
        payment_hash = hashlib.sha256(preimage).hexdigest()
        assert verify_preimage(payment_hash, preimage_hex) is True

    def test_invalid_preimage(self):
        assert verify_preimage("abc123", "def456") is False

    def test_wrong_preimage(self):
        preimage = os.urandom(32)
        wrong_preimage = os.urandom(32)
        payment_hash = hashlib.sha256(preimage).hexdigest()
        assert verify_preimage(payment_hash, wrong_preimage.hex()) is False

    def test_malformed_preimage(self):
        assert verify_preimage("abc", "not-hex") is False


class TestL402Header:
    def test_parse_valid_header(self):
        root_key = generate_root_key()
        mac = mint_macaroon(root_key, "hash123", "/test", 10)
        mac_b64 = serialize_macaroon(mac)
        preimage_hex = "aabbccdd" * 8
        header = f"L402 {mac_b64}:{preimage_hex}"
        token = parse_l402_header(header)
        assert token is not None
        assert token.preimage == preimage_hex

    def test_parse_non_l402_header(self):
        assert parse_l402_header("Bearer abc123") is None

    def test_parse_missing_colon(self):
        assert parse_l402_header("L402 justmacaroon") is None

    def test_create_challenge(self):
        challenge = create_challenge("mac_b64_value", "lnbc100n1...")
        assert 'macaroon="mac_b64_value"' in challenge
        assert 'invoice="lnbc100n1..."' in challenge
        assert challenge.startswith("L402 ")


# --- Unit tests: lightning.py ---


class TestMockLightningClient:
    def test_create_invoice(self):
        client = MockLightningClient()
        invoice = client.create_invoice(100, "test payment")
        assert invoice.amount_sats == 100
        assert invoice.payment_hash
        assert invoice.payment_request.startswith("lnbc")

    def test_verify_unpaid(self):
        client = MockLightningClient()
        invoice = client.create_invoice(100, "test")
        assert client.verify_payment(invoice.payment_hash) is False

    def test_verify_after_payment(self):
        client = MockLightningClient()
        invoice = client.create_invoice(100, "test")
        client.simulate_payment(invoice.payment_hash)
        assert client.verify_payment(invoice.payment_hash) is True

    def test_get_balance(self):
        client = MockLightningClient()
        assert client.get_balance() == 100000

    def test_deterministic_hash(self):
        client = MockLightningClient()
        inv1 = client.create_invoice(100, "same memo")
        inv2 = client.create_invoice(200, "same memo")
        assert inv1.payment_hash == inv2.payment_hash  # Same memo = same hash


# --- Unit tests: pricing.py ---


class TestPricing:
    def test_free_endpoints(self):
        assert get_endpoint_price("/api/v1/health") == 0
        assert get_endpoint_price("/api/v1/status") == 0

    def test_cheap_endpoints(self):
        assert get_endpoint_price("/api/v1/fees") == 10
        assert get_endpoint_price("/api/v1/fees/recommended") == 10
        assert get_endpoint_price("/api/v1/mempool/info") == 10

    def test_medium_endpoints(self):
        price = get_endpoint_price("/api/v1/tx/abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890")
        assert price == 100

    def test_expensive_endpoints(self):
        assert get_endpoint_price("/api/v1/mining/nextblock") == 500
        assert get_endpoint_price("/api/v1/broadcast") == 1000

    def test_unknown_endpoint_is_free(self):
        assert get_endpoint_price("/api/v1/unknown") == 0

    def test_is_free_endpoint(self):
        assert is_free_endpoint("/api/v1/health") is True
        assert is_free_endpoint("/api/v1/fees") is False

    def test_block_pricing(self):
        assert get_endpoint_price("/api/v1/blocks/latest") == 20
        assert get_endpoint_price("/api/v1/blocks/880000") == 100
