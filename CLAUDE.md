# tradingBot — CLAUDE.md

## Project overview

Coinbase Advanced Trade CLI (`tradebot`) — a Python command-line tool for placing market and limit orders, running DCA (Dollar Cost Averaging) schedules, checking prices/balances, and computing trading signals.

## Module layout

| File | Purpose |
|---|---|
| `tradebot.py` | CLI entry point — `argparse` subcommands, wires everything together |
| `cbpro.py` | Coinbase Advanced Trade API client (JWT auth, REST, order builders) |
| `dca.py` | DCA config loading (YAML/JSON/TOML), SQLite ledger, `execute_dca` |
| `strategies.py` | Pure signal functions: SMA crossover, RSI (Wilder EMA), trend-RSI |
| `webfeed.py` | Async websocket client for live price feed |

## Environment / credentials

Credentials are read from the environment (or a `.env` file via `python-dotenv`):

```
CB_API_KEY=...
CB_API_SECRET=...   # PEM-encoded EC private key; \n in the value is normalized
```

Commands that only read public data (`price`, `feed`, `signal`) work without credentials. Commands that touch accounts or place orders require them.

## Running tests

```bash
python -m unittest discover tests/
```

Tests use `unittest` (no pytest). All 40 tests run without network access — the API client has a `live_mode=False` dry-run path that returns a `{"dry_run": True, ...}` dict instead of hitting the API.

## Key design decisions

**Paper mode is the default.** Every order command (`buy`, `sell`, `limit-buy`, `limit-sell`, `dca run`) is a dry run unless `--live --yes` is passed. This prevents accidental real orders. The `--yes` flag is a second, explicit confirmation.

**`live_mode` flag on the client.** `CoinbaseAdvancedTradeClient.live_mode` controls whether `_submit_private_action` actually POSTs or returns a dry-run dict. Pass `live_mode=True` only when both `--live` and `--yes` are set.

**Limit orders use a price factor (fraction, not percent).** `price_factor=0.003` means 0.3% below/above market. The CLI flags (`--discount`, `--premium`) accept percent values and divide by 100 before passing to the client.

**DCA ledger deduplicates by `(run_date, product_id)`.** Re-running the same date skips assets already recorded. The SQLite file defaults to `~/.tradebot/dca.sqlite`.

**All CLI output is JSON to stdout.** Human-readable fill summaries go to stderr. This makes the CLI composable with `jq`.

**RSI uses Wilder's EMA smoothing**, seeded with a simple average of the first `period` changes — matches TradingView / standard TA libraries.

## DCA config format

```yaml
discount: 0.05        # percent below market for limit price (default: 0.01)
post_only: true       # guarantee maker fee or cancel (default: true)
min_quote_buffer: 0   # extra quote balance required beyond sum of funds
state_path: ~/.tradebot/dca.sqlite
assets:
  - product_id: BTC-USD
    funds: 15
  - product_id: ETH-USD
    funds: 10
```

Supports `.yaml`, `.yml`, `.json`, and `.toml`.

## Common commands

```bash
# Prices
tradebot price BTC ETH SOL

# Balances (requires credentials)
tradebot balances

# Paper buy
tradebot buy BTC-USD --funds 100

# Live limit buy at 0.05% below market
tradebot limit-buy BTC-USD --funds 100 --discount 0.05 --live --yes

# Signals
tradebot signal BTC-USD --strategy trend-rsi --trend-window 50 --candles 100

# DCA dry run
tradebot dca run --config dca.example.yaml

# DCA live
tradebot dca run --config dca.yaml --live --yes
```
