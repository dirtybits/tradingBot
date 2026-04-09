from __future__ import annotations

import base64
import json
import os
import secrets
import time
import uuid
from dataclasses import dataclass
from decimal import Decimal, ROUND_DOWN, InvalidOperation
from typing import Any, Iterable
from urllib.parse import urlsplit

import requests
from cryptography.hazmat.primitives import hashes, serialization  # pyright: ignore[reportMissingImports]
from cryptography.hazmat.primitives.asymmetric import ec  # pyright: ignore[reportMissingImports]
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature  # pyright: ignore[reportMissingImports]
from requests.auth import AuthBase

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional dependency
    load_dotenv = None


API_HOST = "api.coinbase.com"
API_BASE_PATH = "/api/v3/brokerage"
API_URL = f"https://{API_HOST}{API_BASE_PATH}"
DEFAULT_TIMEOUT_SECONDS = 10
DEFAULT_QUOTE_INCREMENT = "0.01"
DEFAULT_BASE_INCREMENT = "0.00000001"


class CoinbaseBotError(Exception):
    """Base exception for bot failures."""


class ConfigurationError(CoinbaseBotError):
    """Raised when required configuration is missing."""


class CoinbaseAPIError(CoinbaseBotError):
    """Raised when the brokerage request fails."""


@dataclass(frozen=True)
class CoinbaseCredentials:
    api_key: str
    api_secret: str


def load_credentials(required: bool = False) -> CoinbaseCredentials | None:
    """Load Advanced Trade credentials from the environment."""
    if load_dotenv is not None:
        load_dotenv()

    api_key = os.getenv("CB_API_KEY")
    api_secret = os.getenv("CB_API_SECRET")
    values = {
        "CB_API_KEY": api_key,
        "CB_API_SECRET": api_secret,
    }
    missing = [key for key, value in values.items() if not value]
    if missing:
        if required:
            raise ConfigurationError(
                f"Missing Coinbase credentials: {', '.join(missing)}."
            )
        return None

    normalized_secret = api_secret.replace("\\n", "\n")
    return CoinbaseCredentials(api_key=api_key, api_secret=normalized_secret)


def _decimal(value: Decimal | float | int | str) -> Decimal:
    return Decimal(str(value))


def _quantize_to_increment(
    value: Decimal | float | int | str,
    increment: Decimal | float | int | str,
) -> Decimal:
    decimal_value = _decimal(value)
    decimal_increment = _decimal(increment)
    steps = (decimal_value / decimal_increment).to_integral_value(
        rounding=ROUND_DOWN
    )
    return steps * decimal_increment


def _format_for_increment(
    value: Decimal | float | int | str,
    increment: Decimal | float | int | str,
) -> str:
    decimal_increment = _decimal(increment)
    quantized_value = _quantize_to_increment(value, decimal_increment)
    places = max(-decimal_increment.as_tuple().exponent, 0)
    return f"{quantized_value:.{places}f}"


def _format_decimal_string(value: Decimal | float | int | str) -> str:
    return format(_decimal(value), "f")


def parse_positive_decimal(value: str) -> Decimal:
    try:
        decimal_value = _decimal(value)
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"Invalid decimal amount: {value}") from exc
    if decimal_value <= 0:
        raise ValueError("Amount must be greater than zero.")
    return decimal_value


def _base64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _build_es256_jwt(
    payload: dict[str, Any],
    headers: dict[str, Any],
    private_key: ec.EllipticCurvePrivateKey,
) -> str:
    header_segment = _base64url_encode(
        json.dumps(headers, separators=(",", ":"), sort_keys=True).encode("utf-8")
    )
    payload_segment = _base64url_encode(
        json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    )
    signing_input = f"{header_segment}.{payload_segment}".encode("utf-8")
    signature_der = private_key.sign(signing_input, ec.ECDSA(hashes.SHA256()))
    r_value, s_value = decode_dss_signature(signature_der)
    signature_raw = r_value.to_bytes(32, "big") + s_value.to_bytes(32, "big")
    signature_segment = _base64url_encode(signature_raw)
    return f"{header_segment}.{payload_segment}.{signature_segment}"


def calculate_limit_price(
    reference_price: Decimal | float | int | str,
    factor: Decimal | float | int | str,
    side: str,
    quote_increment: Decimal | float | int | str = DEFAULT_QUOTE_INCREMENT,
) -> str:
    normalized_side = side.upper()
    if normalized_side not in {"BUY", "SELL"}:
        raise ValueError("side must be 'BUY' or 'SELL'")

    multiplier = (
        Decimal("1") - _decimal(factor)
        if normalized_side == "BUY"
        else Decimal("1") + _decimal(factor)
    )
    if multiplier <= 0:
        raise ValueError("factor results in a non-positive price")

    return _format_for_increment(
        _decimal(reference_price) * multiplier,
        quote_increment,
    )


