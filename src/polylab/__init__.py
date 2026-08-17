"""Python client for the public PolyLab API — Polymarket market and smart money data."""

from .client import PolyLabClient, PolyLabError, PolyLabHTTPError
from .models import Holder, Market, Status, Tag

__version__ = "0.1.0"

__all__ = [
    "PolyLabClient",
    "PolyLabError",
    "PolyLabHTTPError",
    "Market",
    "Holder",
    "Tag",
    "Status",
    "__version__",
]
