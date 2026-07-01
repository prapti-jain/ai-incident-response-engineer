# AI Incident Response Engineer

An end-to-end incident response demo that ingests **real telemetry** from live microservices—not mocked data—and uses Gemini to produce **grounded root cause analysis** and **automated postmortems**. When anomaly detection flags elevated error rates or latency, the system pulls actual logs and metrics from the incident window, assigns each item a stable ID, and asks the model to cite specific evidence. Every claim in the RCA can be traced back to a row in Postgres, making the output auditable instead of a black-box summary.

**Live demo:** [Dashboard](https://ai-incident-response-engineer.vercel.app) · [Telemetry health](https://incident-telemetry.onrender.com/health)

## Architecture

```mermaid
flowchart LR
  Browser --> Frontend["Next.js frontend<br/>(Vercel)"]
  Frontend --> Telemetry["Telemetry service<br/>(Render)"]
  Frontend --> ServiceA["service-a<br/>(Render)"]
  Telemetry --> Neon["Postgres / Neon"]
  ServiceA --> ServiceB["service-b<br/>(Render)"]
  ServiceA --> Ingest["/ingest/logs · /ingest/metrics"]
  ServiceB --> Ingest
  Ingest --> Neon
  Neon --> Detector["Anomaly detector"]
  Detector --> Incidents["incidents table"]
  Incidents --> RCA["Gemini RCA"]
  RCA --> RcaReport["incidents.rca_report"]
  Incidents --> Postmortem["Gemini postmortem"]
  Postmortem --> PmReport["incidents.postmortem"]
```

## How the RCA grounding works

1. **Evidence retrieval** — When you trigger RCA for an incident, the telemetry service queries Postgres for logs and metrics in a time window around the incident (with padding before/after start/end). Items are sorted chronologically and, if the window is large, evenly sampled up to a cap so the prompt stays bounded.

2. **Stable IDs** — Each log line and metric point gets a numeric ID in the evidence bundle sent to Gemini. The prompt lists every item as `[id] timestamp service source …`.

3. **Constrained generation** — Gemini is instructed to propose up to three ranked root causes and cite only IDs from the provided list. The response is validated as structured JSON; any citation to an unknown ID is rejected.

4. **Join back to source rows** — After the model responds, cited IDs are resolved to the original log/metric rows and returned alongside the RCA. The UI lets you expand each cause and see the exact evidence behind it.

**Why this matters:** LLMs hallucinate freely when asked open-ended “what went wrong?” questions. Grounding forces the model to anchor hypotheses in observable data. An on-call engineer (or an interviewer) can verify every claim by clicking through to the cited telemetry—not just trusting a plausible-sounding paragraph.

## Local development

**Terminal 1 — backends** (Postgres bootstrap, migrations, three FastAPI services):

```bash
./scripts/start.sh
```

**Terminal 2 — frontend:**

```bash
cd frontend && npm run dev
```

Open [http://localhost:3000](http://localhost:3000). Copy `frontend/.env.local.example` to `frontend/.env.local` if you need to override API URLs.

**Gemini API key** (required for RCA and postmortem):

```bash
# services/telemetry/.env
GEMINI_API_KEY=your-key-here
```

Local Postgres defaults to `postgresql://telemetry:telemetry@127.0.0.1:5432/telemetry` (via Docker Compose or Homebrew). Override with `DATABASE_URL` if needed.

## Tech stack

| Layer | Tools |
|-------|-------|
| Frontend | Next.js, Tailwind CSS, Recharts |
| Backends | FastAPI, SQLAlchemy, Alembic |
| Database | Postgres (Neon in production) |
| AI | Gemini via `google-genai` |
| Deployment | Vercel (frontend) + Render (telemetry, service-a, service-b) |

Infrastructure is defined in [`render.yaml`](render.yaml) for the three backend services.

## Known limitations

- **Render free tier cold starts** — Services spin down after inactivity. The first request after idle can take 50+ seconds while instances wake.
- **error_rate recovery** — The rolling window holds 100 requests; flushing a spike plus the 60s recovery timer means ~180 clean requests before error_rate returns to baseline.
- **Postmortem quality (v1)** — Timelines can be sparse when evidence is thin, and impact framing may need human review before sharing externally.
