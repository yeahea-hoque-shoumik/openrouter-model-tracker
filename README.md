# OpenRouter Free-Model Tracker

Tracks OpenRouter's `:free` model catalog every 12 hours, records when models become free or stop being free, and sends a Telegram alert whenever the free list changes. History lives in your existing PostgreSQL server, so you can answer "how many days was model X free?".

## How it works

Every 12 hours the tracker:

1. Fetches `https://openrouter.ai/api/v1/models` (public, no key)
2. Extracts model ids ending in `:free`
3. Diffs against the stored free set
4. Writes a `poll_runs` row, updates `free_model_status`, appends `free_model_events`
5. Sends a Telegram message (every run, or only on change; see `NOTIFY_EVERY_RUN`)

Example message (the table is a monospace block; Telegram has no native tables):

```
📡 OpenRouter free models (2026-09-19 12:00 UTC)
🟢 Currently free (3):
Model                            Ctx  Int  Code  Agent
------------------------------  ----  ---  ----  -----
cohere/north-mini-code          256k  9.9  36.5    1.1
google/gemma-4-26b-a4b-it       131k    -  39.3      -
nvidia/nemotron-3-super-120b-…  262k   25  57.5      -
Int/Code/Agent = Artificial Analysis indexes
✅ Newly free: cohere/north-mini-code:free
❌ No longer free: mistralai/mistral-small-24b:free
```

`Lat` and `TPS` columns are added when at least one model has a value (needs `OPENROUTER_API_KEY`). Long names are shortened to 30 characters, and a very long list is trimmed to fit Telegram's message limit.

With `NOTIFY_EVERY_RUN=true` a message is sent after every run (including a failure notice if the fetch fails); with `false` only when something changed. The first run only records a baseline.

## Stack

Python 3.12 · PostgreSQL (existing server) · Docker Compose · Telegram Bot API. Designed for an OCI Ampere A1 (ARM64) instance; idle almost all the time.

## Setup

1. Create a Telegram bot via @BotFather (dedicated to this project) and get its chat ID.
2. Copy env template and fill in values:

   ```bash
   cp .env.example .env
   ```

   | Var | Description |
   |-----|-------------|
   | `DATABASE_URL` | Connection string of your existing Postgres, e.g. `postgresql://user:pass@host:5432/dbname` (must be reachable from the container; `localhost` is the container itself) |
   | `TELEGRAM_BOT_TOKEN` | Bot token |
   | `TELEGRAM_CHAT_ID` | Chat to notify |
   | `POLL_INTERVAL_HOURS` | Default `12` |
   | `OPENROUTER_API_KEY` | Optional. Enables the per-model latency/throughput lookup; without it those two fields stay empty |
   | `NOTIFY_EVERY_RUN` | `true` (default): send a Telegram report on every run. `false`: alert only when the free set changes (never on the first run) |

3. Start:

   ```bash
   docker compose up -d --build
   docker compose logs -f tracker
   ```

There is no bundled database. On each cycle the tracker applies `sql/init.sql` (idempotent), which creates the three tables in the target database if missing; the role needs permission to create tables.

## Running a poll manually

Run one poll cycle on demand (same logic and alerting as the scheduled run; it does not disturb the running scheduler):

```bash
docker compose exec tracker python -m app.main --once
```

If the container isn't running: `docker compose run --rm tracker python -m app.main --once`. Exit code is non-zero if the cycle failed.

## Querying history

Days a model was free (from the event log):

```bash
docker compose exec tracker python scripts/days_free.py qwen/qwen3-32b:free
```

Or raw SQL:

```sql
SELECT m.model_id, e.event_type, e.event_at
FROM free_model_events e JOIN models m ON m.id = e.model_pk
WHERE m.model_id = 'qwen/qwen3-32b:free'
ORDER BY e.event_at;
```

Recent runs:

```sql
SELECT run_at, total_models, free_model_count, status FROM poll_runs ORDER BY run_at DESC LIMIT 10;
```

## Schema

| Table | Purpose |
|-------|---------|
| `poll_runs` | One row per poll (counts, status, error) |
| `models` | One row per model seen free: name, context size, Artificial Analysis intelligence/coding/agentic scores, latency/throughput. Other tables reference it by `id` |
| `free_model_status` | Current free/paid state per model (`model_pk` → `models.id`) with first/last seen timestamps |
| `free_model_events` | Append-only `became_free` / `became_paid` / `removed` log (`model_pk` → `models.id`) |

Model details are refreshed from OpenRouter on every run. Scores are `NULL` when Artificial Analysis has none for a model. Latency/throughput are OpenRouter's median p50 across providers, exactly as reported, and only filled when `OPENROUTER_API_KEY` is set and OpenRouter returns them (they were null without a key when checked). An existing database in the older layout is migrated automatically on the next run.

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
