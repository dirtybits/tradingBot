# tradingBot

A small Coinbase Advanced Trade CLI for:
- public price lookups
- authenticated balance queries
- dry-run market buy payload generation
- guarded live market buys
- websocket ticker snapshots

Core files:
- `cbpro.py`: Advanced Trade REST client and auth helpers
- `webfeed.py`: Advanced Trade websocket helpers
- `bot.py`: CLI entrypoint
- `strategies.py`: pure strategy helpers

## Setup

Install dependencies with `uv` in a project-local virtual environment:

```bash
brew install uv
uv venv .venv
source .venv/bin/activate
uv pip install -r requirements.txt
```

Set Advanced Trade credentials in your environment or `.env`:

```bash
CB_API_KEY="organizations/{org_id}/apiKeys/{key_id}"
CB_API_SECRET="-----BEGIN EC PRIVATE KEY-----\nYOUR PRIVATE KEY\n-----END EC PRIVATE KEY-----\n"
```

Notes:
- Use an Advanced Trade CDP API key, not old Coinbase Pro credentials.
- The private key must preserve newlines. Escaped `\n` values in `.env` are supported.

## Usage

Fetch prices:

```bash
python3 bot.py price BTC ETH --quote USD
```

List balances:

```bash
python3 bot.py balances
```

Generate a local dry-run market-buy payload:

```bash
python3 bot.py paper-buy BTC-USD --funds 10
```

Place a live buy:

```bash
python3 bot.py live-buy BTC-USD --funds 10 --confirm-live
```

Fetch one websocket ticker update per product:

```bash
python3 bot.py feed BTC-USD ETH-USD
```


