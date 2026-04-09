from __future__ import annotations

import tempfile
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path

from dca import DEFAULT_STATE_PATH, execute_dca, load_dca_config


class FakeClient:
    def __init__(self) -> None:
        self.live_mode = False
        self.price_calls: list[tuple[list[str], str]] = []
        self.order_calls: list[dict[str, object]] = []
        self.balance_rows: list[dict[str, object]] = []

    def check_prices(self, symbols: list[str], quote: str = "USD") -> dict[str, float]:
        self.price_calls.append((symbols, quote))
        return {symbols[0]: 100.0}

    def get_balances(self, *, non_zero_only: bool = True) -> list[dict[str, object]]:
        if non_zero_only:
            return [
                row for row in self.balance_rows
                if Decimal(str(row["available_balance"]["value"])) > 0
            ]
        return self.balance_rows

    def place_limit_order(self, product_id: str, **kwargs: object) -> dict[str, object]:
        self.order_calls.append({"product_id": product_id, **kwargs})
        return {
            "success": True,
            "success_response": {"order_id": f"order-{product_id}"},
            "order": {
                "status": "OPEN",
                "product_id": product_id,
                "side": "BUY",
                "order_configuration": {
                    "limit_limit_gtc": {
                        "limit_price": "99.99",
                        "post_only": kwargs["post_only"],
                    }
                },
            },
        }


class DcaConfigTests(unittest.TestCase):
    def test_load_dca_config_yaml_applies_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "dca.yaml"
            config_path.write_text(
                "\n".join(
                    [
                        "assets:",
                        "  - product_id: BTC-USD",
                        "    funds: 10",
                        "  - product_id: ETH-USD",
                        "    funds: 12.5",
                    ]
                )
            )

            config = load_dca_config(config_path)

        self.assertEqual(len(config.assets), 2)
        self.assertEqual(config.assets[0].product_id, "BTC-USD")
        self.assertEqual(config.assets[0].funds, Decimal("10"))
        self.assertEqual(config.assets[0].discount_pct, Decimal("0.01"))
        self.assertTrue(config.assets[0].post_only)
        self.assertEqual(config.min_quote_buffer, Decimal("0"))
        self.assertEqual(config.state_path, DEFAULT_STATE_PATH)


class DcaExecutionTests(unittest.TestCase):
    def test_execute_dca_paper_mode_does_not_record_runs(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "state.sqlite"
            config = load_dca_config_from_dict(
                {
                    "state_path": str(config_path),
                    "assets": [{"product_id": "BTC-USD", "funds": 10}],
                }
            )
            client = FakeClient()

            first = execute_dca(client, config, live_mode=False, run_date=date(2026, 4, 8))
            second = execute_dca(client, config, live_mode=False, run_date=date(2026, 4, 8))

        self.assertEqual(first["summary"]["previewed"], 1)
        self.assertEqual(second["summary"]["previewed"], 1)
        self.assertEqual(second["summary"]["skipped"], 0)
        self.assertEqual(len(client.order_calls), 2)

    def test_execute_dca_live_mode_skips_same_day_duplicates(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "state.sqlite"
            config = load_dca_config_from_dict(
                {
                    "state_path": str(config_path),
                    "assets": [{"product_id": "BTC-USD", "funds": 10}],
                }
            )
            client = FakeClient()
            client.balance_rows = [
                {"currency": "USD", "available_balance": {"value": "50"}},
            ]

            first = execute_dca(client, config, live_mode=True, run_date=date(2026, 4, 8))
            second = execute_dca(client, config, live_mode=True, run_date=date(2026, 4, 8))

        self.assertEqual(first["summary"]["submitted"], 1)
        self.assertEqual(second["summary"]["skipped"], 1)
        self.assertEqual(second["results"][0]["reason"], "already_executed_for_date")
        self.assertEqual(len(client.order_calls), 1)

    def test_execute_dca_uses_asset_specific_discount_and_post_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "state.sqlite"
            config = load_dca_config_from_dict(
                {
                    "state_path": str(config_path),
                    "discount": 0.1,
                    "post_only": True,
                    "assets": [
                        {"product_id": "BTC-USD", "funds": 10, "discount": 0.05, "post_only": False}
                    ],
                }
            )
            client = FakeClient()

            execute_dca(client, config, live_mode=False, run_date=date(2026, 4, 8))

        self.assertEqual(client.order_calls[0]["price_factor"], Decimal("0.0005"))
        self.assertEqual(client.order_calls[0]["post_only"], False)

    def test_execute_dca_live_mode_fails_safely_when_usd_too_low(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "state.sqlite"
            config = load_dca_config_from_text(
                "\n".join(
                    [
                        f"state_path: {config_path}",
                        "min_quote_buffer: 5",
                        "assets:",
                        "  - product_id: BTC-USD",
                        "    funds: 10",
                        "  - product_id: ETH-USD",
                        "    funds: 10",
                        "  - product_id: SOL-USD",
                        "    funds: 10",
                    ]
                )
            )
            client = FakeClient()
            client.balance_rows = [
                {"currency": "USD", "available_balance": {"value": "18.42"}},
            ]

            result = execute_dca(client, config, live_mode=True, run_date=date(2026, 4, 8))

        self.assertEqual(result["status"], "insufficient_funds")
        self.assertEqual(result["summary"]["submitted"], 0)
        self.assertEqual(result["summary"]["failed"], 3)
        self.assertEqual(result["shortfalls"][0]["required"], "35")
        self.assertEqual(result["shortfalls"][0]["available"], "18.42")
        self.assertEqual(len(client.order_calls), 0)


def load_dca_config_from_text(config_text: str):
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "dca.yaml"
        config_path.write_text(config_text)
        loaded = load_dca_config(config_path)
    return loaded


def load_dca_config_from_dict(config: dict[str, object]):
    lines: list[str] = []
    for key, value in config.items():
        if key == "assets":
            lines.append("assets:")
            for asset in value:
                lines.append(f"  - product_id: {asset['product_id']}")
                lines.append(f"    funds: {asset['funds']}")
                if "discount" in asset:
                    lines.append(f"    discount: {asset['discount']}")
                if "post_only" in asset:
                    lines.append(f"    post_only: {str(asset['post_only']).lower()}")
        else:
            rendered = str(value).lower() if isinstance(value, bool) else value
            lines.append(f"{key}: {rendered}")
    return load_dca_config_from_text("\n".join(lines))


if __name__ == "__main__":
    unittest.main()
