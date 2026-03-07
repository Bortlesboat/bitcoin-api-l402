"""L402 Lightning payment extension for Satoshi API."""

__version__ = "0.1.0"

from .middleware import enable_l402

__all__ = ["enable_l402"]
