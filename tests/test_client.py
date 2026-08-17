"""Offline tests. Transport is stubbed so the suite never touches the network."""

import json
import unittest
from unittest import mock

from polylab import Market, PolyLabClient, PolyLabHTTPError
from polylab.client import PolyLabError


def _client_returning(payload):
    client = PolyLabClient()
    client._get = mock.Mock(return_value=payload)  # noqa: SLF001 - test seam
    return client


class TestMarkets(unittest.TestCase):
    ROW = {
        "market_id": "2063134",
        "condition_id": "0x7d0a",
        "question": "Will X happen?",
        "outcome_name": "Yes",
        "price": 0.92,
        "apr": 1.06,
        "spread": 0.004,
        "volume_usd": 1000.0,
        "liquidity_usd": 500.0,
        "end_date": "2026-06-01T00:00:00Z",
        "category": "Politics",
        "url": "https://polymarket.com/event/x",
        "event_title": "X",
        "yes_profitable_count": 12,
        "no_profitable_count": 10,
        "verdict_strength": 10.0,
    }

    def test_parses_rows(self):
        markets = _client_returning([self.ROW]).markets()
        self.assertEqual(len(markets), 1)
        self.assertIsInstance(markets[0], Market)
        self.assertEqual(markets[0].outcome_name, "Yes")
        self.assertAlmostEqual(markets[0].apr_percent, 106.0)

    def test_parses_trailing_z_timestamp(self):
        market = _client_returning([self.ROW]).markets()[0]
        self.assertIsNotNone(market.end_date)
        self.assertEqual(market.end_date.year, 2026)

    def test_keeps_unknown_fields_on_raw(self):
        market = _client_returning([self.ROW]).markets()[0]
        self.assertEqual(market.raw["verdict_strength"], 10.0)

    def test_null_apr_stays_none(self):
        row = dict(self.ROW, apr=None)
        self.assertIsNone(_client_returning([row]).markets()[0].apr_percent)

    def test_rejects_unknown_sort_key(self):
        with self.assertRaises(ValueError):
            _client_returning([]).markets(sort_by="not_a_column")

    def test_rejects_bad_sort_dir(self):
        with self.assertRaises(ValueError):
            _client_returning([]).markets(sort_dir="sideways")

    def test_rejects_non_array_payload(self):
        with self.assertRaises(PolyLabError):
            _client_returning({"detail": "nope"}).markets()


class TestQueryEncoding(unittest.TestCase):
    def _captured_url(self, **kwargs):
        client = PolyLabClient()
        with mock.patch.object(client, "_get", return_value=[]) as get:
            client.markets(**kwargs)
        return get.call_args

    def test_joins_tags_with_commas(self):
        _, params = self._captured_url(included_tags=["Politics", "Elections"])[0]
        self.assertEqual(params["included_tags"], "Politics,Elections")

    def test_omits_unset_filters(self):
        _, params = self._captured_url(min_price=0.5)[0]
        self.assertIsNone(params["max_price"])

    def test_encodes_booleans_lowercase(self):
        from polylab.client import _encode

        self.assertEqual(_encode(True), "true")
        self.assertEqual(_encode(False), "false")


class TestPagination(unittest.TestCase):
    def test_stops_on_short_page(self):
        client = PolyLabClient()
        pages = [[TestMarkets.ROW] * 2, [TestMarkets.ROW]]
        client._get = mock.Mock(side_effect=pages)  # noqa: SLF001 - test seam

        rows = list(client.iter_markets(page_size=2))

        self.assertEqual(len(rows), 3)
        self.assertEqual(client._get.call_count, 2)  # noqa: SLF001

    def test_rejects_manual_offset(self):
        with self.assertRaises(ValueError):
            list(_client_returning([]).iter_markets(offset=10))


class TestErrors(unittest.TestCase):
    def test_4xx_does_not_retry(self):
        import urllib.error

        client = PolyLabClient(retries=3)
        error = urllib.error.HTTPError(
            "https://api.polylab.app/api/markets", 404, "Not Found", {}, None
        )
        error.read = lambda: b"missing"

        with mock.patch("urllib.request.urlopen", side_effect=error) as urlopen:
            with self.assertRaises(PolyLabHTTPError) as caught:
                client.markets()

        self.assertEqual(caught.exception.status, 404)
        self.assertEqual(urlopen.call_count, 1)


class TestStatus(unittest.TestCase):
    def test_parses_timestamps(self):
        payload = {
            "last_updated": "2026-08-17T09:02:19.337336+00:00",
            "smart_money_last_updated": "2026-08-17T04:05:50.285490+00:00",
        }
        status = _client_returning(payload).status()
        self.assertEqual(status.last_updated.hour, 9)
        self.assertEqual(status.smart_money_last_updated.hour, 4)

    def test_rejects_array_payload(self):
        with self.assertRaises(PolyLabError):
            _client_returning([]).status()


class TestHolders(unittest.TestCase):
    def test_profitability_flag(self):
        rows = [
            {"wallet_address": "0xa", "total_pnl": 100.0},
            {"wallet_address": "0xb", "total_pnl": -5.0},
        ]
        holders = _client_returning(rows).holders("2063134")
        self.assertTrue(holders[0].is_profitable)
        self.assertFalse(holders[1].is_profitable)


if __name__ == "__main__":
    unittest.main()
