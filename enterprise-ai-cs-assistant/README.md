# Enterprise AI Customer Success Assistant

Internal assistant for a B2B SaaS Customer Success team.
Answers product questions via RAG, looks up customer account info via a
mock tool, and escalates billing/contract issues to a human via a mock
ticketing tool.

## Status
Scaffold only. No implementation yet. See PLAN.md once the implementation
plan is approved.

## Local setup
1. python -m venv .venv && source .venv/bin/activate
2. pip install -r requirements.txt
3. cp .env.example .env and fill in your API key
4. uvicorn app.main:app --reload

## Structure
- app/api      request/response endpoints
- app/rag      document ingestion and retrieval
- app/tools    account lookup and ticket escalation (mock)
- app/agent    decides when to retrieve, call a tool, or escalate
- app/auth     simple API key check
- app/core     config and logging
- data/docs    product docs and release notes used for RAG
- data/mock    fake customer accounts and tickets
- eval         test questions used to check answer quality
- tests        unit and integration tests
- docker       Dockerfile

## Security

Secrets (`LLM_API_KEY`, `API_AUTH_KEY`, `CUSTOMER_API_KEYS`) are configured
only via environment variables. Locally that's `.env` (never committed,
see `.gitignore`); in production they're set directly in Render's
dashboard, injected into the container at runtime, and never baked into
the Docker image.

There are two API key types, both sent via the `X-API-Key` header:

- **Staff key (`API_AUTH_KEY`)** — unrestricted. This app is an *internal*
  CS-team tool, and staff legitimately look up different customers all
  day, so this key intentionally has no per-customer restriction.
- **Customer-scoped keys (`CUSTOMER_API_KEYS`)** — the mechanism for when
  a caller must be restricted to exactly one customer. Format:
  `key1:cust_001,key2:cust_002` (comma-separated `key:customer_id` pairs).
  A request authenticated with one of these keys is bound to that
  `customer_id`: it's used automatically if the request omits
  `customer_id`, and the request is rejected (`403`) if it names a
  different one. This is not a general permissions system — it enforces
  exactly that one boundary.

To rotate either key type: change the value in Render's dashboard and
redeploy. There is currently no rate limiting on `/ask` — accepted as a
reasonable tradeoff given this project's scale (single shared staff key,
low traffic, no external infrastructure).
