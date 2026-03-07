"""Test fixtures for bitcoin-api-l402."""

import pytest


@pytest.fixture
def root_key():
    from bitcoin_api_l402.l402 import generate_root_key
    return generate_root_key()
