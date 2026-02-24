# Censys Alert Ingestion Service

A Python service that periodically fetches alerts from an upstream SIEM aggregator, enriches them with GeoIP and TOR classification data, normalizes them into a local database, and exposes a REST API for downstream consumers.

---

## Quick Start

```bash
# Clone and run
git clone <repo-url>
cd censys-proj

# Copy environment config (defaults work out of the box)
cp .env.example .env

# Build and start both services
docker compose up --build
```

The service is available at **http://localhost:8000**  
The mock upstream API is available at **http://localhost:9000**

Auto-generated API docs: **http://localhost:8000/docs**

---

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    Docker Compose Network                     │
│                                                              │
│  ┌──────────────────┐          ┌───────────────────────┐    │
│  │   alert_simulator_api │          │   censys_service       │    │
│  │   (Flask :9000)  │◄─────────│                       │    │
│  │                  │  HTTP    │  APScheduler           │    │
│  │  GET /alerts     │  GET     │      │                 │    │
│  │                  │          │  Fetcher + tenacity    │    │
│  │  ~20% random     │          │      │                 │    │
│  │  500 failures    │          │  Enrichment plugins    │    │
│  └──────────────────┘          │      │                 │    │
│                                │  Alert DAO             │    │
│                                │      │                 │    │
│                                │  SQLite (volume)       │    │
│                                │                       │    │
│                                │  FastAPI :8000         │    │
│                                │  GET  /alerts          │    │
│                                │  POST /sync            │    │
│                                │  GET  /health          │    │
│                                └───────────────────────┘    │
└──────────────────────────────────────────────────────────────┘
```

---

## API Reference

### `GET /alerts`

Returns normalized, enriched alerts from the local database.

| Parameter         | Type    | Description                                   |
| ----------------- | ------- | --------------------------------------------- |
| `severity`        | enum    | Filter: `low`, `medium`, `high`, `critical`   |
| `source`          | string  | Filter by source system (e.g., `splunk-prod`) |
| `enrichment_type` | enum    | Filter: `tor_exit_node`, `clean`              |
| `since`           | ISO8601 | Alerts created after this timestamp           |
| `limit`           | int     | Max results (default 100, max 500)            |
| `offset`          | int     | Pagination offset                             |

```bash
curl "http://localhost:8000/alerts?severity=critical&limit=10"
curl "http://localhost:8000/alerts?enrichment_type=tor_exit_node"
```

### `POST /sync`

Triggers an immediate fetch from the upstream API.

- Returns `202 Accepted` — sync runs in background, response is immediate
- Returns `409 Conflict` — if a sync is already in progress

```bash
curl -X POST http://localhost:8000/sync
```

### `GET /health`

Lightweight health check. Does **not** call the upstream API (see Architecture Decisions).

```bash
curl http://localhost:8000/health
```

Response:

```json
{
  "status": "ok",
  "db_connected": true,
  "last_successful_sync": "2026-02-22T10:00:00Z",
  "last_sync_status": "success",
  "last_error": null,
  "sync_interval_seconds": 60,
  "upstream_url": "http://alert_simulator_api:9000"
}
```

Status values:

- `ok` — DB reachable, last sync succeeded
- `degraded` — DB reachable but last sync failed (upstream issue, we're still serving stored alerts)
- `down` — DB not reachable (our service is broken)

---

## Configuration

All settings are environment variables. Defaults work for local development.

| Variable                 | Default                           | Description                                |
| ------------------------ | --------------------------------- | ------------------------------------------ |
| `UPSTREAM_URL`           | `http://alert_simulator_api:9000` | Upstream alerts API base URL               |
| `SYNC_INTERVAL_SECONDS`  | `60`                              | How often to poll the upstream             |
| `DB_PATH`                | `/data/alerts.db`                 | SQLite database file path                  |
| `LOG_LEVEL`              | `INFO`                            | Logging level                              |
| `DEFAULT_LOOKBACK_HOURS` | `24`                              | Lookback window on first startup           |
| `MOCK_FAILURE_RATE`      | `0.20`                            | Fraction of mock API calls that return 500 |

---

## Project Structure

