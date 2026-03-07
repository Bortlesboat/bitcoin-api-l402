# bitcoin-api-l402

L402 Lightning payment extension for [Satoshi API](https://github.com/Bortlesboat/bitcoin-api).

Adds HTTP 402 payment challenges with Lightning Network invoices and macaroon-based authentication.

## Installation

```bash
pip install bitcoin-api-l402
```

## Quick Start

```python
from fastapi import FastAPI
from bitcoin_api_l402 import enable_l402

app = FastAPI()

# Enable L402 with mock Lightning backend (for testing)
client = enable_l402(app, lightning_backend="mock")

# Or with Alby Hub
client = enable_l402(
    app,
    root_key="your-hex-encoded-32-byte-key",
    lightning_backend="alby",
    alby_url="http://localhost:8080",
    alby_token="your-alby-token",
)
```

## How It Works

1. Anonymous request hits a priced endpoint
2. API returns `402 Payment Required` with a Lightning invoice in `WWW-Authenticate` header
3. Client pays the invoice, gets a preimage
4. Client resends request with `Authorization: L402 <macaroon>:<preimage>`
5. API verifies payment and serves the response

## Components

- **l402.py** - Macaroon minting, verification, and serialization
- **lightning.py** - Lightning client abstraction (Alby Hub + mock for testing)
- **pricing.py** - Endpoint-to-sats pricing map
- **middleware.py** - FastAPI middleware that handles the L402 flow

## License

MIT
