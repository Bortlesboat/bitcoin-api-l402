"""L402 Lightning payment protocol — macaroon minting, verification, and challenges."""

import base64
import hashlib
import hmac
import json
import logging
import os
import time
from dataclasses import dataclass

log = logging.getLogger(__name__)


@dataclass
class L402Token:
    """Parsed L402 authorization token."""
    macaroon_bytes: bytes
    preimage: str  # hex


@dataclass
class Macaroon:
    """Simple macaroon for L402 — identifier contains payment_hash, signed with root key."""
    identifier: str  # JSON: {"payment_hash": "...", "endpoint": "...", "amount": N, "expires": T}
    signature: str  # HMAC-SHA256 hex


def mint_macaroon(
    root_key: bytes,
    payment_hash: str,
    endpoint: str,
    amount_sats: int,
    expiry_seconds: int = 3600,
) -> Macaroon:
    """Create a new macaroon tied to a Lightning payment."""
    identifier = json.dumps({
        "payment_hash": payment_hash,
        "endpoint": endpoint,
        "amount_sats": amount_sats,
        "expires": int(time.time()) + expiry_seconds,
        "version": 1,
    }, separators=(",", ":"))

    signature = hmac.new(root_key, identifier.encode(), hashlib.sha256).hexdigest()

    return Macaroon(identifier=identifier, signature=signature)


def serialize_macaroon(mac: Macaroon) -> str:
    """Serialize macaroon to base64 string for HTTP headers."""
    payload = json.dumps({
        "identifier": mac.identifier,
        "signature": mac.signature,
    }, separators=(",", ":"))
    return base64.urlsafe_b64encode(payload.encode()).decode()


def deserialize_macaroon(b64_str: str) -> Macaroon:
    """Deserialize macaroon from base64 string."""
    payload = json.loads(base64.urlsafe_b64decode(b64_str))
    return Macaroon(
        identifier=payload["identifier"],
        signature=payload["signature"],
    )


def verify_macaroon(root_key: bytes, mac: Macaroon) -> tuple[bool, str]:
    """Verify macaroon signature and expiry. Returns (valid, reason)."""
    expected = hmac.new(root_key, mac.identifier.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, mac.signature):
        return False, "invalid signature"

    try:
        ident = json.loads(mac.identifier)
    except json.JSONDecodeError:
        return False, "malformed identifier"

    if time.time() > ident.get("expires", 0):
        return False, "macaroon expired"

    return True, "ok"


def verify_preimage(payment_hash: str, preimage_hex: str) -> bool:
    """Verify that SHA256(preimage) == payment_hash."""
    try:
        preimage_bytes = bytes.fromhex(preimage_hex)
        computed_hash = hashlib.sha256(preimage_bytes).hexdigest()
        return hmac.compare_digest(computed_hash, payment_hash)
    except (ValueError, TypeError):
        return False


def parse_l402_header(auth_header: str) -> L402Token | None:
    """Parse Authorization: L402 <macaroon>:<preimage> header."""
    if not auth_header.startswith("L402 "):
        return None
    token_part = auth_header[5:].strip()
    if ":" not in token_part:
        return None
    mac_b64, preimage_hex = token_part.split(":", 1)
    try:
        mac_bytes = base64.urlsafe_b64decode(mac_b64)
    except Exception:
        return None
    return L402Token(macaroon_bytes=mac_bytes, preimage=preimage_hex)


def create_challenge(macaroon_b64: str, invoice: str) -> str:
    """Create WWW-Authenticate header value for 402 response."""
    return f'L402 macaroon="{macaroon_b64}", invoice="{invoice}"'


def generate_root_key() -> bytes:
    """Generate a random 32-byte root key for macaroon signing."""
    return os.urandom(32)