def calculate_size_from_quote(
    quote_amount: Decimal | float | int | str,
    limit_price: Decimal | float | int | str,
    base_increment: Decimal | float | int | str = DEFAULT_BASE_INCREMENT,
) -> str:
    if _decimal(limit_price) <= 0:
        raise ValueError("limit_price must be positive")
    size = _decimal(quote_amount) / _decimal(limit_price)
    return _format_for_increment(size, base_increment)


def build_market_order(
    product_id: str,
    *,
    side: str = "BUY",
    quote_size: Decimal | float | int | str | None = None,
    base_size: Decimal | float | int | str | None = None,
    client_order_id: str | None = None,
) -> dict[str, Any]:
    if (quote_size is None) == (base_size is None):
        raise ValueError("Provide exactly one of quote_size or base_size.")

    market_ioc: dict[str, str] = {}
    if quote_size is not None:
        market_ioc["quote_size"] = _format_decimal_string(quote_size)
    if base_size is not None:
        market_ioc["base_size"] = _format_decimal_string(base_size)
    market_ioc["rfq_disabled"] = True

    return {
        "client_order_id": client_order_id or str(uuid.uuid4()),
        "product_id": product_id,
        "side": side.upper(),
        "order_configuration": {
            "market_market_ioc": market_ioc,
        },
    }


def build_limit_order(
    product_id: str,
    *,
    side: str,
    quote_amount: Decimal | float | int | str,
    reference_price: Decimal | float | int | str,
    price_factor: Decimal | float | int | str = "0.01",
    base_increment: Decimal | float | int | str = DEFAULT_BASE_INCREMENT,
    quote_increment: Decimal | float | int | str = DEFAULT_QUOTE_INCREMENT,
    client_order_id: str | None = None,
) -> dict[str, Any]:
    limit_price = calculate_limit_price(
        reference_price,
        price_factor,
        side=side,
        quote_increment=quote_increment,
    )
    base_size = calculate_size_from_quote(
        quote_amount=quote_amount,
        limit_price=limit_price,
        base_increment=base_increment,
    )
    return {
        "client_order_id": client_order_id or str(uuid.uuid4()),
        "product_id": product_id,
        "side": side.upper(),
        "order_configuration": {
            "limit_limit_gtc": {
                "base_size": base_size,
                "limit_price": limit_price,
                "post_only": False,
                "rfq_disabled": True,
            }
        },
    }


class CoinbaseAdvancedTradeAuth(AuthBase):
    def __init__(self, credentials: CoinbaseCredentials):
        self.api_key = credentials.api_key
        self.private_key = serialization.load_pem_private_key(
            credentials.api_secret.encode("utf-8"),
            password=None,
        )

    def __call__(self, request: requests.PreparedRequest) -> requests.PreparedRequest:
        url = urlsplit(request.url)
        path_with_query = url.path
        if url.query:
            path_with_query = f"{path_with_query}?{url.query}"

        payload = {
            "sub": self.api_key,
            "iss": "cdp",
            "nbf": int(time.time()),
            "exp": int(time.time()) + 120,
            "uri": f"{request.method} {API_HOST}{path_with_query}",
        }
        headers = {
            "alg": "ES256",
            "kid": self.api_key,
            "nonce": secrets.token_hex(),
            "typ": "JWT",
        }
        request.headers.update(
            {
                "Authorization": f"Bearer {_build_es256_jwt(payload, headers, self.private_key)}",
                "Content-Type": "application/json",
            }
        )
        return request


