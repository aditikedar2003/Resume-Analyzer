# utils/auth.py
import sqlite3
from passlib.hash import bcrypt
from utils.db import get_engine, ensure_sqlite_conn
from sqlalchemy import text

def _ensure_users_sqlite(conn: sqlite3.Connection):
    conn.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)
    conn.commit()

def register_user(name: str, email: str, password: str):
    """
    Returns (True, message) or (False, message)
    """
    hashed = bcrypt.hash(password)
    engine = get_engine()
    if engine:
        try:
            with engine.begin() as conn:
                existing = conn.execute(text("SELECT id FROM users WHERE email = :email"), {"email": email}).fetchone()
                if existing:
                    return False, "Email already registered."
                conn.execute(text("INSERT INTO users (name, email, password) VALUES (:name, :email, :pwd)"),
                             {"name": name, "email": email, "pwd": hashed})
            return True, "Registration successful."
        except Exception as e:
            return False, f"Registration failed: {e}"
    else:
        conn = ensure_sqlite_conn()
        _ensure_users_sqlite(conn)
        cur = conn.cursor()
        cur.execute("SELECT id FROM users WHERE email = ?", (email,))
        if cur.fetchone():
            return False, "Email already registered."
        cur.execute("INSERT INTO users (name, email, password) VALUES (?, ?, ?)", (name, email, hashed))
        conn.commit()
        return True, "Registration successful."

def login_user(email: str, password: str):
    """
    Returns (True, user_dict) or (False, message)
    user_dict = {"id": id, "name": name, "email": email}
    """
    engine = get_engine()
    if engine:
        try:
            with engine.connect() as conn:
                r = conn.execute(text("SELECT id, password, name FROM users WHERE email = :email"), {"email": email}).fetchone()
                if not r:
                    return False, "No such user."
                user_id, hashed, name = r
                if bcrypt.verify(password, hashed):
                    return True, {"id": int(user_id), "name": name, "email": email}
                return False, "Invalid credentials."
        except Exception as e:
            return False, f"Login failed: {e}"
    else:
        conn = ensure_sqlite_conn()
        _ensure_users_sqlite(conn)
        cur = conn.cursor()
        cur.execute("SELECT id, password, name FROM users WHERE email = ?", (email,))
        row = cur.fetchone()
        if not row:
            return False, "No such user."
        user_id, hashed, name = row
        if bcrypt.verify(password, hashed):
            return True, {"id": int(user_id), "name": name, "email": email}
        return False, "Invalid credentials."
