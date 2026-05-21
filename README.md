# Pulse &mdash; Agentic Lakehouse Backend

Self-hostable backend that ingests CSV business data, normalizes it into
a queryable lakehouse on object storage, exposes versioned REST APIs,
and answers natural-language questions via an LLM agent that calls
those APIs as tools.

## Quickstart

**Windows (PowerShell):**

```powershell
Copy-Item .env.example .env
.\pulse.ps1 up -d
```

**macOS / Linux:**

```bash
cp .env.example .env
./pulse.sh up -d
```

Then visit:

- Docs index: http://localhost:8000/docs
- Health: http://localhost:8001/health (and :8000, :8002, :8003)
- MinIO console: http://localhost:9001 (`pulse` / `pulse_dev_password`)

Demo tenant API key (local dev only): `demo-key-1234`.
