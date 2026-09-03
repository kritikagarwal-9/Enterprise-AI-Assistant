"""Mock tool: creates a support ticket for billing/contract/complaint issues.

Writes to data/mock/tickets.json. This is a mock, not a real ticketing
system integration - it exists so the agent has a real place to hand off
to a human instead of guessing.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_TICKETS_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "mock" / "tickets.json"
)

VALID_REASONS = {"billing_dispute", "contract_issue", "complaint", "other"}


def create_ticket(
    reason: str,
    summary: str,
    customer_id: str | None = None,
    data_path: Path | None = None,
) -> dict:
    """Create a mock escalation ticket and persist it. Returns the ticket
    record, including a generated ticket_id.
    """
    path = data_path or DEFAULT_TICKETS_PATH
    normalized_reason = reason.strip().lower() if reason else "other"
    if normalized_reason not in VALID_REASONS:
        normalized_reason = "other"

    ticket = {
        "ticket_id": f"tkt_{uuid.uuid4().hex[:10]}",
        "customer_id": customer_id,
        "reason": normalized_reason,
        "summary": summary.strip() if summary else "",
        "status": "open",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        existing = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    except json.JSONDecodeError:
        existing = []
    existing.append(ticket)
    path.write_text(json.dumps(existing, indent=2), encoding="utf-8")

    return ticket
