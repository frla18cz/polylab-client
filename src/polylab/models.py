"""Typed records returned by the PolyLab API.

Every dataclass is built with :meth:`from_dict`, which keeps only the fields it
knows about. The API adds columns over time; unknown keys are preserved on
``raw`` so nothing is lost and a new server field never breaks the client.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Mapping


def _parse_ts(value: Any) -> datetime | None:
    """Parse an API timestamp, tolerating the trailing ``Z`` form."""
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


@dataclass(frozen=True)
class Market:
    """One outcome row of a Polymarket market.

    PolyLab stores one row per outcome, not per market, so a binary market
    appears twice: once as ``Yes`` and once as ``No``. ``price``, ``spread``
    and ``apr`` all describe the single outcome named by ``outcome_name``.
    """

    market_id: str
    condition_id: str
    question: str
    outcome_name: str
    price: float | None
    apr: float | None
    spread: float | None
    volume_usd: float | None
    liquidity_usd: float | None
    end_date: datetime | None
    category: str | None
    url: str | None
    event_title: str | None
    yes_profitable_count: int | None
    no_profitable_count: int | None
    raw: Mapping[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Market":
        return cls(
            market_id=str(data.get("market_id", "")),
            condition_id=str(data.get("condition_id", "")),
            question=data.get("question") or "",
            outcome_name=data.get("outcome_name") or "",
            price=data.get("price"),
            apr=data.get("apr"),
            spread=data.get("spread"),
            volume_usd=data.get("volume_usd"),
            liquidity_usd=data.get("liquidity_usd"),
            end_date=_parse_ts(data.get("end_date")),
            category=data.get("category"),
            url=data.get("url"),
            event_title=data.get("event_title"),
            yes_profitable_count=data.get("yes_profitable_count"),
            no_profitable_count=data.get("no_profitable_count"),
            raw=dict(data),
        )

    @property
    def apr_percent(self) -> float | None:
        """APR as a percentage. ``None`` when the API could not compute it."""
        return None if self.apr is None else self.apr * 100


@dataclass(frozen=True)
class Holder:
    """A sampled wallet holding one side of a market.

    ``total_pnl`` is the wallet's lifetime profit across all of Polymarket, not
    its profit on this position, so it reads as a track record rather than a
    result.
    """

    wallet_address: str
    position_size: float | None
    outcome_index: int | None
    total_pnl: float | None
    alias: str | None
    wallet_tag: str | None
    raw: Mapping[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Holder":
        return cls(
            wallet_address=data.get("wallet_address") or "",
            position_size=data.get("position_size"),
            outcome_index=data.get("outcome_index"),
            total_pnl=data.get("total_pnl"),
            alias=data.get("alias"),
            wallet_tag=data.get("wallet_tag"),
            raw=dict(data),
        )

    @property
    def is_profitable(self) -> bool:
        return (self.total_pnl or 0) > 0


@dataclass(frozen=True)
class Tag:
    """A category label and how many outcome rows currently carry it."""

    tag_label: str
    count: int

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Tag":
        return cls(tag_label=data.get("tag_label") or "", count=data.get("count") or 0)


@dataclass(frozen=True)
class Status:
    """Freshness of the two refresh cycles behind the data.

    Market snapshots and smart-money enrichment run on separate schedules
    (hourly and 6-hourly), so these two timestamps routinely differ.
    """

    last_updated: datetime | None
    smart_money_last_updated: datetime | None

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Status":
        return cls(
            last_updated=_parse_ts(data.get("last_updated")),
            smart_money_last_updated=_parse_ts(data.get("smart_money_last_updated")),
        )
