from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, UTC
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from cbpro import CoinbaseAdvancedTradeClient, parse_positive_decimal
import yaml

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    tomllib = None


DEFAULT_DISCOUNT_PCT = Decimal("0.01")
DEFAULT_STATE_PATH = Path("~/.tradebot/dca.sqlite").expanduser()


@dataclass(frozen=True)
class DcaAsset:
    product_id: str
    funds: Decimal
    discount_pct: Decimal
    post_only: bool


@dataclass(frozen=True)
class DcaConfig:
    assets: list[DcaAsset]
    state_path: Path
    min_quote_buffer: Decimal


def _parse_non_negative_decimal(value: Any, field_name: str) -> Decimal:
    try:
        decimal_value = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError(f"Invalid decimal value for {field_name}: {value}") from exc
    if decimal_value < 0:
        raise ValueError(f"{field_name} must be greater than or equal to zero.")
    return decimal_value


def _load_config_document(path: Path) -> dict[str, Any]:
    suffix = path.suffix.lower()
    if suffix in {".yaml", ".yml"}:
        loaded = yaml.safe_load(path.read_text())
        return loaded if loaded is not None else {}
    if suffix == ".json":
        return json.loads(path.read_text())
    if suffix == ".toml":
        if tomllib is None:
            raise ValueError("TOML config support requires Python 3.11+.")
        return tomllib.loads(path.read_text())
    raise ValueError("Config file must end in .yaml, .yml, .json, or .toml.")


def load_dca_config(path: str | os.PathLike[str]) -> DcaConfig:
    config_path = Path(path).expanduser()
    raw = _load_config_document(config_path)
    if not isinstance(raw, dict):
        raise ValueError("DCA config must be a YAML/JSON/TOML object.")

    raw_assets = raw.get("assets")
    if not isinstance(raw_assets, list) or not raw_assets:
        raise ValueError("DCA config must include a non-empty 'assets' list.")

    default_discount_pct = _parse_non_negative_decimal(
        raw.get("discount", DEFAULT_DISCOUNT_PCT),
        "discount",
    )
    default_post_only = bool(raw.get("post_only", True))
    min_quote_buffer = _parse_non_negative_decimal(
        raw.get("min_quote_buffer", "0"),
        "min_quote_buffer",
    )
    raw_state_path = raw.get("state_path")
    state_path = (
        Path(str(raw_state_path)).expanduser()
        if raw_state_path is not None
        else DEFAULT_STATE_PATH
    )

    assets: list[DcaAsset] = []
    for index, raw_asset in enumerate(raw_assets, start=1):
        if not isinstance(raw_asset, dict):
            raise ValueError(f"Asset #{index} must be an object.")
        product_id = str(raw_asset.get("product_id", "")).strip()
        if not product_id:
            raise ValueError(f"Asset #{index} is missing product_id.")

        if "funds" not in raw_asset:
            raise ValueError(f"Asset #{index} is missing funds.")
        funds = parse_positive_decimal(str(raw_asset["funds"]))
        discount_pct = _parse_non_negative_decimal(
            raw_asset.get("discount", default_discount_pct),
            f"assets[{index}].discount",
        )
        post_only = bool(raw_asset.get("post_only", default_post_only))
        assets.append(
            DcaAsset(
                product_id=product_id,
                funds=funds,
                discount_pct=discount_pct,
                post_only=post_only,
            )
        )

    return DcaConfig(
        assets=assets,
        state_path=state_path,
        min_quote_buffer=min_quote_buffer,
    )


class DcaLedger:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS dca_runs (
                    run_date TEXT NOT NULL,
                    product_id TEXT NOT NULL,
                    funds TEXT NOT NULL,
                    status TEXT NOT NULL,
                    order_id TEXT,
                    result_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (run_date, product_id)
                )
                """
            )

    def get_entry(self, run_date: str, product_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT run_date, product_id, funds, status, order_id, result_json, created_at
                FROM dca_runs
                WHERE run_date = ? AND product_id = ?
                """,
                (run_date, product_id),
            ).fetchone()
        if row is None:
            return None
        return {
            "run_date": row["run_date"],
            "product_id": row["product_id"],
            "funds": row["funds"],
            "status": row["status"],
            "order_id": row["order_id"],
            "result": json.loads(row["result_json"]),
            "created_at": row["created_at"],
        }

    def record(
        self,
        run_date: str,
        asset: DcaAsset,
        *,
        status: str,
        order_id: str | None,
        result: dict[str, Any],
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO dca_runs
                    (run_date, product_id, funds, status, order_id, result_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_date,
                    asset.product_id,
                    str(asset.funds),
                    status,
                    order_id,
                    json.dumps(result, sort_keys=True, default=str),
                    datetime.now(UTC).isoformat(),
                ),
            )


def _reference_price_for_product(
    client: CoinbaseAdvancedTradeClient,
    product_id: str,
) -> float | str:
    base, _, quote = product_id.partition("-")
    prices = client.check_prices([base], quote=quote or "USD")
    price = prices.get(base)
    if price is None:
        raise ValueError(f"Could not fetch price for {product_id}")
    return price


