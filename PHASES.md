# PHASES.md

Phased plan: development → deployment → maintenance. Check items off as done.

## Phase 0 — Prerequisites

- [x] Create dedicated Telegram bot via @BotFather; record token and chat ID
- [x] Confirm SSH + Docker + Compose on OCI Ampere A1 instance
- [x] Init repo, `.gitignore` (`.env`, `__pycache__`, `.venv`), `.env.example`
- [x] Project skeleton: `app/`, `sql/`, `tests/`, `scripts/`, `requirements.txt`

**Done when:** repo skeleton exists and bot token works via a manual `curl` to `sendMessage`.

## Phase 1 — Schema & connectivity (Milestone 1)

- [x] Use an existing PostgreSQL server (no bundled container); `DATABASE_URL` in `.env`
- [x] `sql/init.sql` creating `poll_runs`, `free_model_status`, `free_model_events` (applied idempotently by the app at the start of each cycle)
- [x] `db.py` connection helper reading `DATABASE_URL`

**Done when:** the target database has three tables after the first cycle; app can connect and run `SELECT 1`.

## Phase 2 — Core poll/diff logic (Milestone 2)

- [x] `fetcher.py`: GET `/api/v1/models`, timeout + retry, parse JSON
- [x] Filter ids ending in `:free`
- [x] `diff.py`: pure function `(previous_free, current_free, all_ids) -> newly_free, became_paid, removed`
- [x] Unit tests: no change, added, dropped (paid vs removed), first run (empty DB), empty/garbage API response

**Done when:** `pytest` green; fetcher returns a real free set against live API.

## Phase 3 — Persistence layer (Milestone 3)

- [x] Insert `poll_runs` (ok and error variants)
- [x] Upsert `free_model_status` (set `first_seen_free_at` once, bump `last_seen_free_at` / `last_checked_at`)
- [x] Append `free_model_events` linked to `run_id`
- [x] Single transaction per run
- [x] First-run behavior decided: seed baseline without flooding alerts (recommended: record events but send one summary, or skip alert)

**Done when:** running one poll twice against live API yields two `poll_runs`, correct status rows, zero events on the second run.

## Phase 4 — Telegram integration (Milestone 4)

- [x] `notifier.py`: send message via Bot API
- [x] Message format per plan (timestamp UTC, ✅ newly free, ❌ no longer free)
- [x] Fire only on non-empty diff
- [x] Send failure logged, never raises past the run; DB write already committed

**Done when:** simulated diff produces a Telegram message; broken token logs an error and run still persists.

## Phase 5 — Scheduler + Dockerfile (Milestone 5)

- [x] `main.py`: run one cycle at startup, then every `POLL_INTERVAL_HOURS`
- [x] Top-level exception handling: a failed cycle logs and writes `status='error'`; loop continues
- [x] Structured stdout logs (status, total, free count, diff sizes)
- [x] `Dockerfile` on `python:3.12-slim`, non-root user, arm64-compatible deps
- [x] Add `tracker` service to compose: `restart: unless-stopped`, `env_file: .env` (Postgres is external)

**Done when:** `docker compose up --build` locally runs a cycle, persists, and survives a Postgres outage/restart.

## Phase 6 — Deploy to OCI (Milestone 6)

- [ ] Copy repo + `.env` to instance (never commit `.env`)
- [ ] `docker compose up -d --build` on the Ampere A1
- [ ] Verify first real run: `docker compose logs tracker`, rows in `poll_runs`
- [ ] Verify second scheduled run (12h later) and a real Telegram alert on change
- [ ] Reboot test: containers return automatically; data intact in the existing Postgres

**Done when:** two consecutive real runs succeed unattended.

## Phase 7 — Query script (Milestone 7)

- [x] `scripts/days_free.py <model_id>`: compute total days free from `free_model_events` (sum `became_free` → next `became_paid`/`removed`; open interval runs to now)
- [x] Handle multiple free windows per model
- [x] Document usage in README

**Done when:** script output matches hand-computed result for a model with at least one full window.

## Phase 8 — Maintenance (ongoing)

Routine:

- [ ] Weekly glance at `docker compose logs --tail 200 tracker` and latest `poll_runs` for `status='error'`
- [ ] Monthly: `docker compose pull && docker compose up -d --build` for base image security updates
- [ ] Confirm the tracker's tables stay small (`SELECT pg_size_pretty(pg_total_relation_size('free_model_events'))`)

Backups:

- [ ] Periodic `pg_dump` to a file off the instance (cron on host): `pg_dump "$DATABASE_URL" -t poll_runs -t free_model_status -t free_model_events > backup.sql` (or include it in your existing Postgres backups)
- [ ] Test a restore once

Failure modes to watch:

| Symptom | Likely cause | Action |
|---------|--------------|--------|
| Repeated `status='error'` runs | OpenRouter API change/outage, network | Check response shape; adjust parser |
| No Telegram alerts but events written | Bad token/chat ID, bot blocked | Check logs; rotate token |
| No new `poll_runs` rows | Container down / scheduler stuck | `docker compose ps`, restart |
| Sudden mass `removed` events | Truncated/empty API response | Add sanity guard: skip diff if response implausibly small |

Retention: keep all rows indefinitely (v1 assumption). Revisit only if tables grow unexpectedly.

## Phase 9 — Future enhancements (out of v1 scope)

- [ ] Ship logs to PLG (Prometheus/Loki/Grafana)
- [ ] Read-only HTTP endpoint or Grafana panel over Postgres
- [ ] Track general price changes, not just free/paid transitions
- [ ] Heartbeat alert if no successful run in 24h+
