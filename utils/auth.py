import sqlite3
from passlib.hash import bcrypt
from utils.db import get_db
from sqlalchemy import text

# Register a user; returns (True, msg) or (False, msg)
def register_user(name, email, password):
    db_type, db = get_db()
    hashed = bcrypt.hash(password)
    if db_type == 'postgres':
        engine = db
        with engine.begin() as conn:
            exists = conn.execute(text("SELECT id FROM users WHERE email = :email"), {"email": email}).fetchone()
            if exists:
                return False, 'Email already registered.'
            conn.execute(text("INSERT INTO users (name, email, password) VALUES (:name, :email, :pwd)"),
                         {"name": name, "email": email, "pwd": hashed})
            return True, 'Registration successful.'
    else:
        conn = db
        cur = conn.cursor()
        cur.execute("SELECT id FROM users WHERE email = ?", (email,))
        if cur.fetchone():
            return False, 'Email already registered.'
        cur.execute("INSERT INTO users (name, email, password) VALUES (?, ?, ?)", (name, email, hashed))
        conn.commit()
        return True, 'Registration successful.'

# Login; returns (True, user_dict) or (False, msg)
def login_user(email, password):
    db_type, db = get_db()
    if db_type == 'postgres':
        engine = db
        with engine.connect() as conn:
            row = conn.execute(text("SELECT id, password, name FROM users WHERE email = :email"), {"email": email}).fetchone()
            if not row:
                return False, 'No such user.'
            user_id, hashed, name = row
            if bcrypt.verify(password, hashed):
                return True, {"id": user_id, "name": name, "email": email}
            return False, 'Invalid credentials.'
    else:
        conn = db
        cur = conn.cursor()
        cur.execute("SELECT id, password, name FROM users WHERE email = ?", (email,))
        row = cur.fetchone()
        if not row:
            return False, 'No such user.'
        user_id, hashed, name = row
        if bcrypt.verify(password, hashed):
            return True, {"id": user_id, "name": name, "email": email}
        return False, 'Invalid credentials.'
