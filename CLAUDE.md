# CLAUDE.md

Guidance for Claude Code when working in this repo.

## Project goal

Poll OpenRouter's public model catalog every 12 hours, detect models that become free or stop being free (`:free` suffix on model `id`), store a queryable history in PostgreSQL, and send a Telegram alert whenever the free-model set changes. Runs as one Docker container (tracker) against an existing external PostgreSQL server on an OCI Ampere A1 (ARM64) instance.

Source plan: Notion page "OpenRouter Free-Model Tracker — Project Plan". See `PHASES.md` for the phased roadmap and `README.md` for usage.

## Stack

- Python 3.12, base image `python:3.12-slim` (must build for linux/arm64)
- Scheduler: in-process (`APScheduler` or `while True` + sleep), every `POLL_INTERVAL_HOURS` (default 12)
- Data source: `GET https://openrouter.ai/api/v1/models` (no API key)
- Storage: existing external PostgreSQL server (no bundled container); the app applies `sql/init.sql` idempotently at the start of each cycle
- Alerts: Telegram Bot API, dedicated bot (NOT the `auto_shutdown_oci` bot)
- Deploy: `docker-compose.yml`, `restart: unless-stopped`

## Poll cycle

1. Fetch `/api/v1/models`
2. Collect every model `id` ending in `:free`
3. Diff against current free set in Postgres
4. Write `poll_runs` row, upsert `free_model_status`, insert `free_model_events`
5. Send one Telegram message: every run if `NOTIFY_EVERY_RUN=true` (default; lists currently free, newly free, no longer free), otherwise only if diff non-empty and not the first run
6. Log run outcome (status, counts) to stdout

## Schema (4 tables)

- `poll_runs` — one row per run (`total_models`, `free_model_count`, `status` ok|error, `error_message`)
- `models` — one row per model seen free (`id` PK, unique `model_id` text, `name`, `context_length`, `max_completion_tokens`, Artificial Analysis `intelligence_index`/`coding_index`/`agentic_index`, `latency_p50`, `throughput_p50`); refreshed each run. Other tables reference `models.id`, never the model name text
- `free_model_status` — current state per model, PK/FK `model_pk` (`currently_free`, `first_seen_free_at`, `last_seen_free_at`, `last_checked_at`)
- `free_model_events` — append-only log; FKs `run_id` → `poll_runs`, `model_pk` → `models`; `event_type` in `became_free | became_paid | removed`

The event log is the source of truth for "how many days was model X free".

## Git policy

- Remote `origin`: `git@github.com:yeahea-hoque-shoumik/openrouter-model-tracker.git`
- Claude must NEVER run `git commit` or `git push` (or amend/force-push/tag-push). The user commits and pushes manually. Staging/status/diff are fine only if asked.

## Rules and invariants

- Diff logic is a pure function (no I/O) and must have unit tests.
- A failed Telegram send is logged, never fatal. The run must still persist to Postgres.
- A failed fetch writes a `poll_runs` row with `status='error'` and the scheduler keeps running; the process must not crash.
- Persist one run's writes in a single transaction.
- Events are append-only. Never update or delete `free_model_events` rows.
- Retain all `poll_runs` and `free_model_events` rows indefinitely (v1 assumption; tables are tiny).
- Distinguish `became_paid` (model still listed, no longer `:free`) from `removed` (model gone from catalog).
- All config via env vars; never hardcode or commit secrets. `.env` is gitignored; keep `.env.example` current.
- Timestamps are `TIMESTAMPTZ`, UTC.
- Logs go to stdout only (captured by `docker logs`).

## Config (env vars)

| Var | Purpose                                                               |
|-----|-----------------------------------------------------------------------|
| `DATABASE_URL` | Connection string of the existing Postgres (`postgresql://user:pass@host:5432/openrouter_models`) |
| `TELEGRAM_BOT_TOKEN` | Bot token from @BotFather                                             |
| `TELEGRAM_CHAT_ID` | Target chat                                                           |
| `POLL_INTERVAL_HOURS` | Default `12`                                                          |
| `OPENROUTER_API_KEY` | Optional; enables latency/throughput lookup via `/models/{id}/endpoints` (null otherwise) |
| `NOTIFY_EVERY_RUN` | `true` (default) = message every run; `false` = only on change |

## Out of scope for v1

PLG log shipping, HTTP endpoint / Grafana panel, general price-change tracking. Do not build these unless asked.

## Conventions

- Keep the footprint small: minimal dependencies (e.g. `requests`/`httpx`, `psycopg`, optionally `APScheduler`).
- Suggested layout: `app/` (`main.py`, `fetcher.py`, `diff.py`, `db.py`, `notifier.py`, `config.py`), `sql/init.sql`, `tests/`, `scripts/days_free.py`, `Dockerfile`, `docker-compose.yml`.
- Tests: `pytest`. Run before finishing any change.
- Match surrounding code style; no speculative abstractions.

## Commands

```bash
docker compose up -d --build     # start tracker
docker compose logs -f tracker   # follow logs
pytest                           # unit tests
docker compose exec tracker python -m app.main --once   # run one poll manually
psql "$DATABASE_URL"                # inspect data
```
