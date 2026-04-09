# tradingBot

A Coinbase Advanced Trade CLI for price lookups, balance queries, market orders, websocket snapshots, technical signals, and config-driven daily DCA runs.

Core files:
- `tradebot.py` — CLI entrypoint
- `dca.py` — config loading, DCA runner, and sqlite idempotency ledger
- `cbpro.py` — Advanced Trade REST client and auth helpers
- `webfeed.py` — Advanced Trade websocket helpers
- `strategies.py` — pure strategy helpers (SMA, RSI, crossover, RSI signal)

## Setup

Install dependencies with `uv`:

```bash
brew install uv
uv venv .venv
source .venv/bin/activate
uv pip install -e .
```

The `-e .` install makes `tradebot` available as a command. Set credentials in your environment or `.env`:

```bash
CB_API_KEY="organizations/{org_id}/apiKeys/{key_id}"
CB_API_SECRET="-----BEGIN EC PRIVATE KEY-----\nYOUR PRIVATE KEY\n-----END EC PRIVATE KEY-----\n"
```

Notes:
- Use an Advanced Trade CDP API key, not old Coinbase Pro credentials.
- The private key must preserve newlines. Escaped `\n` values in `.env` are supported.

## Commands

All commands output JSON to stdout. Errors print to stderr with exit code 1.

### `price` — fetch current prices

```bash
tradebot price BTC
tradebot price BTC ETH SOL
tradebot price BTC ETH --quote EUR
```

### `balances` — list account balances (requires credentials)

```bash
tradebot balances
tradebot balances --all          # include zero-balance accounts
```

### `buy` — market buy order

Paper mode by default (builds the order payload without sending it).

```bash
tradebot buy BTC-USD --funds 100
tradebot buy ETH-USD --funds 50 --live --yes   # submit a real order
```

### `sell` — market sell order

Paper mode by default.

```bash
tradebot sell BTC-USD --size 0.001
tradebot sell ETH-USD --size 0.01 --live --yes  # submit a real order
```

### `limit-buy` / `limit-sell` — maker-friendly limit orders

Use these to place resting GTC limit orders near market. `--post-only` ensures
maker execution (or cancellation), so you never accidentally pay taker fees.

```bash
# Preview a limit buy (paper mode)
tradebot limit-buy BTC-USD --funds 100

# 0.5% below market instead of the default 0.3%
tradebot limit-buy BTC-USD --funds 100 --discount 0.5

# Live post-only limit buy (maker-or-cancel)
tradebot limit-buy BTC-USD --funds 100 --post-only --live --yes

# Live limit sell 0.3% above market (default premium)
tradebot limit-sell BTC-USD --size 0.001 --live --yes
```

### `feed` — websocket ticker snapshot

Collects one price update per product and exits.

```bash
tradebot feed BTC-USD
tradebot feed BTC-USD ETH-USD SOL-USD
```

### `signal` — technical signal from recent candles

Fetches candles from the REST API, runs a strategy, and returns a `buy`/`sell`/`hold` signal.

```bash
tradebot signal BTC-USD                           # moving-average crossover, 1h candles
tradebot signal BTC-USD --strategy rsi            # RSI strategy
tradebot signal ETH-USD --strategy crossover --short-window 5 --long-window 20
tradebot signal BTC-USD --strategy rsi --candles 50 --period 14 --oversold 30 --overbought 70
tradebot signal BTC-USD --granularity FIFTEEN_MINUTE --candles 100
```

Available granularities: `ONE_MINUTE`, `FIVE_MINUTE`, `FIFTEEN_MINUTE`, `THIRTY_MINUTE`, `ONE_HOUR`, `TWO_HOUR`, `SIX_HOUR`, `ONE_DAY`.

### `dca run` — config-driven daily buys

Runs a daily set of limit buys from a config file. In live mode, successful
same-day submissions are recorded in a local sqlite ledger so a cron retry does
not submit duplicates for the same asset/date.

```bash
# Paper mode preview
tradebot dca run --config dca.example.json

# Backfill or test a specific day
tradebot dca run --config dca.example.json --date 2026-04-08

# Live run
tradebot dca run --config dca.example.json --live --yes
```

Example config:

```json
{
  "discount": 0.01,
  "post_only": true,
  "state_path": "~/.tradebot/dca.sqlite",
  "assets": [
    { "product_id": "BTC-USD", "funds": 10 },
    { "product_id": "ETH-USD", "funds": 10 },
    { "product_id": "SOL-USD", "funds": 10 }
  ]
}
```

Notes:
- `discount` is a percent below market, so `0.01` means `0.01%`, not `1%`.
- `post_only: true` makes each order maker-or-cancel.
- The sqlite ledger only records live submissions; paper runs stay repeatable.

### Cron

Use cron to run the DCA job once per day. Example: 9:00 AM local time.

```cron
0 9 * * * cd /absolute/path/to/tradingBot && /absolute/path/to/tradingBot/.venv/bin/tradebot dca run --config /absolute/path/to/tradingBot/dca.example.json --live --yes >> ~/.tradebot/dca.log 2>&1
```

Tips:
- Use absolute paths for both `tradebot` and the config file.
- Keep the log file so you can inspect skipped/failed/submitted assets later.
- Test the command in paper mode before enabling the live cron line.

### Global help

```bash
tradebot --help
tradebot <command> --help
```
