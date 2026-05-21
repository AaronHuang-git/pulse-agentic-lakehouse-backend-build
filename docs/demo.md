# Pulse demo script (target: 4 minutes)

A copy-pasteable script for the portfolio screencast. Read narration in
your own words; the commands and expected outputs are what to type and
what should appear on screen.

## Prep checklist (do once, before hitting record)

```powershell
# 1. Stack should be running and healthy
.\pulse.ps1 ps
# All 9 containers should show Up + (healthy) where applicable.
# If not: .\pulse.ps1 up -d

# 2. Verify .env points at real Anthropic (so the live demo uses Claude)
Get-Content .env | Select-String "PULSE_AGENT_PROVIDER|ANTHROPIC_API_KEY="
# Should show:
#   ANTHROPIC_API_KEY=sk-ant-api03-...   (a real key, not REPLACE-ME)
#   PULSE_AGENT_PROVIDER=anthropic

# 3. Confirm olist_geolocation is already ingested (set up earlier)
curl.exe -s "http://localhost:8002/v1/datasets" -H "Authorization: Bearer demo-key-1234" `
    | ConvertFrom-Json | Format-Table name, total_rows
# Should show olist_geolocation with ~1M rows.

# 4. Pre-open these in your browser, hidden behind the terminal:
#    - http://localhost:8000/docs       (gateway docs index)
#    - http://localhost:9001            (MinIO console; login pulse/pulse_dev_password)
#    - http://localhost:8001/metrics    (Prometheus endpoint, raw text)

# 5. Open a second PowerShell window for tailing worker logs.
#    In it, run:
#        .\pulse.ps1 logs -f ingest-worker
```

Hit record. Screen should show terminal full-screen.

---

## [0:00 - 0:15] Open

**Show:** terminal at repo root, nothing else.

**Say:**

> Pulse is a self-hostable backend that ingests CSV business data into a
> queryable lakehouse, exposes REST APIs, and answers natural-language
> questions through an LLM agent that calls those APIs as tools. The
> whole stack runs locally with one command. Let me show you.

**Type:**

```powershell
.\pulse.ps1 ps
```

**Expected on screen:** 9 containers, all healthy. Point at the
columns briefly &mdash; gateway, ingest, ingest-worker, query, agent on
top; postgres, redis, minio, mongodb beneath.

**Say:**

> Four Pulse services, four backing data stores, plus the Celery worker.
> All on a private Docker network.

---

## [0:15 - 1:00] Upload &mdash; the async ingestion path

**Say:**

> Ingestion is async with idempotency. The endpoint accepts the file,
> writes the raw artifact to MinIO, computes a SHA, enqueues a parse
> task, and returns 202 immediately. A separate worker picks it up.

**Type** (in the main terminal):

```powershell
curl.exe -X POST http://localhost:8001/v1/ingest/upload `
    -H "Authorization: Bearer demo-key-1234" `
    -F "file=@data/olist/olist_orders_dataset.csv" `
    -F "dataset=olist_orders_demo"
```

**Expected:** JSON with `status: queued` or `deduplicated: true` if you've
uploaded it before. Either is fine for the demo &mdash; both show
idempotency working.

**Switch to the second terminal** showing `pulse logs -f ingest-worker`.
Wait ~2 seconds. You'll see:

```
Task ingest.parse_upload[...] received
Task ingest.parse_upload[...] succeeded in 1.5s
```

**Say:**

> The worker received the task, ran DuckDB to write Parquet to MinIO,
> updated the job row, and finished in under two seconds. The upload
> endpoint returned in under a second &mdash; even for the 1 M-row
> Olist geolocation file.

---

## [1:00 - 1:45] Structured query

**Say:**

> Now I can query the data. There are two interfaces: a JSON DSL the
> agent uses, and a read-only SQL endpoint for power users. Both enforce
> tenant isolation server-side.

**Type:**

```powershell
curl.exe -s "http://localhost:8002/v1/datasets" `
    -H "Authorization: Bearer demo-key-1234" `
    | ConvertFrom-Json | Format-Table
```

**Expected:** table of datasets, row counts, last-ingested timestamps.

**Type the structured-DSL query:**

```powershell
$body = '{"dataset":"olist_geolocation","filters":[{"column":"geolocation_state","op":"eq","value":"SP"}],"group_by":["geolocation_city"],"aggregate":[{"fn":"count","as":"n"}],"order_by":[{"column":"n","dir":"desc"}],"limit":5}'
$body | Out-File -FilePath body.json -Encoding ascii
curl.exe -s -X POST "http://localhost:8002/v1/query/structured" `
    -H "Authorization: Bearer demo-key-1234" `
    -H "Content-Type: application/json" `
    --data-binary "@body.json" `
    | ConvertFrom-Json | Select-Object -ExpandProperty rows | Format-Table
