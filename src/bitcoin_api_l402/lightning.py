"""Lightning Network client abstraction for L402 payments."""

import hashlib
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass

import httpx

log = logging.getLogger(__name__)


@dataclass
class Invoice:
    payment_hash: str
    payment_request: str
    amount_sats: int
    expiry: int


class LightningClient(ABC):
    @abstractmethod
    def create_invoice(self, amount_sats: int, memo: str, expiry: int = 3600) -> Invoice:
        ...

    @abstractmethod
    def verify_payment(self, payment_hash: str) -> bool:
        ...

    @abstractmethod
    def get_balance(self) -> int:
        ...


class AlbyHubClient(LightningClient):
    def __init__(self, base_url: str, token: str):
        self.base_url = base_url.rstrip("/")
        self.client = httpx.Client(
            base_url=self.base_url,
            headers={"Authorization": f"Bearer {token}"},
            timeout=10.0,
        )

    def create_invoice(self, amount_sats: int, memo: str, expiry: int = 3600) -> Invoice:
        resp = self.client.post("/api/v1/invoices", json={
            "amount": amount_sats * 1000,  # Alby uses millisats
            "description": memo,
            "expiry": expiry,
        })
        resp.raise_for_status()
        data = resp.json()
        return Invoice(
            payment_hash=data["payment_hash"],
            payment_request=data["payment_request"],
            amount_sats=amount_sats,
            expiry=expiry,
        )

    def verify_payment(self, payment_hash: str) -> bool:
        resp = self.client.get(f"/api/v1/invoices/{payment_hash}")
        if resp.status_code == 404:
            return False
        resp.raise_for_status()
        data = resp.json()
        return data.get("settled", False) or data.get("state") == "settled"

    def get_balance(self) -> int:
        resp = self.client.get("/api/v1/balance")
        resp.raise_for_status()
        data = resp.json()
        return data.get("balance", 0) // 1000  # Convert millisats to sats


class MockLightningClient(LightningClient):
    def __init__(self):
        self.invoices: dict[str, Invoice] = {}
        self.paid: set[str] = set()

    def create_invoice(self, amount_sats: int, memo: str, expiry: int = 3600) -> Invoice:
        payment_hash = hashlib.sha256(memo.encode()).hexdigest()
        invoice = Invoice(
            payment_hash=payment_hash,
            payment_request=f"lnbc{amount_sats}n1mock{payment_hash[:20]}",
            amount_sats=amount_sats,
            expiry=expiry,
        )
        self.invoices[payment_hash] = invoice
        return invoice

    def verify_payment(self, payment_hash: str) -> bool:
        return payment_hash in self.paid

    def get_balance(self) -> int:
        return 100000

    def simulate_payment(self, payment_hash: str) -> None:
        self.paid.add(payment_hash)
