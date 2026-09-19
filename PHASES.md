# PHASES.md

Phased plan: development → deployment → maintenance. Check items off as done.

## Phase 0 — Prerequisites

- [ ] Create dedicated Telegram bot via @BotFather; record token and chat ID
- [ ] Confirm SSH + Docker + Compose on OCI Ampere A1 instance
- [ ] Init repo, `.gitignore` (`.env`, `__pycache__`, `.venv`), `.env.example`
- [ ] Project skeleton: `app/`, `sql/`, `tests/`, `scripts/`, `requirements.txt`

**Done when:** repo skeleton exists and bot token works via a manual `curl` to `sendMessage`.

## Phase 1 — Schema & connectivity (Milestone 1)

- [ ] Add `postgres:16-alpine` service + `pgdata` volume to `docker-compose.yml`
- [ ] `sql/init.sql` creating `poll_runs`, `free_model_status`, `free_model_events` (mounted to `/docker-entrypoint-initdb.d`, or tiny migration on first start)
- [ ] `db.py` connection helper reading `DATABASE_URL`

**Done when:** `docker compose up postgres` yields three tables; app can connect and run `SELECT 1`.

## Phase 2 — Core poll/diff logic (Milestone 2)

- [ ] `fetcher.py`: GET `/api/v1/models`, timeout + retry, parse JSON
- [ ] Filter ids ending in `:free`
- [ ] `diff.py`: pure function `(previous_free, current_free, all_ids) -> newly_free, became_paid, removed`
- [ ] Unit tests: no change, added, dropped (paid vs removed), first run (empty DB), empty/garbage API response

**Done when:** `pytest` green; fetcher returns a real free set against live API.

## Phase 3 — Persistence layer (Milestone 3)

- [ ] Insert `poll_runs` (ok and error variants)
- [ ] Upsert `free_model_status` (set `first_seen_free_at` once, bump `last_seen_free_at` / `last_checked_at`)
- [ ] Append `free_model_events` linked to `run_id`
- [ ] Single transaction per run
- [ ] First-run behavior decided: seed baseline without flooding alerts (recommended: record events but send one summary, or skip alert)

**Done when:** running one poll twice against live API yields two `poll_runs`, correct status rows, zero events on the second run.

## Phase 4 — Telegram integration (Milestone 4)

- [ ] `notifier.py`: send message via Bot API
- [ ] Message format per plan (timestamp UTC, ✅ newly free, ❌ no longer free)
- [ ] Fire only on non-empty diff
- [ ] Send failure logged, never raises past the run; DB write already committed

**Done when:** simulated diff produces a Telegram message; broken token logs an error and run still persists.

## Phase 5 — Scheduler + Dockerfile (Milestone 5)

- [ ] `main.py`: run one cycle at startup, then every `POLL_INTERVAL_HOURS`
- [ ] Top-level exception handling: a failed cycle logs and writes `status='error'`; loop continues
- [ ] Structured stdout logs (status, total, free count, diff sizes)
- [ ] `Dockerfile` on `python:3.12-slim`, non-root user, arm64-compatible deps
- [ ] Add `tracker` service to compose: `restart: unless-stopped`, `depends_on: postgres` (with healthcheck condition)

**Done when:** `docker compose up --build` locally runs a cycle, persists, and survives a killed Postgres/restart.

## Phase 6 — Deploy to OCI (Milestone 6)

- [ ] Copy repo + `.env` to instance (never commit `.env`)
- [ ] `docker compose up -d --build` on the Ampere A1
- [ ] Verify first real run: `docker compose logs tracker`, rows in `poll_runs`
- [ ] Verify second scheduled run (12h later) and a real Telegram alert on change
- [ ] Reboot test: containers return automatically; data intact in `pgdata`

**Done when:** two consecutive real runs succeed unattended.

## Phase 7 — Query script (Milestone 7)

- [ ] `scripts/days_free.py <model_id>`: compute total days free from `free_model_events` (sum `became_free` → next `became_paid`/`removed`; open interval runs to now)
- [ ] Handle multiple free windows per model
- [ ] Document usage in README

**Done when:** script output matches hand-computed result for a model with at least one full window.

## Phase 8 — Maintenance (ongoing)

Routine:

- [ ] Weekly glance at `docker compose logs --tail 200 tracker` and latest `poll_runs` for `status='error'`
- [ ] Monthly: `docker compose pull && docker compose up -d --build` for base image security updates
- [ ] Confirm Postgres volume size stays small (`docker system df -v`)

Backups:

- [ ] Periodic `pg_dump` to a file off the instance (cron on host): `docker compose exec -T postgres pg_dump -U tracker openrouter_tracker > backup.sql`
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