```
censys-proj/
├── alert_simulator_api/     # Flask mock upstream Alerts API
│   ├── alert_simulator_server.py
│   └── Dockerfile
│
├── service/
│   ├── server.py           # FastAPI entry point + lifespan startup
│   ├── config.py           # Environment variable settings
│   ├── models.py           # Pydantic schemas
│   ├── api/routes.py       # HTTP endpoints
│   ├── ingestion/
│   │   ├── fetcher.py      # httpx + tenacity retry
│   │   ├── pipeline.py     # fetch → enrich → store orchestration
│   │   └── scheduler.py    # APScheduler periodic job
│   ├── enrichment/
│   │   ├── base.py         # Abstract plugin interface
│   │   ├── geo_ip.py       # GeoIP plugin
│   │   └── tor_classifier.py  # TOR exit node plugin
│   └── storage/
│       ├── database.py     # SQLite init, connection
│       └── alert_dao.py    # All DB read/write (DAO pattern)
│
├── tests/
│   ├── test_enrichment.py
│   ├── test_fetcher.py
│   └── test_api.py
│
├── .github/workflows/
│   ├── lint.yml            # black, isort, pylint
│   ├── test.yml            # pytest + coverage
│   └── security.yml        # Snyk + OWASP ZAP
│
├── docker-compose.yml
├── pyproject.toml
└── .env.example
```

---

## Running Tests

```bash
# Install dependencies
pip install -r service/requirements.txt
pip install -r tests/requirements.txt

# Run all tests with coverage
cd tests
pytest --cov=../service --cov-report=term-missing

# Run a specific test file
pytest test_enrichment.py -v
pytest test_fetcher.py -v
pytest test_api.py -v
```

---

## CI/CD Pipeline

Three GitHub Actions workflows run on every push and pull request:

| Workflow       | Trigger           | Checks                                                      |
| -------------- | ----------------- | ----------------------------------------------------------- |
| `lint.yml`     | Every push/PR     | `black --check`, `isort --check`, `pylint --fail-under=8.0` |
| `test.yml`     | Every push/PR     | `pytest` with 75% coverage threshold                        |
| `security.yml` | Push/PR to `main` | Snyk dependency scan + OWASP ZAP DAST scan                  |

**Note:** The `SNYK_TOKEN` secret must be added to the GitHub repository secrets for the Snyk scan to run.

---

## Architecture Decisions

### Database: SQLite

SQLite was chosen over PostgreSQL for this scope because:

- Zero operational overhead — no separate container or process to manage
- Full SQL support with proper schema, indexes, and constraints
- Ships with Python stdlib — no additional dependency
- The DAO pattern (`storage/alert_dao.py`) abstracts all SQL, so migrating to PostgreSQL for a multi-instance production deployment requires only a connection string change and swapping `sqlite3` for `psycopg2`

### Retry Strategy: tenacity with exponential backoff + jitter

`tenacity` was used instead of manual retry logic — it's the industry-standard library and avoids reinventing a well-tested wheel. The retry policy:

- Up to 3 attempts
- Exponential backoff: 1s → 2s → 4s with jitter
- Retries on 5xx and network errors only — 4xx errors indicate a client bug and are not retried

**Next step:** A circuit breaker (e.g., `pybreaker`) would prevent indefinite retry storms during sustained outages by opening the circuit after N consecutive failures.

### Enrichment: Plugin Architecture

Enrichment is implemented as a plugin system with an abstract base class. Adding a new enrichment source (e.g., WHOIS, ASN lookup) means creating one new file that implements `EnrichmentPlugin.enrich()`. Nothing else changes — the pipeline calls all plugins in sequence without knowing their internals.

Current plugins:

1. **GeoIP** — Randomized public IP (production: MaxMind GeoLite2 or ipwhois)
2. **TOR Classifier** — Checks IP against a simulated Tor exit node list (production: `check.torproject.org/torbulkexitlist`, refreshed and cached every few hours)

### Concurrency: asyncio.Lock

An `asyncio.Lock` prevents two syncs from running simultaneously (scheduler fires while `POST /sync` is in progress). This is sufficient for a single-process deployment. In a multi-instance deployment, this would be replaced with a distributed lock (Redis SETNX) or a dedicated job queue.

### `/health` Does Not Call Upstream

Health checks are polled frequently by load balancers and monitoring systems. Calling the upstream API in `/health` would:

- Inflate upstream rate limits
- Cause false "down" reports when upstream is slow but our service is healthy
- Add latency to every health check

Upstream reachability is instead reflected by `last_sync_status` — captured during actual sync attempts, not on every health poll.

### Idempotent Ingestion

Alerts are inserted with `INSERT OR IGNORE` using `UNIQUE(source, created_at)` as the natural dedup key. This means:

- Re-fetching overlapping time windows (e.g., after a restart) never creates duplicate rows
- The service guarantees **at-least-once delivery** with **idempotent storage** — the practical equivalent of exactly-once for this use case

### Event Time vs Ingestion Time

Each stored alert has two timestamps:

- `created_at` — when the event happened in the source system (security timeline)
- `ingested_at` — when our service stored it (pipeline monitoring, "are we falling behind?")

This two-timestamp pattern is standard across the industry (Splunk: `_time` vs `_indextime`, QRadar: `startTime` vs indexing timestamp).
