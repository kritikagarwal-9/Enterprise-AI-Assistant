"""Unit tests for the mock escalation/ticketing tool."""

import json
import logging
from pathlib import Path

import pytest

from app.tools.escalation import TicketCreationError, create_ticket


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


def test_create_ticket_raises_on_write_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    path = tmp_path / "tickets.json"

    def _boom(self, *args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(Path, "write_text", _boom)
    with pytest.raises(TicketCreationError):
        create_ticket(reason="complaint", summary="x", data_path=path)


def test_create_ticket_logs_warning_on_corrupt_existing_file(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    path = tmp_path / "tickets.json"
    path.write_text("{not valid json", encoding="utf-8")

    with caplog.at_level(logging.WARNING, logger="app"):
        create_ticket(reason="complaint", summary="x", data_path=path)

    assert any("tickets_file_corrupt" in record.message for record in caplog.records)