```

**Expected:** top 5 SP cities by row count. São Paulo ~135k, then variants
and other cities.

**Say:**

> The DSL is compiled to parameterized SQL server-side. Column names are
> validated against the schema; values are bound as parameters. Tenant
> isolation happens through a DuckDB temp view &mdash; the agent
> physically can't read another tenant's data.

---

## [1:45 - 3:15] Agent &mdash; the headline demo

**Say:**

> Now the agent. I'll ask a natural-language question; Claude will pick
> tools and execute queries to answer it. Every number in the answer
> traces back to a tool result &mdash; grounding is structural, not just
> a prompt rule.

**Type:**

```powershell
$q = '{"question":"What are the top 3 Brazilian states by number of geolocation entries? Give me the state codes and counts."}'
$q | Out-File -FilePath question.json -Encoding ascii
curl.exe -s -X POST "http://localhost:8003/v1/agent/ask" `
    -H "Authorization: Bearer demo-key-1234" `
    -H "Content-Type: application/json" `
    --data-binary "@question.json" `
    | ConvertFrom-Json | Format-List
```

**Expected (after ~6 seconds):**

```
answer       : The top 3 Brazilian states by number of geolocation entries are:
               1. **SP** - 404,268 entries
               2. **MG** - 126,336 entries
               3. **RJ** - 121,169 entries

tool_calls   : {@{tool=list_datasets; ...}, @{tool=describe_dataset; ...}, @{tool=run_query; ...}}
iterations   : 4
model        : claude-haiku-4-5-20251001
provider     : anthropic
tokens_used  : @{input=7573; output=374}
```

**Say (pointing at fields as they appear):**

> Four model turns, three tool calls. The agent listed the datasets,
> described the schema, then built a structured query itself based on
> what it learned. The final answer's numbers come straight from that
> last tool result &mdash; you can read the trace and verify every claim.
> One question cost about a cent.

---

## [3:15 - 3:45] Observability tour

**Type:**

```powershell
curl.exe -s "http://localhost:8001/metrics" | Select-String "^pulse_" | Select-Object -First 8
```

**Expected:** Prometheus-format lines &mdash; `pulse_requests_total{...}`,
`pulse_request_duration_seconds_bucket{...}`, etc.

**Say:**

> Every service exposes Prometheus metrics on /metrics. Every log line is
> JSON. Every request gets a correlation ID that propagates across
> services &mdash; you can grep one ID and reconstruct the full trace.

**Type:**

```powershell
.\pulse.ps1 logs --tail 3 query 2>$null
```

**Expected:** 1-3 JSON log lines from the query service.

**Switch to browser, show:** http://localhost:8000/docs &mdash; the
gateway's aggregated docs index page with links to each service's
Swagger UI.

---

## [3:45 - 4:00] Close

**Say (back in terminal):**

> The repo has three ADRs documenting why I picked DuckDB over a
> warehouse, Celery over alternatives, and two query interfaces over
> one. A benchmark report with real numbers. Twenty-one passing tests
> including an end-to-end one. CI workflow ready. Mock LLM fallback
> for anyone running without an API key.
>
> Everything's at github.com/AaronHuang-git/pulse-agentic-lakehouse-backend-build. Thanks.

End recording.

---

## Recovery notes (if something breaks live)

| Symptom | Fix |
|---|---|
| Upload returns 401 | `.env` API key is wrong. Verify `Authorization: Bearer demo-key-1234`. |
| Upload returns `deduplicated: true` and that's confusing | That's the idempotency feature working &mdash; not a bug. Acknowledge it on camera and move on. |
| Agent returns `[MOCK provider]` answer | `PULSE_AGENT_PROVIDER` in `.env` was left as `mock`. Either switch and restart agent before recording, or own it on camera as the offline path. |
| One of the containers is unhealthy | `.\pulse.ps1 logs <service>` to see the error. Worst case: `.\pulse.ps1 down ; .\pulse.ps1 up -d` and wait 20 seconds. |
| `curl` JSON formatting mangles output | Pipe to `| ConvertFrom-Json | ConvertTo-Json -Depth 10` instead. |

## Suggested recording tool

- **Loom** (web app, free tier covers up to 5 min &mdash; a tight cap).
  Cursor highlighting + facecam optional.
- Alternative: **OBS Studio** if you want raw screen capture with no
  account.

