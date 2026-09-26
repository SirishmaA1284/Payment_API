import os
import sqlite3
from pathlib import Path

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "payments.db"


def _db_path() -> str:
    return os.environ.get("PAYMENTS_DB_PATH", str(DEFAULT_DB_PATH))


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(_db_path())
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = get_connection()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                amount REAL NOT NULL,
                tax REAL NOT NULL,
                discount REAL NOT NULL,
                total REAL NOT NULL
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def create_payment(amount: float, tax: float, discount: float, total: float) -> int:
    conn = get_connection()
    try:
        cursor = conn.execute(
            "INSERT INTO payments (amount, tax, discount, total) VALUES (?, ?, ?, ?)",
            (amount, tax, discount, total),
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def get_payment(payment_id: int):
    conn = get_connection()
    try:
        cursor = conn.execute("SELECT * FROM payments WHERE id = ?", (payment_id,))
        return cursor.fetchone()
    finally:
        conn.close()