class CoinbaseAdvancedTradeClient:
    def __init__(
        self,
        credentials: CoinbaseCredentials | None = None,
        *,
        live_mode: bool = False,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
        session: requests.Session | None = None,
    ) -> None:
        self.credentials = credentials
        self.live_mode = live_mode
        self.timeout_seconds = timeout_seconds
        self.session = session or requests.Session()
        self.session.headers.update(
            {
                "Accept": "application/json",
                "Cache-Control": "no-cache",
                "User-Agent": "tradingBot/advanced-trade",
            }
        )
        self.auth = CoinbaseAdvancedTradeAuth(credentials) if credentials else None

    @classmethod
    def from_env(
        cls,
        *,
        live_mode: bool = False,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    ) -> "CoinbaseAdvancedTradeClient":
        credentials = load_credentials(required=live_mode)
        return cls(
            credentials=credentials,
            live_mode=live_mode,
            timeout_seconds=timeout_seconds,
        )

    def _request(
        self,
        method: str,
        path: str,
        *,
        auth_required: bool = False,
        params: dict[str, Any] | None = None,
        payload: dict[str, Any] | None = None,
    ) -> Any:
        auth = None
        if auth_required:
            if self.auth is None:
                raise ConfigurationError("This action requires Coinbase credentials.")
            auth = self.auth

        request_path = f"{API_BASE_PATH}/{path.lstrip('/')}"
        url = f"https://{API_HOST}{request_path}"
        try:
            response = self.session.request(
                method=method.upper(),
                url=url,
                params=params,
                json=payload,
                auth=auth,
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
        except requests.HTTPError as exc:
            detail = exc.response.text if exc.response is not None else str(exc)
            raise CoinbaseAPIError(
                f"{method.upper()} {path} failed: {detail}"
            ) from exc
        except requests.RequestException as exc:
            raise CoinbaseAPIError(
                f"{method.upper()} {path} failed: {exc}"
            ) from exc

        if not response.content:
            return {}

        try:
            return response.json()
        except ValueError as exc:
            raise CoinbaseAPIError(
                f"{method.upper()} {path} returned non-JSON content."
            ) from exc

    def _submit_private_action(
        self,
        method: str,
        path: str,
        payload: dict[str, Any],
    ) -> Any:
        if not self.live_mode:
            return {
                "dry_run": True,
                "method": method.upper(),
                "path": path,
                "payload": payload,
            }
        return self._request(
            method,
            path,
            auth_required=True,
            payload=payload,
        )

    def get_accounts(self) -> list[dict[str, Any]]:
        accounts: list[dict[str, Any]] = []
        cursor: str | None = None

        while True:
            params: dict[str, Any] = {"limit": 250}
            if cursor:
                params["cursor"] = cursor
            response = self._request(
                "GET",
                "accounts",
                auth_required=True,
                params=params,
            )
            accounts.extend(response.get("accounts", []))
            if not response.get("has_next"):
                break
            cursor = response.get("cursor")
            if not cursor:
                break

        return accounts

    def get_balances(self, *, non_zero_only: bool = True) -> list[dict[str, Any]]:
        accounts = self.get_accounts()
        if not non_zero_only:
            return accounts
        return [
            account
            for account in accounts
            if _decimal(account.get("available_balance", {}).get("value", "0")) > 0
        ]

    def get_product(self, product_id: str) -> dict[str, Any]:
        return self._request("GET", f"market/products/{product_id}")

    def get_ticker(self, product_id: str) -> dict[str, Any]:
        return self._request("GET", f"market/products/{product_id}/ticker")

    def check_prices(
        self,
        symbols: Iterable[str],
        quote: str = "USD",
    ) -> dict[str, float | str]:
        prices: dict[str, float | str] = {}
        last_time = None
        for symbol in symbols:
            product_id = f"{symbol}-{quote}"
            ticker = self.get_ticker(product_id)
            trades = ticker.get("trades", [])
            if trades:
                latest_trade = max(
                    trades,
                    key=lambda trade: trade.get("time", ""),
                )
                prices[symbol] = float(latest_trade["price"])
                last_time = latest_trade.get("time", last_time)
            else:
                product = self.get_product(product_id)
                prices[symbol] = float(product["price"])

        if last_time is not None:
            prices["time"] = last_time
        return prices

    def build_market_buy_order(
        self,
        product_id: str,
        *,
        funds: Decimal | float | int | str,
    ) -> dict[str, Any]:
        return build_market_order(
            product_id,
            side="BUY",
            quote_size=funds,
        )

    def place_market_order(
        self,
        product_id: str,
        *,
        funds: Decimal | float | int | str | None = None,
        base_size: Decimal | float | int | str | None = None,
        side: str = "BUY",
    ) -> Any:
        normalized_side = side.upper()
        if normalized_side == "BUY":
            if funds is None:
                raise ValueError("BUY market orders require funds.")
            payload = build_market_order(
                product_id,
                side="BUY",
                quote_size=funds,
            )
        else:
            sell_size = base_size if base_size is not None else funds
            if sell_size is None:
                raise ValueError("SELL market orders require base_size.")
            payload = build_market_order(
                product_id,
                side="SELL",
                base_size=sell_size,
            )
        return self._submit_private_action("POST", "orders", payload)
