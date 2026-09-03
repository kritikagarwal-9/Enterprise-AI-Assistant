"""Unit tests for the mock escalation/ticketing tool."""

import json
from pathlib import Path

from app.tools.escalation import create_ticket


def test_create_ticket_writes_and_returns_record(tmp_path: Path) -> None:
    path = tmp_path / "tickets.json"
    ticket = create_ticket(
        reason="billing_dispute",
        summary="Customer says they were double charged.",
        customer_id="cust_001",
        data_path=path,
    )
    assert ticket["ticket_id"].startswith("tkt_")
    assert ticket["reason"] == "billing_dispute"
    assert ticket["status"] == "open"

    saved = json.loads(path.read_text(encoding="utf-8"))
    assert len(saved) == 1
    assert saved[0]["ticket_id"] == ticket["ticket_id"]


def test_create_ticket_appends_to_existing_file(tmp_path: Path) -> None:
    path = tmp_path / "tickets.json"
    create_ticket(reason="complaint", summary="first", data_path=path)
    create_ticket(reason="complaint", summary="second", data_path=path)
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert len(saved) == 2


def test_create_ticket_normalizes_unknown_reason(tmp_path: Path) -> None:
    path = tmp_path / "tickets.json"
    ticket = create_ticket(reason="not_a_real_reason", summary="x", data_path=path)
    assert ticket["reason"] == "other"
