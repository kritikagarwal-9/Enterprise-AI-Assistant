"""Unit tests for mock account lookup."""

import json
from pathlib import Path

from app.tools.account_lookup import lookup_account


def test_lookup_cust_001() -> None:
    result = lookup_account("cust_001")
    assert result is not None
    assert result["customer_id"] == "cust_001"
    assert result["plan"] == "starter"
    assert result["status"] == "active"
    assert result["usage"] == {"seats_used": 3, "seats_limit": 5}


def test_lookup_cust_003_past_due() -> None:
    result = lookup_account("cust_003")
    assert result is not None
    assert result["status"] == "past_due"


def test_lookup_unknown_returns_none() -> None:
    assert lookup_account("cust_999") is None


def test_lookup_empty_id_returns_none() -> None:
    assert lookup_account("") is None
    assert lookup_account("   ") is None


def test_lookup_uses_custom_data_path(tmp_path: Path) -> None:
    custom = tmp_path / "customers.json"
    custom.write_text(
        json.dumps(
            [
                {
                    "customer_id": "cust_temp",
                    "plan": "enterprise",
                    "status": "active",
                    "usage": {"seats_used": 1, "seats_limit": 100},
                }
            ]
        ),
        encoding="utf-8",
    )
    result = lookup_account("cust_temp", data_path=custom)
    assert result is not None
    assert result["plan"] == "enterprise"
    assert lookup_account("cust_001", data_path=custom) is None
