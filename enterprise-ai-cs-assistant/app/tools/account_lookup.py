"""Mock tool: given a customer id, returns plan tier, usage, account status."""

from __future__ import annotations

import json
from pathlib import Path

DEFAULT_CUSTOMERS_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "mock" / "customers.json"
)


def lookup_account(
    customer_id: str,
    data_path: Path | None = None,
) -> dict | None:
    if not customer_id or not customer_id.strip():
        return None

    path = data_path or DEFAULT_CUSTOMERS_PATH
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
