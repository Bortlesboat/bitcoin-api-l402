"""FastAPI middleware for L402 Lightning payments."""

import json
import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .l402 import (
    deserialize_macaroon,
    verify_macaroon,
    verify_preimage,
    mint_macaroon,
    serialize_macaroon,
    create_challenge,
    generate_root_key,
)
from .lightning import AlbyHubClient, MockLightningClient, LightningClient
from .pricing import get_endpoint_price

log = logging.getLogger(__name__)


def _extract_l402_token(request: Request) -> tuple[str | None, str | None]:
    """Extract L402 token from Authorization header."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("L402 "):
        return None, None
    token_part = auth[5:].strip()
    if ":" not in token_part:
        return None, None
    mac_b64, preimage_hex = token_part.split(":", 1)
    return mac_b64, preimage_hex


def enable_l402(
    app: FastAPI,
    *,
    root_key: str = "",
    lightning_backend: str = "mock",
    alby_url: str = "",
    alby_token: str = "",
    default_expiry: int = 3600,
) -> LightningClient:
    """Enable L402 Lightning payments on a FastAPI app.

    Args:
        app: FastAPI application instance
        root_key: Hex-encoded 32-byte key for macaroon signing (auto-generated if empty)
        lightning_backend: "alby" or "mock"
        alby_url: Alby Hub URL (required if backend is "alby")
        alby_token: Alby Hub auth token (required if backend is "alby")
        default_expiry: Invoice expiry in seconds

    Returns:
        The Lightning client instance (useful for testing with MockLightningClient)
    """
    # Root key
    if root_key:
        _root_key = bytes.fromhex(root_key)
    else:
        _root_key = generate_root_key()
        log.warning("L402: No root key configured, generated ephemeral key.")

    # Lightning backend
    if lightning_backend == "alby":
        client = AlbyHubClient(alby_url, alby_token)
        log.info("L402: Alby Hub client initialized at %s", alby_url)
    else:
        client = MockLightningClient()
        log.info("L402: Mock Lightning client initialized (for testing)")

    @app.middleware("http")
    async def l402_middleware(request: Request, call_next):
        # Only intercept anonymous requests (no API key)
        api_key = request.headers.get("X-API-Key") or request.query_params.get("api_key")
        if api_key:
            return await call_next(request)

        # Check for L402 token
        mac_b64, preimage_hex = _extract_l402_token(request)
        if mac_b64 and preimage_hex:
            try:
                mac = deserialize_macaroon(mac_b64)
                valid, reason = verify_macaroon(_root_key, mac)
                if valid:
                    ident = json.loads(mac.identifier)
                    payment_hash = ident["payment_hash"]
                    if verify_preimage(payment_hash, preimage_hex):
                        # Valid L402 — set tier and continue
                        request.state.l402_tier = "lightning"
                        request.state.l402_key_hash = f"l402:{payment_hash[:16]}"
                        log.info("L402: Valid payment for %s", request.url.path)
                        return await call_next(request)
                    else:
                        log.warning("L402: Invalid preimage for hash=%s...", payment_hash[:16])
                else:
                    log.warning("L402: Macaroon verification failed: %s", reason)
            except Exception as e:
                log.warning("L402: Token parse error: %s", e)

        # Check if endpoint is priced
        price = get_endpoint_price(request.url.path)
        if price > 0:
            try:
                invoice = client.create_invoice(
                    amount_sats=price,
                    memo=f"Satoshi API: {request.url.path}",
                    expiry=default_expiry,
                )
                mac = mint_macaroon(
                    _root_key,
                    invoice.payment_hash,
                    request.url.path,
                    price,
                    default_expiry,
                )
                mac_b64_new = serialize_macaroon(mac)
                challenge = create_challenge(mac_b64_new, invoice.payment_request)

                request_id = getattr(request.state, "request_id", "")
                resp = JSONResponse(
                    status_code=402,
                    content={
                        "error": {
                            "status": 402,
                            "title": "Payment Required",
                            "detail": f"This endpoint costs {price} sats. Pay the Lightning invoice to access.",
                            "request_id": request_id,
                        }
                    },
                )
                resp.headers["WWW-Authenticate"] = challenge
                if request_id:
                    resp.headers["X-Request-ID"] = request_id
                resp.headers["X-Price-Sats"] = str(price)
                return resp
            except Exception as e:
                log.error("L402: Failed to create invoice: %s", e)
                # Fall through to normal access on failure

        return await call_next(request)

    return client
