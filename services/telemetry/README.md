# telemetry — Postgres-backed log and metric store

Ingestion service for structured logs and request metrics from service-a and service-b.

## Setup

```bash
cd services/telemetry
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Postgres must be running (from repo root):

```bash
docker compose up -d postgres
```

Run migrations:

```bash
cd services/telemetry
source .venv/bin/activate
alembic upgrade head
```

## Run locally

```bash
uvicorn main:app --host 0.0.0.0 --port 8002 --reload
```

Or use `./scripts/start.sh` from the repo root (starts Postgres, migrates, then all services).

## Endpoints

- `GET /health` — DB connectivity + row counts + open incident count
- `POST /ingest/logs` — `{service, timestamp, level, message, trace_id}`
- `POST /ingest/metrics` — `{service, timestamp, metric_name, value}`
- `GET /incidents` — list all incidents (newest first)
- `GET /incidents/{id}` — single incident
- `GET /incidents/{id}/evidence` — numbered logs + metrics for incident window
- `POST /incidents/{id}/analyze` — Gemini RCA (requires `GEMINI_API_KEY`)

## Gemini RCA

```bash
export GEMINI_API_KEY=your-key-here
./scripts/start.sh telemetry
curl -X POST http://127.0.0.1:8002/incidents/2/analyze | python3 -m json.tool
```

Also accepts `GOOGLE_API_KEY`. Optional `GEMINI_MODEL` (default `gemini-2.0-flash`).

## Anomaly detection

A **background asyncio task** runs every 10 seconds (configurable). It is **not** a polling
endpoint — see tradeoffs below.

For each monitored service (`service-a`, `service-b`) and metric (`error_rate`, `latency_ms`):

1. Load metrics from the last **N minutes** (default 5).
2. Compute mean + stddev on the baseline window **excluding the most recent 30 seconds**.
3. Flag an anomaly if the latest value exceeds `mean + 3 * stddev`.
4. On first anomaly → insert `incidents` row with `status='open'`.
5. When values stay normal for **60 continuous seconds** → set `ended_at`, `status='resolved'`.

### Background task vs polling endpoint

| | Background task (chosen) | Polling endpoint |
|---|---|---|
| **Runs automatically** | Yes, every 10s while telemetry is up | Only when something calls it |
| **Ops complexity** | None — built into the service | Needs cron, k8s CronJob, or manual curls |
| **Testing** | Watch `GET /incidents` after injecting failures | Easy one-shot: `curl POST /admin/detect` |
| **Multi-instance** | Each replica runs its own loop (needs leader election later) | Same problem unless external scheduler |
| **Process coupling** | Stops when telemetry stops | Detection pauses if nobody polls |

We use a background task because incident detection should be autonomous during local dev and
Phase 1 verification — you inject a failure, wait ~10–40s, and check `GET /incidents`.

**Important:** the baseline window excludes the most recent 30 seconds. To detect a spike:

1. Generate normal traffic for at least 30 seconds (e.g. 20+ `POST /request` calls).
2. **Wait 30+ seconds** so those samples land in the baseline (not the recent window).
3. Inject failure and hammer the gateway — spike samples go into the **recent window**.
4. Within ~10s the detector compares `recent_mean` vs baseline and opens an incident.

If you spike immediately without a warmed baseline, logs will show:
`skip=insufficient baseline (N samples, need 3) — normal traffic must be older than 30s`

Tail the detector: `grep anomaly .run/telemetry.log` (runs every 10s, logs every service/metric).

## Verify incidents

```bash
# Generate baseline traffic
for i in $(seq 1 20); do curl -s -X POST http://127.0.0.1:8000/request > /dev/null; done

# Inject failure
curl -X POST http://127.0.0.1:8001/admin/inject \
  -H "Content-Type: application/json" \
  -d '{"mode":"error","magnitude":100}'

# Hammer gateway to spike error_rate
for i in $(seq 1 30); do curl -s -o /dev/null -X POST http://127.0.0.1:8000/request; done

# Check incidents (~10–40s after spike)
curl http://127.0.0.1:8002/incidents | python3 -m json.tool

# Clear failure and wait 60s+ with normal traffic
curl -X POST http://127.0.0.1:8001/admin/inject \
  -H "Content-Type: application/json" \
  -d '{"mode":"none","magnitude":0}'
for i in $(seq 1 20); do curl -s -X POST http://127.0.0.1:8000/request > /dev/null; sleep 3; done

curl http://127.0.0.1:8002/incidents | python3 -m json.tool
```

## Environment

| Variable | Default |
|----------|---------|
| `DATABASE_URL` | `postgresql://telemetry:telemetry@127.0.0.1:5432/telemetry` |
| `ANOMALY_CHECK_INTERVAL_SECONDS` | `10` |
| `ANOMALY_WINDOW_MINUTES` | `5` |
| `ANOMALY_EXCLUDE_RECENT_SECONDS` | `30` |
| `ANOMALY_RECOVERY_SECONDS` | `60` |
| `ANOMALY_STD_DEV_MULTIPLIER` | `3` |
| `ANOMALY_MIN_BASELINE_SAMPLES` | `3` |
