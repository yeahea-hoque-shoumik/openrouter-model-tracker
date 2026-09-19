# OpenRouter Free-Model Tracker

Tracks OpenRouter's `:free` model catalog every 12 hours, records when models become free or stop being free, and sends a Telegram alert whenever the free list changes. History lives in Postgres, so you can answer "how many days was model X free?".

## How it works

Every 12 hours the tracker:

1. Fetches `https://openrouter.ai/api/v1/models` (public, no key)
2. Extracts model ids ending in `:free`
3. Diffs against the stored free set
4. Writes a `poll_runs` row, updates `free_model_status`, appends `free_model_events`
5. Sends a Telegram message if anything changed

Example alert:

```
📡 OpenRouter free-model change (2026-09-19 12:00 UTC)
✅ Newly free: qwen/qwen3-32b:free
❌ No longer free: mistralai/mistral-small-24b:free
```

## Stack

Python 3.12 · PostgreSQL 16 · Docker Compose · Telegram Bot API. Designed for an OCI Ampere A1 (ARM64) instance; idle almost all the time.

## Setup

1. Create a Telegram bot via @BotFather (dedicated to this project) and get its chat ID.
2. Copy env template and fill in values:

   ```bash
   cp .env.example .env
   ```

   | Var | Description |
   |-----|-------------|
   | `DB_PASSWORD` | Postgres password |
   | `TELEGRAM_BOT_TOKEN` | Bot token |
   | `TELEGRAM_CHAT_ID` | Chat to notify |
   | `POLL_INTERVAL_HOURS` | Default `12` |

3. Start:

   ```bash
   docker compose up -d --build
   docker compose logs -f tracker
   ```

Postgres data persists in the `pgdata` named volume across restarts and updates.

## Querying history

Days a model was free (from the event log):

```bash
python scripts/days_free.py qwen/qwen3-32b:free
```

Or raw SQL:

```sql
SELECT model_id, event_type, event_at
FROM free_model_events
WHERE model_id = 'qwen/qwen3-32b:free'
ORDER BY event_at;
```

Recent runs:

```sql
SELECT run_at, total_models, free_model_count, status FROM poll_runs ORDER BY run_at DESC LIMIT 10;
```

## Schema

| Table | Purpose |
|-------|---------|
| `poll_runs` | One row per poll (counts, status, error) |
| `free_model_status` | Current free/paid state per model with first/last seen timestamps |
| `free_model_events` | Append-only `became_free` / `became_paid` / `removed` log |

## Development

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest
```

## Roadmap

See [PHASES.md](PHASES.md). Project rules for Claude Code are in [CLAUDE.md](CLAUDE.md).

## Not in v1

Log shipping to PLG, read-only HTTP endpoint/Grafana panel, general price-change tracking.
