"""Unit tests for CUSTOMER_API_KEYS parsing."""

from app.auth.security import _parse_customer_api_keys


def test_parses_normal_entries() -> None:
    result = _parse_customer_api_keys("key1:cust_001,key2:cust_002")
    assert result == {"key1": "cust_001", "key2": "cust_002"}


def test_empty_input_returns_empty_mapping() -> None:
    assert _parse_customer_api_keys("") == {}
    assert _parse_customer_api_keys("   ") == {}


def test_entry_without_colon_is_dropped() -> None:
    result = _parse_customer_api_keys("key1cust001,key2:cust_002")
    assert result == {"key2": "cust_002"}


def test_entry_with_empty_key_is_dropped() -> None:
    result = _parse_customer_api_keys(":cust_001,key2:cust_002")
    assert result == {"key2": "cust_002"}


def test_entry_with_empty_customer_id_is_dropped() -> None:
    result = _parse_customer_api_keys("key1:,key2:cust_002")
    assert result == {"key2": "cust_002"}


def test_duplicate_key_is_dropped_entirely_not_first_wins() -> None:
    result = _parse_customer_api_keys("key1:cust_001,key1:cust_002,key2:cust_003")
    assert result == {"key2": "cust_003"}
    assert "key1" not in result


def test_whitespace_around_entries_and_pairs_is_tolerated() -> None:
    result = _parse_customer_api_keys(" key1 : cust_001 , key2:cust_002 ")
    assert result == {"key1": "cust_001", "key2": "cust_002"}


def test_splits_on_first_colon_only() -> None:
    result = _parse_customer_api_keys("key1:cust:001")
    assert result == {"key1": "cust:001"}
