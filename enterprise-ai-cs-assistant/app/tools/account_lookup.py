"""Mock tool: given a customer id, returns plan tier, usage, account status."""

from __future__ import annotations

import json
from pathlib import Path

DEFAULT_CUSTOMERS_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "mock" / "customers.json"
)


class AccountLookupError(Exception):
    """Raised when the mock customer data can't be read or is malformed."""


def lookup_account(
    customer_id: str,
    data_path: Path | None = None,
) -> dict | None:
    if not customer_id or not customer_id.strip():
        return None

    path = data_path or DEFAULT_CUSTOMERS_PATH
    try:
        customers = json.loads(path.read_text(encoding="utf-8"))
        wanted = customer_id.strip()
        for customer in customers:
            if customer.get("customer_id") == wanted:
                return {
                    "customer_id": customer["customer_id"],
                    "plan": customer["plan"],
                    "status": customer["status"],
                    "usage": customer["usage"],
                }
        return None
    except (OSError, json.JSONDecodeError, KeyError, TypeError, AttributeError) as exc:
        raise AccountLookupError(f"account data unavailable: {exc}") from exc
