from __future__ import annotations

import os
import unittest
from unittest.mock import Mock, patch

from cbpro import (
    CoinbaseAdvancedTradeClient,
    CoinbaseCredentials,
    build_limit_order,
    build_market_order,
    load_credentials,
    parse_positive_decimal,
)


class LoadCredentialsTests(unittest.TestCase):
    def test_load_credentials_from_environment(self) -> None:
        with patch.dict(
            os.environ,
            {
                "CB_API_KEY": "organizations/test/apiKeys/test",
                "CB_API_SECRET": "-----BEGIN EC PRIVATE KEY-----\\nsecret\\n-----END EC PRIVATE KEY-----\\n",
            },
            clear=False,
        ):
            credentials = load_credentials(required=True)

        self.assertEqual(
            credentials,
            CoinbaseCredentials(
                api_key="organizations/test/apiKeys/test",
                api_secret="-----BEGIN EC PRIVATE KEY-----\nsecret\n-----END EC PRIVATE KEY-----\n",
            ),
        )


class OrderPayloadTests(unittest.TestCase):
    def test_build_market_order_uses_advanced_trade_shape(self) -> None:
        payload = build_market_order(
            "BTC-USD",
            side="BUY",
            quote_size="10.00",
            client_order_id="order-1",
        )

        self.assertEqual(payload["client_order_id"], "order-1")
        self.assertEqual(payload["product_id"], "BTC-USD")
        self.assertEqual(payload["side"], "BUY")
        self.assertEqual(
            payload["order_configuration"]["market_market_ioc"]["quote_size"],
            "10.00",
        )
        self.assertTrue(payload["order_configuration"]["market_market_ioc"]["rfq_disabled"])

    def test_build_limit_order_uses_brokerage_configuration(self) -> None:
        payload = build_limit_order(
            product_id="BTC-USD",
            side="BUY",
            quote_amount="10",
            reference_price="50000",
            price_factor="0.01",
            base_increment="0.00000001",
            quote_increment="0.01",
            client_order_id="limit-1",
        )

        limit_order = payload["order_configuration"]["limit_limit_gtc"]
        self.assertEqual(payload["client_order_id"], "limit-1")
        self.assertEqual(limit_order["limit_price"], "49500.00")
        self.assertEqual(limit_order["base_size"], "0.00020202")
        self.assertTrue(limit_order["rfq_disabled"])

    def test_paper_market_buy_returns_dry_run_payload(self) -> None:
        session = Mock()
        session.headers = {}
        session.request.side_effect = AssertionError("network should not be called")
        client = CoinbaseAdvancedTradeClient(
            credentials=None,
            live_mode=False,
            session=session,
        )

        result = client.place_market_order("BTC-USD", funds="10")

        self.assertTrue(result["dry_run"])
        self.assertEqual(result["path"], "orders")
        self.assertEqual(result["payload"]["product_id"], "BTC-USD")
        self.assertEqual(result["payload"]["side"], "BUY")

    def test_dry_run_market_order_uses_brokerage_orders_path(self) -> None:
        session = Mock()
        session.headers = {}
        session.request.side_effect = AssertionError("network should not be called")
        client = CoinbaseAdvancedTradeClient(
            credentials=None,
            live_mode=False,
            session=session,
        )

        result = client.place_market_order("BTC-USD", funds="10")

        self.assertTrue(result["dry_run"])
        self.assertEqual(result["path"], "orders")
        self.assertEqual(result["payload"]["order_configuration"]["market_market_ioc"]["quote_size"], "10")

    def test_sell_market_order_uses_base_size(self) -> None:
        session = Mock()
        session.headers = {}
        session.request.side_effect = AssertionError("network should not be called")
        client = CoinbaseAdvancedTradeClient(
            credentials=None,
            live_mode=False,
            session=session,
        )

        result = client.place_market_order(
            "BTC-USD",
            side="SELL",
            base_size="0.001",
        )

        market_ioc = result["payload"]["order_configuration"]["market_market_ioc"]
        self.assertEqual(result["payload"]["side"], "SELL")
        self.assertEqual(market_ioc["base_size"], "0.001")

    def test_get_balances_filters_available_balance_value(self) -> None:
        client = CoinbaseAdvancedTradeClient(credentials=None, live_mode=False)
        with patch.object(
            client,
            "get_accounts",
            return_value=[
                {"currency": "BTC", "available_balance": {"value": "0.5"}},
                {"currency": "ETH", "available_balance": {"value": "0"}},
            ],
        ):
            balances = client.get_balances()

        self.assertEqual(len(balances), 1)
        self.assertEqual(balances[0]["currency"], "BTC")

    def test_parse_positive_decimal_rejects_zero(self) -> None:
        with self.assertRaises(ValueError):
            parse_positive_decimal("0")


if __name__ == "__main__":
    unittest.main()
