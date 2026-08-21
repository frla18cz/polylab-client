<div align="center">

<img src="https://raw.githubusercontent.com/frla18cz/polylab-client/main/assets/polylab-mark.svg" alt="PolyLab" width="72" height="72">

# polylab-client

### Polymarket data in Python. One import, zero dependencies.

Live prices, spreads, liquidity, annualized yield, and wallet-level smart money
positioning — from the [PolyLab](https://www.polylab.app) analytics engine.
No API key. No account. Nothing to install but this.

[![PyPI](https://img.shields.io/pypi/v/polylab-client?color=2e75ff&label=pypi)](https://pypi.org/project/polylab-client/)
[![tests](https://github.com/frla18cz/polylab-client/actions/workflows/tests.yml/badge.svg)](https://github.com/frla18cz/polylab-client/actions/workflows/tests.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-2e75ff)](https://www.python.org/downloads/)
[![dependencies: none](https://img.shields.io/badge/dependencies-none-2e75ff)](https://github.com/frla18cz/polylab-client/blob/main/pyproject.toml)
[![License: MIT](https://img.shields.io/badge/license-MIT-2e75ff)](https://github.com/frla18cz/polylab-client/blob/main/LICENSE)

[Website](https://www.polylab.app) ·
[Live scanner](https://www.polylab.app/app) ·
[Docs](https://www.polylab.app/docs) ·
[API contract](https://www.polylab.app/docs/reference/public-api-contract)

</div>

---

```bash
pip install polylab-client
```

```python
from polylab import PolyLabClient

client = PolyLabClient()

for m in client.markets(min_price=0.15, max_price=0.85, max_spread=0.02,
                        min_volume=500_000, sort_by="volume_usd", sort_dir="desc"):
    print(f"{m.price:.2f} {m.outcome_name:<4} ${m.volume_usd/1e6:.1f}M  {m.question}")
```

```text
0.17 Yes  $59.1M  Will the U.S. invade Iran before 2027?
0.83 No   $59.1M  Will the U.S. invade Iran before 2027?
0.15 Yes  $26.8M  Will Gavin Newsom win the 2028 Democratic presidential nomination?
0.85 No   $26.8M  Will Gavin Newsom win the 2028 Democratic presidential nomination?
0.20 Yes  $15.6M  Will JD Vance win the 2028 US Presidential Election?
```

*Real output, trimmed. Prices move — yours will differ.* Note that each market
appears twice, once per outcome. That is the shape of every result set here.

## What it gives you

|  | |
| --- | --- |
| **Screen the whole board** | Filter ~350,000 live outcomes by price, spread, liquidity, volume, time to expiry, and category tags — server-side, in one call. |
| **Find yield** | Annualized hold-to-maturity return precomputed on every row, so "what pays more than 15% and isn't expiring tomorrow" is a single query. |
| **Follow the sharps** | Which side of a market the historically profitable wallets are sitting on, and which side the losing ones took. |
| **Stay unblocked** | Unknown server fields land on `.raw`, so a new column is reachable the day it ships — no client release needed. |

Everything below answers one question, with code you can paste.

---

## How to get Polymarket prices in Python

Every row is one **outcome**, not one market — a binary market appears twice,
once as `Yes` and once as `No`. Prices are fractions of a dollar between 0 and
1, and settle at exactly 1 or 0.

```python
from polylab import PolyLabClient

client = PolyLabClient()
markets = client.markets(search="election", limit=10)

for market in markets:
    print(market.outcome_name, market.price, market.question)
```

## How to find high-APR Polymarket positions

APR annualizes the return from buying at the current price and holding to a $1
payout: `((1 / price) - 1) * (365 / days_to_resolution)`. It inflates sharply
as expiry approaches, so pair it with a floor on time remaining.

```python
# At least 50% annualized, but not expiring inside a week
markets = client.markets(
    min_apr=0.5,                 # a fraction, not a percent
    min_price=0.10,              # see the warning below
    min_hours_to_expire=24 * 7,
    min_liquidity=5_000,
    sort_by="apr",
    sort_dir="desc",
    limit=20,
)

for market in markets:
    print(f"{market.apr_percent:8.1f}%  {market.question[:60]}")
```

**Sort by APR without a `min_price` floor and the top of the list is noise.**
Because the formula divides by price, a long shot trading at $0.001 scores
roughly 99,900% before annualization even starts — sorting descending returns
those and nothing else. Real figures in the millions of percent are common at
the top. A floor around `min_price=0.10` keeps the ranking meaningful.

`apr` is `None` when it cannot be computed — expired markets, zero prices, or
non-positive durations. Those rows can never satisfy `min_apr`.

## How to screen Polymarket markets by spread and liquidity

```python
tradable = client.markets(
    min_price=0.05,
    max_price=0.95,
    max_spread=0.02,        # 2 cents
    min_liquidity=10_000,
    min_volume=50_000,
    sort_by="liquidity_usd",
    sort_dir="desc",
)
```

Filter by category with tags. Included tags are OR logic — a market passes on
any one of them. Excluded tags are hard blocks.

```python
politics = client.markets(
    included_tags=["Politics", "Elections"],
    excluded_tags=["Sports"],
    limit=25,
)

for tag in client.tags()[:10]:
    print(tag.tag_label, tag.count)
```

## How to track smart money wallets on Polymarket

Ask for markets where profitable wallets sit on one side and losing wallets sit
on the other:

```python
split = client.markets(
    min_profitable=5,          # profitable wallets on this outcome
    min_losing_opposite=5,     # losing wallets on the opposite outcome
    min_liquidity=10_000,
)
```

Then inspect the individual holders. `total_pnl` is the wallet's **lifetime**
profit across all of Polymarket, so it reads as a track record rather than a
result on this position:

```python
market = split[0]

for holder in client.holders(market.market_id)[:10]:
    name = holder.alias or holder.wallet_address[:10]
    print(f"{name:<20} {holder.position_size:>12,.0f}  pnl={holder.total_pnl:>14,.0f}")
```

Holder rows are a sample of the largest positions, not every participant.

## How to page through every matching market

`iter_markets` handles `limit`/`offset` for you and stops on the first short
page:

```python
count = 0
for market in client.iter_markets(min_volume=100_000, page_size=100):
    count += 1
print(count)
```

## How fresh is the data

```python
status = client.status()
print("markets:", status.last_updated)
print("smart money:", status.smart_money_last_updated)
```

Market snapshots refresh hourly; smart money refreshes every six hours. Those
are separate cycles, so a row routinely pairs a fresh price with older holder
data. Cross-check anything you intend to execute on against live Polymarket.

---

## Reference

### `PolyLabClient(base_url=..., timeout=30.0, retries=3)`

| Method | Returns | Description |
| --- | --- | --- |
| `markets(**filters)` | `list[Market]` | Screen outcome rows |
| `iter_markets(page_size=100, **filters)` | `Iterable[Market]` | Same, paged automatically |
| `holders(market_id)` | `list[Holder]` | Sampled wallets and lifetime PnL |
| `tags()` | `list[Tag]` | Category labels with row counts |
| `status()` | `Status` | Refresh timestamps |

### Filters accepted by `markets()`

`search`, `included_tags`, `excluded_tags`, `min_price`, `max_price`,
`max_spread`, `min_apr`, `min_volume`, `min_liquidity`, `min_hours_to_expire`,
`max_hours_to_expire`, `include_expired`, `min_profitable`,
`min_losing_opposite`, `sort_by`, `sort_dir`, `limit`, `offset`.

Prices, spreads and APR are all fractions, never percentages.

### Sort keys

`volume_usd`, `liquidity_usd`, `end_date`, `price`, `spread`, `apr`,
`question`, `yes_profitable_count`, `yes_losing_count`, `yes_total`,
`no_profitable_count`, `no_losing_count`, `no_total`.

An unsupported key raises `ValueError` rather than silently falling back.

### Errors

`PolyLabHTTPError` for non-2xx responses (carries `.status`, `.url`, `.body`),
`PolyLabError` for transport and decoding failures. 5xx responses and network
errors retry with exponential backoff; 4xx responses raise immediately.

### Unknown fields

The API gains columns over time. Each record keeps the full server response on
`.raw`, so a new field is reachable without waiting for a client release:

```python
market.raw["verdict_strength"]
```

---

## Notes

This is a thin, read-only wrapper over the same public endpoints the PolyLab
web app calls. It documents the current implementation rather than a versioned
stability promise — see the
[public API contract](https://www.polylab.app/docs/reference/public-api-contract).

Nothing here is trading advice. Prediction market positions can settle at zero.

MIT licensed.
