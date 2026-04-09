# tradingBot

A Coinbase Advanced Trade CLI for price lookups, balance queries, market orders, websocket snapshots, and technical signals.

Core files:
- `tradebot.py` — CLI entrypoint
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
bot price BTC
bot price BTC ETH SOL
bot price BTC ETH --quote EUR
```

### `balances` — list account balances (requires credentials)

```bash
bot balances
bot balances --all          # include zero-balance accounts
```

### `buy` — market buy order

Paper mode by default (builds the order payload without sending it).

```bash
bot buy BTC-USD --funds 100
bot buy ETH-USD --funds 50 --live --yes   # submit a real order
```

### `sell` — market sell order

Paper mode by default.

```bash
bot sell BTC-USD --size 0.001
bot sell ETH-USD --size 0.01 --live --yes  # submit a real order
```

### `feed` — websocket ticker snapshot

Collects one price update per product and exits.

```bash
bot feed BTC-USD
bot feed BTC-USD ETH-USD SOL-USD
```

### `signal` — technical signal from recent candles

Fetches candles from the REST API, runs a strategy, and returns a `buy`/`sell`/`hold` signal.

```bash
bot signal BTC-USD                           # moving-average crossover, 1h candles
bot signal BTC-USD --strategy rsi            # RSI strategy
bot signal ETH-USD --strategy crossover --short-window 5 --long-window 20
bot signal BTC-USD --strategy rsi --candles 50 --period 14 --oversold 30 --overbought 70
bot signal BTC-USD --granularity FIFTEEN_MINUTE --candles 100
```

Available granularities: `ONE_MINUTE`, `FIVE_MINUTE`, `FIFTEEN_MINUTE`, `THIRTY_MINUTE`, `ONE_HOUR`, `TWO_HOUR`, `SIX_HOUR`, `ONE_DAY`.

### Global help

```bash
bot --help
bot <command> --help
```
