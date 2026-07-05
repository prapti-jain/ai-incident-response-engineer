# AI Incident Response Engineer

**Project Report**

---

## 1. Title Page Information

| Field | Details |
|-------|---------|
| **Project Title** | AI Incident Response Engineer |
| **Author** | Prapti Jain |
| **Repository** | [github.com/prapti-jain/ai-incident-response-engineer](https://github.com/prapti-jain/ai-incident-response-engineer) |
| **Live Frontend** | [ai-incident-response-engineer.vercel.app](https://ai-incident-response-engineer.vercel.app) |
| **Live Telemetry Health** | [incident-telemetry.onrender.com/health](https://incident-telemetry.onrender.com/health) |
| **Date** | June–July 2026 |

### Tech Stack Summary

Next.js 16 · React 19 · Tailwind CSS 4 · Recharts 3 · FastAPI · SQLAlchemy 2 · Alembic · PostgreSQL (Neon) · Google Gemini (`google-genai`) · Vercel · Render

---

## 2. Abstract

AI Incident Response Engineer is a full-stack observability and incident-response platform that demonstrates how large language models can assist on-call engineers without sacrificing auditability. The system runs two victim microservices (a gateway and a worker) that emit **real structured logs and metrics** into a PostgreSQL telemetry store—not synthetic or hard-coded incident data. A statistical anomaly detector monitors `error_rate` and `latency_ms` across both services and automatically opens and resolves incidents in a dedicated `incidents` table.

When an incident is investigated, the telemetry service retrieves time-windowed evidence from Postgres, assigns each log line and metric point a stable numeric ID, and sends the bundle to Google Gemini with strict instructions to cite only those IDs. Model output is validated with Pydantic schemas and cross-checked against the evidence index before being persisted as `incidents.rca_report`. A second Gemini pass generates a structured postmortem with timeline timestamps and peak metric values verified against computed database aggregates, stored in `incidents.postmortem`. A Next.js dashboard provides live metrics, log streaming, fault injection, and an incidents UI with evidence expansion and Markdown export.

The project's primary technical contribution is **grounded RCA over real telemetry**: every hypothesis returned by the LLM must reference verifiable evidence rows, preventing hallucinated root causes and making AI-assisted incident response suitable for review in academic or professional settings.

---

## 3. Introduction

### 3.1 Problem Statement

Production incident response is painful for several overlapping reasons. When an alert fires, engineers must manually correlate logs, metrics, and deployment history across multiple systems. Writing a post-incident review (postmortem) is time-consuming and often delayed—sometimes skipped entirely under operational pressure. Generic LLM summaries of incidents are tempting but dangerous: models can produce plausible-sounding root causes with no connection to actual telemetry, making them unsuitable for blameless postmortems or audit trails.

Real engineering teams need tooling that (a) captures structured observability data automatically, (b) detects anomalies without requiring a pre-trained ML pipeline, and (c) uses AI to accelerate analysis while keeping every claim traceable to source data.

### 3.2 Project Objectives

1. Build a realistic multi-service workload that generates authentic logs and metrics under normal and failure conditions.
2. Ingest telemetry into PostgreSQL and detect anomalies using interpretable statistical methods.
3. Implement evidence retrieval with stable IDs and LLM grounding so RCA output is verifiable.
4. Generate structured postmortems with validated timestamps and metric peaks.
5. Provide a live dashboard for demonstration, fault injection, and incident investigation.
6. Deploy the full stack to production (Vercel + Render + Neon) as a portfolio-ready system.

### 3.3 Scope

**In scope:**

- Three FastAPI backend services (telemetry, service-a gateway, service-b worker)
- PostgreSQL schema with Alembic migrations
- Statistical anomaly detection with open/resolved incident lifecycle
- Gemini-powered RCA and postmortem generation with Pydantic validation
- Next.js frontend with dashboard, incidents list, and incident detail pages
- Deployment via Render Blueprint (`render.yaml`) and Vercel

**Out of scope:**

- Real-time streaming ingestion (logs/metrics are HTTP-posted; dashboard polls)
- ML-based anomaly detection or vector search over logs
- PagerDuty, Slack, or other external alerting integrations
- Authentication/authorization on admin endpoints
- Automated test suites (verification was manual during development)

---

## 4. System Architecture

### 4.1 High-Level Overview

The system consists of four deployable components plus a managed database:

| Component | Role | Deployment |
|-----------|------|------------|
| **Next.js frontend** | Dashboard, fault injection UI, incidents browser | Vercel |
| **Telemetry service** | Ingest, storage, anomaly detection, RCA, postmortem | Render (`incident-telemetry`) |
| **service-a** | HTTP gateway; proxies requests to service-b | Render (`incident-service-a`) |
| **service-b** | Worker with injectable failure modes | Render (`incident-service-b`) |
| **PostgreSQL** | Persistent store for logs, metrics, incidents | Neon |

### 4.2 Architecture Diagram

The repository README contains a Mermaid diagram (`README.md`, Architecture section) depicting the following flow:

```
Browser → Next.js (Vercel)
       → Telemetry (Render) → Postgres/Neon
       → service-a → service-b
service-a/b → /ingest/logs, /ingest/metrics → Neon
Neon → Anomaly detector → incidents table
incidents → Gemini RCA → incidents.rca_report
incidents → Gemini postmortem → incidents.postmortem
```

Inter-service URLs on Render are wired via Blueprint `fromService` references to `RENDER_EXTERNAL_URL` (e.g., `TELEMETRY_URL`, `WORKER_URL`).

### 4.3 Data Flow Walkthrough

1. **Request path** — The frontend (or a client) calls `POST /request` on service-a. Service-a forwards a `GET` to service-b's `/work` endpoint, propagating an `X-Trace-Id` header for correlation.

2. **Telemetry ingestion** — Both service-a and service-b middleware call `log_event()` on every request. This emits JSON to stdout and asynchronously POSTs to telemetry's `/ingest/logs`. When `emit_metrics=True`, a rolling 100-request window computes `error_rate` (percentage) and `latency_ms`, POSTed to `/ingest/metrics`.

3. **Storage** — Telemetry persists logs to the `logs` table and metrics to the `metrics` table in Neon/Postgres.

4. **Anomaly detection** — A background asyncio task runs every 10 seconds (configurable). For each monitored service/metric pair, it compares a 5-minute baseline window (excluding the most recent 30 seconds) against recent samples using a 3-sigma threshold. Anomalies open incidents; sustained normal readings for 60 seconds resolve them.

5. **Evidence retrieval** — On RCA or postmortem request, telemetry queries logs and metrics within a padded time window around the incident, sorts chronologically, assigns stable IDs (1…N), and optionally samples to 150 items.

6. **RCA** — Evidence is formatted and sent to Gemini (`gemini-2.5-flash` by default) with JSON schema enforcement. Up to three ranked causes with `evidence_ids` are validated and joined back to source rows.

7. **Postmortem** — Using the stored RCA, evidence, computed metric peaks, and a curated list of timeline-eligible timestamps, Gemini generates a structured postmortem. Timeline timestamps and peak values are validated before persistence.

8. **Frontend display** — The dashboard polls recent metrics/logs. The incidents UI lists detected incidents and provides analyze, evidence expand, postmortem generate, and Markdown export actions.

---

## 5. Technology Stack

### 5.1 Frontend

| Technology | Version (approx.) | Purpose |
|------------|-------------------|---------|
| Next.js | 16.2.9 | App Router, SSR/client components |
| React | 19.2.4 | UI rendering |
| Tailwind CSS | 4.x | Styling (dark ops-dashboard theme) |
| Recharts | 3.9.x | Error rate and latency line charts |
| TypeScript | 5.x | Type-safe frontend code |

Environment variables (`NEXT_PUBLIC_TELEMETRY_URL`, `NEXT_PUBLIC_SERVICE_A_URL`, `NEXT_PUBLIC_SERVICE_B_URL`) configure backend URLs at build time.

### 5.2 Backend

| Technology | Version (approx.) | Purpose |
|------------|-------------------|---------|
| FastAPI | ≥0.115.0 | HTTP API for all three services |
| Uvicorn | ≥0.32.0 | ASGI server |
| SQLAlchemy | ≥2.0.36 | ORM and query layer |
| Alembic | ≥1.14.0 | Schema migrations |
| psycopg2-binary | ≥2.9.10 | PostgreSQL driver |
| httpx | ≥0.28.0 | Inter-service HTTP and telemetry POST |
| python-dotenv | ≥1.0.0 | Local `.env` loading for Gemini key |

### 5.3 Database

- **PostgreSQL** via Neon in production
- Local development: Docker Compose or Homebrew Postgres at `postgresql://telemetry:telemetry@127.0.0.1:5432/telemetry`
- JSONB columns on `incidents` for `rca_report` and `postmortem`

### 5.4 AI / LLM

| Component | Details |
|-----------|---------|
| Provider | Google Gemini via `google-genai` SDK (≥1.0.0) |
| Default model | `gemini-2.5-flash` (override via `GEMINI_MODEL`) |
| Output mode | `response_mime_type="application/json"` with `response_schema` set to Pydantic models |
| Temperature | 0.2 for both RCA and postmortem |
| Retry | Up to 2 attempts; validation errors fed back into prompt on retry |

### 5.5 Deployment

| Platform | Service |
|----------|---------|
| Vercel | Next.js frontend |
| Render (free tier) | `incident-telemetry`, `incident-service-a`, `incident-service-b` |
| Neon | Managed PostgreSQL (`DATABASE_URL` set manually in Render dashboard) |

Render Blueprint: `render.yaml` at repo root with `rootDir` per service, Alembic migrations on telemetry startup, and `fromService` URL wiring.

### 5.6 Development Tools

- Python virtual environments per service (`.venv`)
- `scripts/start.sh` — bootstrap DB, run migrations, start all backends
- `scripts/stop.sh` — stop running services
- Structured JSON logging to stdout from service-a/b
- PID files and logs under `.run/` directory

---

## 6. Module-Wise Description

### 6a. Victim System (service-a + service-b + Fault Injection)

**service-a (gateway)** exposes `POST /request`, which proxies to service-b's worker URL. The worker URL is read from the `WORKER_URL` environment variable (default `http://127.0.0.1:8001/work` for local dev; on Render, wired via Blueprint `fromService`). Each request receives or generates an `X-Trace-Id` for distributed tracing correlation.

**service-b (worker)** exposes `GET /work` (the actual work endpoint) and `POST /admin/inject` (fault injection). The inject endpoint accepts `{ mode, magnitude }` where `mode` is one of `latency`, `error`, `cpu_spike`, or `none`:

| Mode | Behavior |
|------|----------|
| `latency` | `time.sleep(magnitude / 1000)` seconds |
| `cpu_spike` | Busy-loop for `magnitude` milliseconds |
| `error` | Random failure with probability `min(magnitude, 100)%` |
| `none` | Clears injection |

**Design rationale:** Separating gateway and worker mimics a real microservice topology. Injectable failures produce measurable latency spikes and error rates in telemetry without modifying application code at runtime. The frontend's Fault Injection panel calls `/admin/inject` directly on service-b.

### 6b. Telemetry Pipeline

**Structured logging** (`logging_utils.py` in service-a/b) writes JSON log records to stdout and POSTs them to `{TELEMETRY_URL}/ingest/logs` with fields: `service`, `timestamp`, `level`, `message`, `trace_id`.

**Metrics emission** occurs when `emit_metrics=True` in middleware. Each request appends to a `deque(maxlen=100)` error boolean window, then emits:
- `latency_ms` — request duration in milliseconds
- `error_rate` — `(errors / window_size) * 100` as a percentage

**Postgres schema** stores raw ingested data in `logs` and `metrics` tables (see Section 7).

**Design rationale:** Fire-and-forget HTTP ingestion keeps victim services decoupled from telemetry storage. Failures in telemetry POST are silently swallowed so injected errors in service-b do not cascade. The rolling error window produces a realistic lag in error_rate recovery (see Section 10).

### 6c. Anomaly Detection Engine

Implemented in `anomaly_detector.py` as a periodic background task in telemetry's FastAPI lifespan.

**Algorithm:**

1. For each `(service, metric_name)` pair in the monitored set (`service-a`, `service-b` × `error_rate`, `latency_ms`):
2. Fetch **baseline** metric values from the last 5 minutes, excluding the most recent 30 seconds.
3. Fetch **recent** values from the last 30 seconds.
4. Compute baseline mean and standard deviation; threshold = mean + 3 × stdev.
5. If stdev is 0, flag anomalous when recent_mean > mean.
6. Require ≥3 baseline samples and ≥1 recent sample; otherwise skip with reason logged.

**Incident lifecycle:**

- **Open:** First anomalous reading creates an `Incident` with `status="open"`, `trigger_type="{service}:{metric_name}"`.
- **Recovering:** When readings return to normal, a 60-second recovery timer starts.
- **Resolved:** After 60 continuous seconds of normal readings, `ended_at` is set and `status="resolved"`.

In-memory trackers sync from open incidents in the DB on startup via `sync_trackers_from_db()`.

**Design rationale:** Statistical 3-sigma detection is interpretable, requires no training data, and produces log output explaining skip reasons (e.g., insufficient baseline). The 30-second exclusion prevents the anomaly itself from polluting the baseline. The recovery timer avoids flapping incidents on brief spikes.

### 6d. Evidence Retrieval Layer

Implemented in `evidence.py`.

**Window computation:** `incident.started_at ± 2 minutes` (padding), extended to `incident.ended_at` if later.

**Collection:** Queries `logs` and `metrics` for `service-a` and `service-b` within the window, sorted by `(timestamp, source, service, row_id)`.

**Stable ID assignment:** Sequential IDs (1…N) assigned after sorting—not database primary keys—so the LLM sees a compact, ordered list.

**Sampling:** If total items exceed 150 (`EVIDENCE_MAX_ITEMS`), evenly spaced indices are selected via `_even_sample_indices()`. The response includes `sampled`, `total_items`, `returned_items`, and `omitted_items` metadata.

**Design rationale:** Time-windowed queries mirror how SREs investigate incidents. Stable sequential IDs simplify LLM citation. Sampling bounds prompt size and API cost while preserving temporal coverage.

### 6e. RCA Agent

Implemented in `rca.py`.

**Flow:**

1. Build evidence dict via `build_evidence()`.
2. Format evidence as numbered lines for the prompt.
3. Call Gemini with system prompt requiring citation of evidence IDs only.
4. Parse response into `RcaReport` Pydantic model (1–3 causes, unique ranks, non-empty `evidence_ids`).
5. Validate all cited IDs exist in the evidence set.
6. On validation failure, retry once with the error message appended to the prompt.
7. Join cited IDs back to full evidence rows via `join_cited_evidence()`.
8. Persist JSON to `incidents.rca_report`.

**API endpoint:** `POST /incidents/{id}/analyze`

**Design rationale:** JSON schema mode (`response_schema=RcaReport`) constrains output structure. Post-generation ID validation catches hallucinated citations even when schema validation passes. The retry loop handles occasional model formatting mistakes without infinite loops.

### 6f. Postmortem Generator

Implemented in `postmortem.py`.

**Flow:**

1. Require or auto-generate RCA report (`_ensure_rca_report()` in `main.py`).
2. Compute metric peaks via SQL `MAX(value)` grouped by service/metric in the evidence window.
3. Build timeline-eligible events: incident open/close timestamps, error-level logs, and metric points matching peak values.
4. Send RCA, evidence, peaks, and timeline candidates to Gemini with strict rules:
   - Timeline timestamps must come from the eligible list only.
   - `impact.peak_error_rate` and `impact.peak_latency_ms` must match computed peaks exactly (±0.01 tolerance).
5. Validate with Pydantic; validate timeline timestamps and peak values programmatically.
6. Retry once on validation failure.
7. Persist JSON to `incidents.postmortem`.

**Output schema:** `summary`, `timeline[]`, `root_cause`, `impact`, `action_items[]`

**Design rationale:** Separating RCA (hypothesis ranking) from postmortem (narrative document) allows each step to have tailored prompts and validation. Hard-checking peak metrics and timestamps prevents the model from inventing impact numbers—a common failure mode in LLM-generated incident reports.

### 6g. Frontend Dashboard

Implemented in `components/Dashboard.tsx` and related components.

**Features:**

- **Health indicators** — Polls `/health` on all three services every 10 seconds; green/red status dots.
- **Fault Injection panel** — Buttons for Latency (500 ms), Error (100%), CPU spike (200 ms), Clear; calls `POST /admin/inject` on service-b.
- **Metrics charts** — Polls `GET /metrics/recent?minutes=15` every 3 seconds; Recharts line charts for error_rate and latency_ms per service.
- **Log stream** — Polls `GET /logs/recent?limit=100` every 2 seconds; scrollable log display.

**Design rationale:** Polling (rather than WebSockets) keeps the frontend simple and sufficient for a demo. The dark theme and monospace accents target an ops-dashboard aesthetic appropriate for incident tooling.

### 6h. Incidents UI

**Incidents list** (`/incidents`) — Polls `GET /incidents` every 5 seconds. Table shows ID, trigger type, status badge, start time, and duration. Full row click navigates to detail page.

**Incident detail** (`/incidents/[id]`) — Shows metadata, RCA section with "Analyze" button, expandable evidence per cause, postmortem section with "Generate" button, and Markdown export (`incident-{id}-postmortem.md` download via `postmortemToMarkdown()`).

**Evidence panel** (`EvidencePanel.tsx`) — Renders individual evidence items with source, timestamp, service, and content; supports expanding cited IDs from RCA causes.

---

## 7. Database Schema

Migration: `alembic/versions/001_initial_schema.py` (revision `001`).

### 7.1 Table: `logs`

| Column | Type | Constraints | Index |
|--------|------|-------------|-------|
| `id` | INTEGER | PRIMARY KEY, autoincrement | — |
| `service` | VARCHAR(64) | NOT NULL | `ix_logs_service` |
| `timestamp` | TIMESTAMPTZ | NOT NULL | `ix_logs_timestamp` |
| `level` | VARCHAR(16) | NOT NULL | — |
| `message` | TEXT | NOT NULL | — |
| `trace_id` | VARCHAR(64) | NOT NULL | `ix_logs_trace_id` |

**Purpose:** Stores structured log lines from service-a and service-b. Indexed on `service`, `timestamp`, and `trace_id` for time-window queries and trace correlation.

### 7.2 Table: `metrics`

| Column | Type | Constraints | Index |
|--------|------|-------------|-------|
| `id` | INTEGER | PRIMARY KEY, autoincrement | — |
| `service` | VARCHAR(64) | NOT NULL | `ix_metrics_service` |
| `timestamp` | TIMESTAMPTZ | NOT NULL | `ix_metrics_timestamp` |
| `metric_name` | VARCHAR(64) | NOT NULL | `ix_metrics_metric_name` |
| `value` | FLOAT | NOT NULL | — |

**Purpose:** Stores time-series metric points (`latency_ms`, `error_rate`). Indexed for anomaly detection window queries and peak aggregation.

### 7.3 Table: `incidents`

| Column | Type | Constraints | Index |
|--------|------|-------------|-------|
| `id` | INTEGER | PRIMARY KEY, autoincrement | — |
| `started_at` | TIMESTAMPTZ | NOT NULL | — |
| `ended_at` | TIMESTAMPTZ | NULLABLE | — |
| `trigger_type` | VARCHAR(64) | NOT NULL | — |
| `status` | VARCHAR(32) | NOT NULL | — |
| `rca_report` | JSONB | NULLABLE | — |
| `postmortem` | JSONB | NULLABLE | — |

**Purpose:** Tracks detected incidents and stores AI-generated artifacts. `trigger_type` format: `{service}:{metric_name}` (e.g., `service-b:error_rate`). `status` values: `open`, `resolved`. JSONB columns allow flexible schema evolution for RCA/postmortem payloads without additional migrations.

### 7.4 Design Decisions

- **Separate logs and metrics tables** rather than a unified events table—simplifies typed queries and aligns with how observability backends typically partition data.
- **JSONB for AI outputs**—RCA and postmortem schemas may evolve; storing validated JSON avoids rigid column-per-field migrations.
- **No foreign keys from incidents to logs/metrics**—evidence is retrieved by time window, not by incident ID, reflecting that incidents are derived views over telemetry rather than owning the raw data.

---

## 8. API Documentation

### 8.1 Telemetry Service (`incident-telemetry`)

Base URL (production): `https://incident-telemetry.onrender.com`

| Method | Path | Purpose | Request | Response |
|--------|------|---------|---------|----------|
| GET | `/health` | Health check + DB stats | — | `{ status, service, log_count, metric_count, open_incidents, anomaly_check_interval_seconds, anomaly_task_running, anomaly_cycles_completed, gemini_api_key_configured }` |
| POST | `/ingest/logs` | Ingest log entry | `{ service, timestamp, level, message, trace_id }` | `{ id }` (201) |
| POST | `/ingest/metrics` | Ingest metric point | `{ service, timestamp, metric_name, value }` | `{ id }` (201) |
| GET | `/metrics/recent` | Recent metrics for dashboard | Query: `minutes` (1–120, default 15) | `{ window_minutes, window_start, window_end, items[] }` |
| GET | `/logs/recent` | Recent logs for dashboard | Query: `limit` (1–500, default 100) | `{ limit, items[] }` |
| GET | `/incidents` | List all incidents | — | `IncidentOut[]` |
| GET | `/incidents/{id}` | Get single incident | — | `IncidentOut` |
| GET | `/incidents/{id}/evidence` | Evidence bundle for incident | — | `EvidenceResponse` |
| POST | `/incidents/{id}/analyze` | Run Gemini RCA | — | `AnalyzeResponse` |
| POST | `/incidents/{id}/postmortem` | Generate postmortem (auto-RCA if missing) | — | `PostmortemResponse` |

**Key response shapes:**

```json
// IncidentOut
{ "id", "started_at", "ended_at", "trigger_type", "status", "rca_report", "postmortem" }

// AnalyzeResponse
{ "incident_id", "trigger_type", "rca_report", "causes", "all_cited_evidence", "evidence_summary" }

// PostmortemResponse
{ "incident_id", "trigger_type", "postmortem", "metric_peaks" }
```

**Error handling:** Gemini failures return structured JSON errors via `AnalyzeError` (503 for missing API key, 502 for validation/SDK errors, 429 mapping for quota exceeded).

### 8.2 Service-A Gateway (`incident-service-a`)

Base URL (production): `https://incident-service-a.onrender.com`

| Method | Path | Purpose | Request | Response |
|--------|------|---------|---------|----------|
| GET | `/health` | Health check | — | `{ status: "ok", service: "service-a" }` |
| POST | `/request` | Proxy to service-b worker | — | `{ trace_id, result }` or error JSON |

### 8.3 Service-B Worker (`incident-service-b`)

Base URL (production): `https://incident-service-b.onrender.com`

| Method | Path | Purpose | Request | Response |
|--------|------|---------|---------|----------|
| GET | `/health` | Health check | — | `{ status: "ok", service: "service-b" }` |
| GET | `/work` | Execute work (applies failure mode) | Header: `X-Trace-Id` | `{ status, service, trace_id, failure_mode, magnitude }` or 500 |
| POST | `/admin/inject` | Set failure injection mode | `{ mode, magnitude }` | `{ mode, magnitude }` |

**Inject modes:** `latency`, `error`, `cpu_spike`, `none` (see Section 6a).

---

## 9. Key Technical Decisions & Design Rationale

### 9.1 Statistical Detection Instead of ML

Machine learning anomaly detection requires training data, model maintenance, and opaque decision boundaries. For a demo system with injectable, known failure modes, a 3-sigma rule over rolling windows is sufficient, fully explainable, and produces log output showing baseline counts, means, thresholds, and skip reasons. This aligns with how many teams start before investing in ML-based observability.

### 9.2 Evidence Grounding Instead of Open-Ended LLM Prompting

Asking an LLM "what caused this incident?" without constraints produces fluent but unverifiable answers. Numbering evidence items and requiring `evidence_ids` citations creates a machine-checkable contract. Invalid citations are rejected before the response reaches the user.

### 9.3 Pydantic Validation on LLM Outputs

Gemini's JSON schema mode reduces formatting errors, but programmatic validation (unique ranks, chronological timeline, peak value matching, timestamp whitelist) catches semantic errors schema enforcement alone cannot. The two-attempt retry with error feedback improves success rate without masking persistent failures.

### 9.4 Separate Services Instead of a Monolith

Three services mirror a realistic deployment topology (gateway, worker, observability plane). Separate Render services allow independent scaling, failure isolation, and demonstrate inter-service telemetry ingestion—the gateway and worker both emit logs/metrics independently.

### 9.5 Neon + Render + Vercel Deployment

| Choice | Rationale |
|--------|-----------|
| **Neon** | Serverless Postgres with generous free tier; external DB works with Render's `sync: false` DATABASE_URL pattern (Render's `fromDatabase` requires Render Postgres) |
| **Render** | Simple Python web service deployment with Blueprint IaC; free tier sufficient for demo |
| **Vercel** | Optimized Next.js hosting with automatic preview deployments |

Monorepo `rootDir` in `render.yaml` maps each service to its subdirectory without splitting the repository.

---

## 10. Challenges Faced & Solutions

### 10.1 CORS and Private Network Access (localhost vs 127.0.0.1)

**Problem:** Browser requests from `http://localhost:3000` to `http://127.0.0.1:8002` triggered Chrome's Private Network Access restrictions and CORS mismatches (different origins).

**Solution:** Standardized frontend env vars to use `localhost` URLs. Added `CORSMiddleware` plus a custom `PrivateNetworkAccessMiddleware` setting `Access-Control-Allow-Private-Network: true` on all three FastAPI services. For production, `CORS_ORIGINS` must include the Vercel deployment URL.

### 10.2 Alembic Migrations on Cold-Start Deployment

**Problem:** Telemetry crashed on Render startup with `relation "incidents" does not exist` because Neon was empty and migrations had never run.

**Solution:** Added `run_migrations()` calling `alembic upgrade head` at the start of the FastAPI lifespan handler, before anomaly detection or any DB queries. Every deploy automatically applies pending migrations.

### 10.3 Anomaly Detection Baseline Warmup

**Problem:** Detection skips with "insufficient baseline" until enough metric samples exist that are older than 30 seconds.

**Solution:** Documented as expected behavior. Normal traffic must run for ~30+ seconds before the baseline window has qualifying samples (minimum 3). The dashboard empty state directs users to generate traffic via fault injection.

### 10.4 error_rate Recovery Window

**Problem:** After clearing an error injection, `error_rate` remains elevated because it is computed over a rolling 100-request window (`METRICS_WINDOW_SIZE`), and incident resolution requires 60 seconds of normal readings after the metric returns to baseline.

**Solution:** Documented as a known limitation. Full recovery requires approximately 100 clean requests to flush the window plus the 60-second recovery timer (~180 requests total in practice).

### 10.5 Process Lifecycle Management

**Problem:** Backend processes started by automated agents died when the agent session ended.

**Solution:** `scripts/start.sh` uses `nohup` with PID files under `.run/` and health-check polling. Users run backends in their own terminal session. Logs written to `.run/{service}.log`.

### 10.6 Render Root Directory Configuration for Monorepo

**Problem:** Single-repo layout with three Python services required correct build/start paths on Render.

**Solution:** `render.yaml` Blueprint with per-service `rootDir` (`services/telemetry`, `services/service-a`, `services/service-b`), shared build pattern (`pip install -r requirements.txt`), and `fromService` env wiring for inter-service URLs.

### 10.7 Vercel Frontend Configuration

**Problem:** Deployed frontend showed "Failed to fetch" because `NEXT_PUBLIC_*` URLs defaulted to localhost and CORS did not allow the Vercel origin.

**Solution:** Set `NEXT_PUBLIC_TELEMETRY_URL`, `NEXT_PUBLIC_SERVICE_A_URL`, and `NEXT_PUBLIC_SERVICE_B_URL` in Vercel environment variables pointing to Render URLs. Set `CORS_ORIGINS` on all Render services to include the Vercel production URL. Redeploy both frontend and backends after changes.

---

## 11. Testing & Verification

### 11.1 Manual curl-Based API Verification

Each service exposes `GET /health` verified via curl during local startup (`scripts/start.sh` runs health checks on ports 8000, 8001, 8002). Ingest endpoints tested with sample JSON payloads. Gateway flow verified with `curl -X POST http://127.0.0.1:8000/request`.

### 11.2 SQL Queries for Telemetry Ingestion

Manual verification via Postgres queries:

```sql
SELECT COUNT(*) FROM logs;
SELECT COUNT(*) FROM metrics;
SELECT service, metric_name, AVG(value) FROM metrics GROUP BY 1, 2;
SELECT * FROM incidents ORDER BY started_at DESC;
```

Used to confirm ingest pipeline populated tables after fault injection and gateway requests.

### 11.3 Evidence ID Cross-Checking

After `POST /incidents/{id}/analyze`, cited `evidence_ids` in the response were compared against `GET /incidents/{id}/evidence` items. Validation logic in `rca.py` (`_validate_cited_ids`) was verified by inspecting 502 responses when the model cited invalid IDs (observed during Gemini quota errors and early development).

### 11.4 End-to-End Production Testing

On the deployed system:

1. Open Vercel dashboard; confirm health dots turn green after Render cold start.
2. Click Fault Injection → Error (100%).
3. Generate traffic (fault injection triggers service-b; metrics appear after requests flow through service-a).
4. Wait for anomaly detection to open an incident (~10–30 seconds after sufficient baseline + anomalous readings).
5. Navigate to Incidents → click incident → Analyze RCA → expand evidence.
6. Generate postmortem → export Markdown.

Production health endpoint verified: `https://incident-telemetry.onrender.com/health` returns 200 with DB connectivity and row counts.

---

## 12. Results & Screenshots

> Placeholder sections for documentation submission. Insert screenshots at the paths indicated.

### 12.1 Live Dashboard

**[Screenshot placeholder: Live dashboard]**

*Expected content:* Metrics charts (error rate, latency), log stream, fault injection panel, green health indicators. URL: `https://ai-incident-response-engineer.vercel.app`

### 12.2 Incident List Page

**[Screenshot placeholder: Incidents list]**

*Expected content:* Table with incident ID, trigger type (e.g., `service-b:error_rate`), status badge (open/resolved), timestamps. URL: `/incidents`

### 12.3 RCA Detail Page with Evidence Citations

**[Screenshot placeholder: RCA with evidence]**

*Expected content:* Ranked root causes with expandable evidence items showing log lines and metric values referenced by ID.

### 12.4 Generated Postmortem

**[Screenshot placeholder: Postmortem view]**

*Expected content:* Summary, timeline entries, root cause, impact with peak metrics, action items. Optional: exported `.md` file preview.

### 12.5 Deployment Confirmation

**[Screenshot placeholder: Render + Vercel deployment]**

*Expected content:* Render dashboard showing three live services; Vercel deployment status; Neon database connection active.

---

## 13. Known Limitations & Future Scope

### 13.1 Known Limitations

| Limitation | Details |
|------------|---------|
| **Render free-tier cold starts** | Services spin down after ~15 minutes of inactivity. First request may take 50+ seconds to wake all three backends. |
| **Postmortem quality (v1)** | Timeline can be sparse when few timeline-eligible events exist. Action items may be generic. Impact framing may need human review before external sharing. |
| **error_rate recovery** | 100-request rolling window + 60-second recovery timer means sustained normal traffic (~180 requests) needed before error_rate and incident status fully normalize. |
| **Evidence sampling** | Large incident windows sample to 150 items; some evidence IDs referenced in expanded views may fall outside the sampled set sent to Gemini. |
| **Polling-based dashboard** | Metrics polled every 3s, logs every 2s—not true real-time streaming. |
| **No authentication** | `/admin/inject` and all telemetry endpoints are unauthenticated—acceptable for demo, not production-ready. |
| **Gemini API dependency** | RCA and postmortem require `GEMINI_API_KEY`; free-tier quota limits can cause 429 errors mapped to structured API responses. |

### 13.2 Future Scope

1. **Vector search over logs** — Semantic retrieval of relevant log lines beyond time-window queries, using embeddings for evidence selection.
2. **Streaming log ingestion** — Replace HTTP POST + polling with WebSockets or a message queue (Kafka, Redis Streams) for lower-latency dashboards.
3. **Alert correlation** — Combine multiple signal types (error rate + latency + log patterns) into composite alerts before opening incidents.
4. **Slack/PagerDuty integration** — Push incident open/resolve notifications and postmortem links to on-call channels.
5. **CORS wildcard for Vercel previews** — Allow `*.vercel.app` origins programmatically to avoid manual CORS updates per preview deployment.
6. **Automated test suite** — pytest for anomaly detection logic, evidence sampling, and Pydantic validation; Playwright for frontend E2E.
7. **Multi-model support** — Configurable LLM provider abstraction beyond Gemini.

---

## 14. Conclusion

AI Incident Response Engineer demonstrates that LLM-assisted incident analysis can be both powerful and trustworthy when grounded in real observability data. By ingesting live logs and metrics from microservices, detecting anomalies with interpretable statistics, and constraining Gemini to cite numbered evidence items validated against PostgreSQL rows, the system produces RCA and postmortem outputs that an engineer can audit rather than blindly accept.

The project spans the full stack—from injectable failure modes and telemetry ingestion through anomaly-driven incident lifecycle management to a production-deployed dashboard on Vercel, Render, and Neon. Its core technical idea—**grounded RCA over real telemetry**—addresses a genuine gap in AI-for-ops tooling: moving beyond fluent summaries toward verifiable, evidence-linked incident response suitable for academic study and professional portfolio demonstration.

---

## 15. References

1. FastAPI Documentation — [https://fastapi.tiangolo.com/](https://fastapi.tiangolo.com/)
2. Next.js Documentation — [https://nextjs.org/docs](https://nextjs.org/docs)
3. Google Gemini API Documentation — [https://ai.google.dev/gemini-api/docs](https://ai.google.dev/gemini-api/docs)
4. SQLAlchemy Documentation — [https://docs.sqlalchemy.org/](https://docs.sqlalchemy.org/)
5. Alembic Documentation — [https://alembic.sqlalchemy.org/](https://alembic.sqlalchemy.org/)
6. Neon PostgreSQL Documentation — [https://neon.tech/docs](https://neon.tech/docs)
7. Render Deployment Documentation — [https://render.com/docs](https://render.com/docs)
8. Render Blueprint YAML Reference — [https://render.com/docs/blueprint-spec](https://render.com/docs/blueprint-spec)
9. Recharts Documentation — [https://recharts.org/](https://recharts.org/)
10. Pydantic Documentation — [https://docs.pydantic.dev/](https://docs.pydantic.dev/)

---

*Report generated from the implemented codebase at `github.com/prapti-jain/ai-incident-response-engineer`. All endpoint paths, column names, configuration defaults, and architectural descriptions reflect the code as deployed, not an idealized design.*
