import re
import sqlite3
from dataclasses import dataclass

from app.database import connect

PHONE_RE = re.compile(r"^\+?[0-9]{7,15}$")


class ValidationError(ValueError):
    pass


def normalize_phone(value: str) -> str:
    raw = (value or "").strip()
    prefix = "+" if raw.startswith("+") else ""
    digits = re.sub(r"\D", "", raw)
    phone = prefix + digits
    if not PHONE_RE.fullmatch(phone):
        raise ValidationError("Enter a valid phone number with 7–15 digits.")
    return phone


def clean_name(value: str) -> str:
    name = " ".join((value or "").strip().split())
    if not 2 <= len(name) <= 80:
        raise ValidationError("Customer name must be 2–80 characters.")
    return name


def clean_note(value: str) -> str:
    note = " ".join((value or "").strip().split())
    if len(note) > 200:
        raise ValidationError("Note must be 200 characters or fewer.")
    return note


def get_customer_by_phone(phone: str):
    normalized = normalize_phone(phone)
    with connect() as db:
        customer = db.execute(
            "SELECT * FROM customers WHERE phone = ?", (normalized,)
        ).fetchone()
        return dict(customer) if customer else None


def get_customer(customer_id: int):
    with connect() as db:
        customer = db.execute(
            "SELECT * FROM customers WHERE id = ?", (customer_id,)
        ).fetchone()
        return dict(customer) if customer else None


def list_customers(query: str = ""):
    with connect() as db:
        if query:
            pattern = f"%{query.strip()}%"
            rows = db.execute(
                """SELECT * FROM customers
                   WHERE name LIKE ? OR phone LIKE ?
                   ORDER BY updated_at DESC, id DESC""",
                (pattern, pattern),
            ).fetchall()
        else:
            rows = db.execute(
                "SELECT * FROM customers ORDER BY updated_at DESC, id DESC"
            ).fetchall()
        return [dict(row) for row in rows]


def create_or_update_customer(name: str, phone: str):
    name, phone = clean_name(name), normalize_phone(phone)
    with connect() as db:
        existing = db.execute(
            "SELECT id FROM customers WHERE phone = ?", (phone,)
        ).fetchone()
        if existing:
            db.execute(
                """UPDATE customers SET name = ?, updated_at = CURRENT_TIMESTAMP
                   WHERE id = ?""",
                (name, existing["id"]),
            )
            customer_id = existing["id"]
            created = False
        else:
            cur = db.execute(
                "INSERT INTO customers(name, phone) VALUES (?, ?)", (name, phone)
            )
            customer_id = cur.lastrowid
            created = True
    return get_customer(customer_id), created


def update_customer(customer_id: int, name: str, phone: str):
    name, phone = clean_name(name), normalize_phone(phone)
    with connect() as db:
        try:
            cur = db.execute(
                """UPDATE customers SET name = ?, phone = ?,
                   updated_at = CURRENT_TIMESTAMP WHERE id = ?""",
                (name, phone, customer_id),
            )
        except sqlite3.IntegrityError as exc:
            raise ValidationError("That phone number already belongs to a customer.") from exc
        if not cur.rowcount:
            raise ValidationError("Customer not found.")
    return get_customer(customer_id)


def change_points(customer_id: int, amount: int, note: str, actor: str):
    if amount == 0 or abs(amount) > 1_000_000:
        raise ValidationError("Point change must be between -1,000,000 and 1,000,000.")
    note = clean_note(note)
    with connect() as db:
        customer = db.execute(
            "SELECT points FROM customers WHERE id = ?", (customer_id,)
        ).fetchone()
        if not customer:
            raise ValidationError("Customer not found.")
        balance = customer["points"] + amount
        if balance < 0:
            raise ValidationError("This change would make the balance negative.")
        db.execute(
            """UPDATE customers SET points = ?, updated_at = CURRENT_TIMESTAMP
               WHERE id = ?""",
            (balance, customer_id),
        )
        db.execute(
            """INSERT INTO point_history
               (customer_id, change, balance_after, note, actor)
               VALUES (?, ?, ?, ?, ?)""",
            (customer_id, amount, balance, note, actor[:80]),
        )
    return get_customer(customer_id)


def customer_history(customer_id: int, limit: int = 100):
    with connect() as db:
        rows = db.execute(
            """SELECT * FROM point_history WHERE customer_id = ?
               ORDER BY id DESC LIMIT ?""",
            (customer_id, min(max(limit, 1), 500)),
        ).fetchall()
        return [dict(row) for row in rows]


def stats():
    with connect() as db:
        row = db.execute(
            "SELECT COUNT(*) customers, COALESCE(SUM(points), 0) points FROM customers"
        ).fetchone()
        changes = db.execute(
            "SELECT COUNT(*) FROM point_history"
        ).fetchone()[0]
        return {"customers": row["customers"], "points": row["points"], "changes": changes}

