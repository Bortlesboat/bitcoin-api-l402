"""Endpoint pricing for L402 Lightning payments."""

import re
from dataclasses import dataclass


@dataclass
class EndpointPrice:
    pattern: str
    price_sats: int
    description: str


# Pricing tiers (sats per request)
ENDPOINT_PRICES: list[EndpointPrice] = [
    # Free (0 sats)
    EndpointPrice(r"/api/v1/health$", 0, "Health check"),
    EndpointPrice(r"/api/v1/status$", 0, "Node status"),

    # Cheap (10-50 sats)
    EndpointPrice(r"/api/v1/fees$", 10, "Fee estimates"),
    EndpointPrice(r"/api/v1/fees/recommended$", 10, "Fee recommendation"),
    EndpointPrice(r"/api/v1/fees/\d+$", 10, "Custom fee target"),
    EndpointPrice(r"/api/v1/mempool/info$", 10, "Mempool quick stats"),
    EndpointPrice(r"/api/v1/blocks/latest$", 20, "Latest block"),
    EndpointPrice(r"/api/v1/blocks/tip/(height|hash)$", 10, "Chain tip"),
    EndpointPrice(r"/api/v1/network$", 20, "Network info"),
    EndpointPrice(r"/api/v1/network/difficulty$", 10, "Difficulty info"),
    EndpointPrice(r"/api/v1/network/forks$", 20, "Chain forks"),

    # Medium (100-200 sats)
    EndpointPrice(r"/api/v1/blocks/[^/]+$", 100, "Block by height or hash"),
    EndpointPrice(r"/api/v1/blocks/\d+/stats$", 100, "Block statistics"),
    EndpointPrice(r"/api/v1/blocks/[^/]+/txids$", 100, "Block transaction IDs"),
    EndpointPrice(r"/api/v1/blocks/[^/]+/txs$", 200, "Block transactions"),
    EndpointPrice(r"/api/v1/tx/[a-f0-9]+$", 100, "Transaction analysis"),
    EndpointPrice(r"/api/v1/tx/[a-f0-9]+/raw$", 50, "Raw transaction"),
    EndpointPrice(r"/api/v1/tx/[a-f0-9]+/status$", 50, "Transaction status"),
    EndpointPrice(r"/api/v1/utxo/", 100, "UTXO lookup"),
    EndpointPrice(r"/api/v1/mining$", 100, "Mining info"),
    EndpointPrice(r"/api/v1/mempool$", 100, "Mempool analysis"),
    EndpointPrice(r"/api/v1/mempool/tx/", 100, "Mempool tx lookup"),
    EndpointPrice(r"/api/v1/mempool/txids$", 100, "Mempool tx IDs"),
    EndpointPrice(r"/api/v1/mempool/recent$", 100, "Recent mempool txs"),

    # Expensive (500-1000 sats)
    EndpointPrice(r"/api/v1/mining/nextblock$", 500, "Next block prediction"),
    EndpointPrice(r"/api/v1/broadcast$", 1000, "Broadcast transaction"),
    EndpointPrice(r"/api/v1/decode$", 500, "Decode transaction"),
]

# Compile patterns once
_COMPILED_PRICES = [(re.compile(ep.pattern), ep) for ep in ENDPOINT_PRICES]


def get_endpoint_price(path: str) -> int:
    """Get the price in sats for a given endpoint path. Returns 0 for unmatched paths."""
    for pattern, ep in _COMPILED_PRICES:
        if pattern.search(path):
            return ep.price_sats
    return 0  # Default: free for unknown endpoints


def is_free_endpoint(path: str) -> bool:
    """Check if an endpoint is free (0 sats)."""
    return get_endpoint_price(path) == 0
