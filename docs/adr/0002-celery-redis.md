# ADR-0002: Celery + Redis for async ingestion

**Status:** Accepted, 2026-05-20.

## Context

The ingest endpoint must accept files of &ge; 100 MB without blocking the
HTTP request path. Parsing a CSV into Parquet via DuckDB takes seconds to
tens of seconds depending on size; doing that work synchronously would
both burn HTTP timeout budget and serialize uploads behind one worker.

We need:

- A queue where the HTTP-facing process enqueues parse jobs and a separate
  worker pool consumes them.
- A status-of-record table so clients can poll progress
  (`queued -> processing -> done|failed`).
- At-least-once delivery (a crashed worker mid-task re-runs after recovery).

## Decision

Use **Celery 5** with **Redis** as the broker (DB 0) and result backend
(DB 1, short TTL). Postgres `jobs` table remains the authoritative
status-of-record; the Celery result backend is bookkeeping only.

Worker container is the same image as the web container; the only
difference is the entry command (`celery ... worker` vs `uvicorn ...`).
This keeps build pipelines and code paths unified.

## Alternatives considered

- **RQ (Redis Queue)** &mdash; lighter-weight than Celery, but lacks
  Celery's worker recycling, late-ack semantics, and ecosystem
  (Flower, beat, signals). Worth it on smaller projects; we want the
  observability and reliability surface.
- **Postgres-backed queue (`pgmq`, `pg-boss`, listen/notify)** &mdash;
  attractive because we already run Postgres. But Postgres queues
  have lock-contention issues at high throughput, and we'd lose the
  separate-failure-domain property: a Postgres outage already disables
  every API path, so we don't want it to also disable the work queue.
  Plus Redis is already in the stack as the FastAPI/auth cache; reusing
  it for queueing is free.
- **AWS SQS / GCP Pub/Sub** &mdash; managed and excellent, but defeats
  the self-hostable goal and adds a cloud dependency.
- **In-process background tasks (FastAPI `BackgroundTasks`,
  `asyncio.create_task`)** &mdash; would block on a web restart and
  doesn't survive process crashes. Unacceptable for ingestion.

## Consequences

**Positive**
- The upload endpoint returns in &lt;1.5s even for 60 MB / 1M-row uploads
  (measured in `docs/benchmark.md`).
- Workers can scale horizontally (`--concurrency=N`, multiple worker
  containers).
- Late-ack semantics: a crashed worker mid-task re-delivers the message,
  and our parse task is idempotent (same Parquet object key, same SQL
  upsert pattern) so retries are safe.
- `worker_max_tasks_per_child=200` recycles worker processes to defend
  against memory leaks from long-lived DuckDB connections.

**Negative / Accepted limitations**
- Two more moving parts (Celery + Redis) versus a synchronous design.
- Celery's API surface is large; we use a small subset (just `.delay()`
  and `@task`).
- We need both async and sync SQLAlchemy engines &mdash; async for the
  FastAPI endpoints, sync for the Celery worker code path. Adds ~40
  lines to `shared/db.py`.

## Revisit triggers

- Workloads outgrowing Redis's single-node capacity (~100k tasks/sec).
- Need for cross-region durability of pending tasks (Redis is local;
  managed queue or persistent broker becomes attractive).
- A workflow engine (Airflow / Prefect / Dagster) becoming a better fit
  if scheduling and DAGs enter scope.
