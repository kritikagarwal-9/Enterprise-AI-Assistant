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
