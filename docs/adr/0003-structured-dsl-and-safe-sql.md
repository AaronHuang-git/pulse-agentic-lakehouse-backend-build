# ADR-0003: Two query interfaces &mdash; structured DSL and safe SQL

**Status:** Accepted, 2026-05-20.

## Context

The query service has two distinct callers:

- **The LLM agent**, which constructs queries from natural-language
  questions. Reliability and safety matter more than expressiveness.
- **A power user**, who already knows SQL and wants a read-only escape
  hatch into the lakehouse without rebuilding their query in a JSON DSL.

Both must enforce tenant isolation server-side. Neither can be allowed
to mutate data.

## Decision

Expose **two complementary endpoints**:

- `POST /v1/query/structured` &mdash; a JSON DSL with explicit fields
  for `dataset`, `filters`, `group_by`, `aggregate`, `order_by`, `limit`,
  and a cursor for pagination. Compiled server-side to parameterized
  SQL. Column references are validated against the dataset's schema
  before any SQL is built; values bind as parameters; identifiers are
  double-quoted only after rejecting illegal characters.
- `POST /v1/query/sql` &mdash; read-only SQL. Parsed by `sqlglot`,
  rejected if it is not a single SELECT/UNION/CTE/Subquery. Referenced
  tables must match valid datasets for the caller's tenant; each is
  bound as a tenant-scoped temporary DuckDB view before execution.
  Wrapped in `SELECT * FROM (<user_sql>) LIMIT 10000`.

The LLM agent uses **only** the structured DSL via its
`run_query` tool. The SQL endpoint is for humans.

## Alternatives considered

- **Raw SQL only.** Simpler. But: exposes the agent to prompt-injection
  attacks that construct malicious SQL strings. The agent could be
  manipulated into writing `'; DROP TABLE jobs;--` patterns. Even with a
  parser-based denylist, the surface is too wide and the failure mode
  (data loss) too sharp. We keep the agent on a structured grammar so
  it has no string-concatenation surface to exploit.
- **DSL only.** Cleaner, but rejects the legitimate "give an analyst
  read-only SQL access" use case. We don't want to invent CTE-equivalent
  features for v1.
- **Graph query languages (GraphQL, Cube.js model).** Too heavy for
  a single-tenant, single-dataset-family workload. Wins at federated
  catalogs that we don't have.

## Consequences

**Positive**
- Defense in depth: even if a parser-based check missed a mutation,
  the DuckDB connection is per-request and tenant views only expose
  the caller's Parquet glob. Three independent layers stand between
  the user and the data.
- The agent's structured-DSL surface is **easy for an LLM to construct
  correctly** &mdash; verified by Claude Haiku 4.5 producing valid
  queries 4-of-4 on first attempt (see `docs/benchmark.md`).
- Both endpoints share the same `register_dataset_view()` helper, so
  the tenant-scoping rule is in one place.

**Negative / Accepted limitations**
- The DSL covers ~80% of analytical query needs. Window functions,
  CTEs, and joins-across-datasets require dropping to `/v1/query/sql`.
  This is intentional; we don't want the DSL to grow into a SQL
  parallel-universe.
- The cursor is opaque base64 of the offset; we don't sign it or bind
  it to the query hash. A determined client could swap cursors between
  queries and get inconsistent paging. Acceptable for v1.
- Tool descriptions in the agent's `tool_specs.py` carry significant
  semantic weight (the LLM reads them as part of the prompt). Wording
  changes can shift agent behavior; we'd treat this as a versioned
  contract in production.

## Revisit triggers

- The agent starts asking for joins across datasets often enough that
  multi-dataset DSL expansion becomes worth the cost.
- A real attacker / red-team finds a way to mutate data via the SQL
  endpoint; the response would be to remove it rather than expand the
  parser denylist.
- DuckDB releases native statement timeouts; we add them in both paths.
