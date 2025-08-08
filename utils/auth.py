# utils/auth.py
import streamlit as st
from passlib.hash import bcrypt
from utils.db import get_postgres_engine, ensure_sqlite_db
from sqlalchemy import text
import sqlite3
import os

def _create_users_table_sqlite(conn: sqlite3.Connection):
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

def register_user(name, email, password):
    engine = get_postgres_engine()
    hashed = bcrypt.hash(password)
    if engine:
        with engine.begin() as conn:
            res = conn.execute(text("SELECT id FROM users WHERE email = :email"), {"email": email}).fetchone()
            if res:
                return False, "Email already registered."
            conn.execute(text("INSERT INTO users (name, email, password) VALUES (:name, :email, :password)"),
                         {"name": name, "email": email, "password": hashed})
            return True, "Registration successful."
    else:
        conn = ensure_sqlite_db()
        _create_users_table_sqlite(conn)
        cur = conn.cursor()
        cur.execute("SELECT id FROM users WHERE email = ?", (email,))
        if cur.fetchone():
            return False, "Email already registered."
        cur.execute("INSERT INTO users (name, email, password) VALUES (?, ?, ?)", (name, email, hashed))
        conn.commit()
        return True, "Registration successful."

def login_user(email, password):
    engine = get_postgres_engine()
    if engine:
        with engine.connect() as conn:
            r = conn.execute(text("SELECT id, password, name FROM users WHERE email = :email"), {"email": email}).fetchone()
            if not r:
                return False, "No such user."
            user_id, hashed, name = r
            if bcrypt.verify(password, hashed):
                return True, {"id": user_id, "name": name, "email": email}
            return False, "Invalid credentials."
    else:
        conn = ensure_sqlite_db()
        _create_users_table_sqlite(conn)
        cur = conn.cursor()
        cur.execute("SELECT id, password, name FROM users WHERE email = ?", (email,))
        row = cur.fetchone()
        if not row:
            return False, "No such user."
        user_id, hashed, name = row
        if bcrypt.verify(password, hashed):
            return True, {"id": user_id, "name": name, "email": email}
        return False, "Invalid credentials."
