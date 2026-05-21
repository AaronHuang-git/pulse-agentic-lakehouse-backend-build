# ADR-0001: DuckDB + Parquet for the lakehouse layer

**Status:** Accepted, 2026-05-20.

## Context

Pulse must serve aggregate queries over CSV-ingested business data with:

- Tenant-isolated reads (server-injected `WHERE tenant_id = ?`).
- Single-laptop deployability (`docker compose up` and nothing else).
- Throughput in the hundreds-of-thousands-of-rows-per-second range so we
  meet a 5k rows/sec ingest target with margin.
- A query latency profile that an LLM agent can chain over multiple tool
  calls without becoming wall-clock-painful.

We do **not** need: cluster-scale concurrency, ANSI-SQL window-function
parity with Snowflake, or sub-second cold queries.

## Decision

Use **DuckDB** as the embedded analytical SQL engine, with **Parquet
files on S3-compatible object storage** (MinIO locally; swappable to AWS
S3 or compatible) as the durable storage layer. DuckDB reads Parquet
directly from S3 via its `httpfs` extension.

## Alternatives considered

- **ClickHouse** &mdash; great columnar engine, but introduces a separate
  server process, replication considerations, and its own SQL dialect.
  Overkill for the single-tenant scope of this submission.
- **Trino / Presto + Hive Metastore** &mdash; the "industry standard"
  query-federation answer, but the coordinator/worker topology is
  disproportionate to what we're doing. Three extra long-running services
  for a system that fits on a laptop.
- **PostgreSQL + columnstore extensions (e.g. `pg_columnar`, Citus)**
  &mdash; appealing because we already run Postgres for metadata, but
  analytical performance is not in the same class as DuckDB on the same
  data shape, and we'd reintroduce row-store overhead for OLAP queries.
- **Hosted warehouses (Snowflake, BigQuery, Databricks SQL)**
  &mdash; defeats the self-hostable goal and adds a paid dependency.

## Consequences

**Positive**
- Zero ops: DuckDB is one Python `import`. No additional container, no
  metastore, no separate schema registry.
- S3-compatible storage means a future swap to AWS S3, GCS, or Azure
  Blob is a config change, not a code change.
- Parquet's compression and column-pruning give us 5&ndash;10&times;
  size reduction over the raw CSV and 10&ndash;100&times; faster scans
  for aggregate queries.
- DuckDB's `read_csv_auto` does schema inference well, simplifying
  the ingest path.

**Negative / Accepted limitations**
- **Single-node only.** Horizontal scale-out would require a different
  engine. Documented as out of scope.
- **No native statement timeout.** We cap row counts at 10,000 per query
  and discussed implementing a Python-side watchdog using
  `con.interrupt()` in a future iteration.
- **Connection-per-request model**: each query opens a fresh in-memory
  DuckDB. Adds ~50&ndash;100ms of session-init overhead. A connection
  pool would help (see `docs/benchmark.md`).

## Revisit triggers

- Adding a second tenant with materially different working sets and
  needing isolation beyond storage paths.
- Cold-storage data growing past what a single laptop can scan in
  acceptable time (multi-TB).
- A workload that does heavy joins across very large tables (DuckDB
  handles this well, but ClickHouse-style distribution would win at
  cluster scale).