def _result_status(result: dict[str, Any]) -> str:
    order = result.get("order")
    if isinstance(order, dict):
        status = order.get("status")
        if status:
            return str(status).lower()
    return "submitted"


def _asset_quote_currency(product_id: str) -> str:
    _, _, quote = product_id.partition("-")
    return quote or "USD"


def _available_quote_balances(
    client: CoinbaseAdvancedTradeClient,
) -> dict[str, Decimal]:
    balances: dict[str, Decimal] = {}
    for account in client.get_balances(non_zero_only=False):
        currency = str(account.get("currency", "")).upper()
        available_value = account.get("available_balance", {}).get("value", "0")
        try:
            balances[currency] = Decimal(str(available_value))
        except (InvalidOperation, TypeError, ValueError):
            continue
    return balances


def _required_quote_balances(config: DcaConfig) -> dict[str, Decimal]:
    required: dict[str, Decimal] = {}
    for asset in config.assets:
        quote = _asset_quote_currency(asset.product_id).upper()
        required[quote] = required.get(quote, Decimal("0")) + asset.funds
    for quote in list(required):
        required[quote] += config.min_quote_buffer
    return required


def _preflight_quote_balances(
    client: CoinbaseAdvancedTradeClient,
    config: DcaConfig,
) -> dict[str, Any] | None:
    required = _required_quote_balances(config)
    available = _available_quote_balances(client)
    shortfalls: list[dict[str, str]] = []

    for quote, required_amount in required.items():
        available_amount = available.get(quote, Decimal("0"))
        if available_amount < required_amount:
            shortfalls.append(
                {
                    "quote": quote,
                    "available": str(available_amount),
                    "required": str(required_amount),
                    "shortfall": str(required_amount - available_amount),
                }
            )

    if not shortfalls:
        return None

    return {
        "status": "insufficient_funds",
        "available_balances": {quote: str(amount) for quote, amount in available.items()},
        "required_balances": {quote: str(amount) for quote, amount in required.items()},
        "shortfalls": shortfalls,
    }


def execute_dca(
    client: CoinbaseAdvancedTradeClient,
    config: DcaConfig,
    *,
    live_mode: bool,
    run_date: date | None = None,
) -> dict[str, Any]:
    effective_date = (run_date or date.today()).isoformat()
    ledger = DcaLedger(config.state_path)
    results: list[dict[str, Any]] = []

    if live_mode:
        preflight = _preflight_quote_balances(client, config)
        if preflight is not None:
            return {
                "command": "dca run",
                "run_date": effective_date,
                "live_mode": live_mode,
                "state_path": str(config.state_path),
                "results": results,
                "summary": {
                    "submitted": 0,
                    "previewed": 0,
                    "skipped": 0,
                    "failed": len(config.assets),
                },
                **preflight,
            }

    for asset in config.assets:
        existing = ledger.get_entry(effective_date, asset.product_id)
        if existing is not None:
            results.append(
                {
                    "product_id": asset.product_id,
                    "funds": str(asset.funds),
                    "status": "skipped",
                    "reason": "already_executed_for_date",
                    "existing_status": existing["status"],
                    "order_id": existing.get("order_id"),
                }
            )
            continue

        try:
            reference_price = _reference_price_for_product(client, asset.product_id)
            result = client.place_limit_order(
                asset.product_id,
                side="BUY",
                quote_amount=asset.funds,
                reference_price=reference_price,
                price_factor=asset.discount_pct / Decimal("100"),
                post_only=asset.post_only,
            )
            asset_result = {
                "product_id": asset.product_id,
                "funds": str(asset.funds),
                "discount_pct": str(asset.discount_pct),
                "post_only": asset.post_only,
                "reference_price": reference_price,
                "result": result,
                "status": "submitted" if live_mode else "preview",
            }
            if live_mode:
                success_response = result.get("success_response", {})
                order_id = (
                    success_response.get("order_id")
                    if isinstance(success_response, dict)
                    else None
                )
                if result.get("success") is False or order_id is None:
                    asset_result["status"] = "failed"
                    asset_result["error"] = "Live order was not accepted by Coinbase."
                else:
                    status = _result_status(result)
                    asset_result["status"] = status
                    asset_result["order_id"] = order_id
                    ledger.record(
                        effective_date,
                        asset,
                        status=status,
                        order_id=order_id,
                        result=asset_result,
                    )
            results.append(asset_result)
        except Exception as exc:
            results.append(
                {
                    "product_id": asset.product_id,
                    "funds": str(asset.funds),
                    "discount_pct": str(asset.discount_pct),
                    "post_only": asset.post_only,
                    "status": "failed",
                    "error": str(exc),
                }
            )

    summary = {
        "submitted": sum(1 for item in results if item["status"] in {"submitted", "open", "pending", "filled"}),
        "previewed": sum(1 for item in results if item["status"] == "preview"),
        "skipped": sum(1 for item in results if item["status"] == "skipped"),
        "failed": sum(1 for item in results if item["status"] == "failed"),
    }
    return {
        "command": "dca run",
        "run_date": effective_date,
        "live_mode": live_mode,
        "state_path": str(config.state_path),
        "results": results,
        "summary": summary,
    }
