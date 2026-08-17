"""HTTP client for the public PolyLab API.

Standard library only — no dependencies to install and nothing to keep in sync
with your own requirements.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Iterable, Sequence

from .models import Holder, Market, Status, Tag

__all__ = ["PolyLabClient", "PolyLabError", "PolyLabHTTPError"]

DEFAULT_BASE_URL = "https://api.polylab.app"
DEFAULT_TIMEOUT = 30.0
DEFAULT_RETRIES = 3
USER_AGENT = "polylab-client/0.1.0 (+https://www.polylab.app)"

# Sort keys the backend accepts. An unknown key silently falls back to
# volume_usd server-side, which is easy to miss, so reject it here instead.
SORT_KEYS = frozenset(
    {
        "volume_usd",
        "liquidity_usd",
        "end_date",
        "price",
        "spread",
        "apr",
        "question",
        "yes_profitable_count",
        "yes_losing_count",
        "yes_total",
        "no_profitable_count",
        "no_losing_count",
        "no_total",
    }
)


class PolyLabError(Exception):
    """Base error for every failure raised by this client."""


class PolyLabHTTPError(PolyLabError):
    """The API answered with a non-2xx status."""

    def __init__(self, status: int, url: str, body: str) -> None:
        super().__init__(f"HTTP {status} for {url}: {body[:200]}")
        self.status = status
        self.url = url
        self.body = body


class PolyLabClient:
    """Read-only client for ``https://api.polylab.app``.

    The API is public and needs no key or account.

    >>> client = PolyLabClient()
    >>> markets = client.markets(min_price=0.9, max_spread=0.02, limit=5)
    """

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        *,
        timeout: float = DEFAULT_TIMEOUT,
        retries: int = DEFAULT_RETRIES,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.retries = max(1, retries)

    # ------------------------------------------------------------------
    # Endpoints
    # ------------------------------------------------------------------

    def markets(
        self,
        *,
        search: str | None = None,
        included_tags: Sequence[str] | None = None,
        excluded_tags: Sequence[str] | None = None,
        min_price: float | None = None,
        max_price: float | None = None,
        max_spread: float | None = None,
        min_apr: float | None = None,
        min_volume: float | None = None,
        min_liquidity: float | None = None,
        min_hours_to_expire: float | None = None,
        max_hours_to_expire: float | None = None,
        include_expired: bool | None = None,
        min_profitable: int | None = None,
        min_losing_opposite: int | None = None,
        sort_by: str | None = None,
        sort_dir: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[Market]:
        """Screen Polymarket outcomes.

        Prices and spreads are fractions of a dollar (``0.92``, not ``92``),
        and ``min_apr`` is a fraction too (``1.5`` means 150%). Rows with a
        ``null`` APR can never satisfy ``min_apr``.

        Included tags are OR logic — a market passes on any one of them.
        Excluded tags are hard blocks.
        """
        if sort_by is not None and sort_by not in SORT_KEYS:
            raise ValueError(
                f"unsupported sort_by {sort_by!r}; expected one of {sorted(SORT_KEYS)}"
            )
        if sort_dir is not None and sort_dir not in ("asc", "desc"):
            raise ValueError(f"sort_dir must be 'asc' or 'desc', got {sort_dir!r}")

        params = {
            "search": search,
            "included_tags": _join(included_tags),
            "excluded_tags": _join(excluded_tags),
            "min_price": min_price,
            "max_price": max_price,
            "max_spread": max_spread,
            "min_apr": min_apr,
            "min_volume": min_volume,
            "min_liquidity": min_liquidity,
            "min_hours_to_expire": min_hours_to_expire,
            "max_hours_to_expire": max_hours_to_expire,
            "include_expired": include_expired,
            "min_profitable": min_profitable,
            "min_losing_opposite": min_losing_opposite,
            "sort_by": sort_by,
            "sort_dir": sort_dir,
            "limit": limit,
            "offset": offset,
        }
        payload = self._get("/api/markets", params)
        return [Market.from_dict(row) for row in _as_list(payload)]

    def holders(self, market_id: str | int) -> list[Holder]:
        """Sampled wallets holding either side of a market, with lifetime PnL.

        This is a sample of the largest holders, not every participant.
        """
        payload = self._get(f"/api/markets/{market_id}/holders", {})
        return [Holder.from_dict(row) for row in _as_list(payload)]

    def tags(self) -> list[Tag]:
        """Every category label in the current snapshot, with row counts."""
        payload = self._get("/api/tags", {})
        return [Tag.from_dict(row) for row in _as_list(payload)]

    def status(self) -> Status:
        """When the market snapshot and smart-money layer last refreshed."""
        payload = self._get("/api/status", {})
        if not isinstance(payload, dict):
            raise PolyLabError(f"expected an object from /api/status, got {type(payload).__name__}")
        return Status.from_dict(payload)

    def iter_markets(self, *, page_size: int = 100, **filters: Any) -> Iterable[Market]:
        """Page through every match, yielding rows as they arrive.

        Stops on the first short page. Do not pass ``limit`` or ``offset`` —
        this method owns them.
        """
        for key in ("limit", "offset"):
            if key in filters:
                raise ValueError(f"iter_markets manages {key} itself")
        offset = 0
        while True:
            page = self.markets(limit=page_size, offset=offset, **filters)
            yield from page
            if len(page) < page_size:
                return
            offset += page_size

    # ------------------------------------------------------------------
    # Transport
    # ------------------------------------------------------------------

    def _get(self, path: str, params: dict[str, Any]) -> Any:
        query = urllib.parse.urlencode(
            {k: _encode(v) for k, v in params.items() if v is not None}
        )
        url = f"{self.base_url}{path}" + (f"?{query}" if query else "")
        request = urllib.request.Request(
            url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"}
        )

        last_error: Exception | None = None
        for attempt in range(self.retries):
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    return json.loads(response.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                body = exc.read().decode("utf-8", errors="replace")
                # 4xx means the request itself is wrong; retrying cannot help.
                if exc.code < 500:
                    raise PolyLabHTTPError(exc.code, url, body) from exc
                last_error = PolyLabHTTPError(exc.code, url, body)
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
                last_error = PolyLabError(f"request to {url} failed: {exc}")

            if attempt < self.retries - 1:
                time.sleep(2**attempt)

        raise last_error if last_error else PolyLabError(f"request to {url} failed")


def _join(values: Sequence[str] | None) -> str | None:
    return ",".join(values) if values else None


def _encode(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _as_list(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, list):
        raise PolyLabError(f"expected a JSON array, got {type(payload).__name__}")
    return [row for row in payload if isinstance(row, dict)]
