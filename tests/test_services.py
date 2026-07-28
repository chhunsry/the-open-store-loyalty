import os

import pytest

from app.database import init_db
from app.services import (
    ValidationError,
    change_points,
    create_or_update_customer,
    customer_history,
    get_customer_by_phone,
    normalize_phone,
)


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    init_db()


def test_phone_normalization():
    assert normalize_phone("+855 (12) 345-678") == "+85512345678"
    with pytest.raises(ValidationError):
        normalize_phone("123")


def test_create_update_and_points():
    customer, created = create_or_update_customer("Sophea Chan", "+855 12 345 678")
    assert created and customer["points"] == 0
    updated, created = create_or_update_customer("Sophea C.", "+85512345678")
    assert not created and updated["id"] == customer["id"]
    result = change_points(customer["id"], 75, "Purchase", "test")
    assert result["points"] == 75
    assert get_customer_by_phone("+85512345678")["name"] == "Sophea C."
    assert customer_history(customer["id"])[0]["balance_after"] == 75


def test_balance_cannot_be_negative():
    customer, _ = create_or_update_customer("Test Person", "012345678")
    with pytest.raises(ValidationError):
        change_points(customer["id"], -1, "Nope", "test")

