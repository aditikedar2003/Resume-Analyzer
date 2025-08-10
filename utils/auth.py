### FILE: utils/auth.py
# utils/auth.py
import sqlite3
from passlib.hash import bcrypt
from utils.db import get_db
from sqlalchemy import text
import streamlit as st

def register_user(name, email, password):
    """
    Insert a new user into DB. Returns (True, message) or (False, message).
    """
    db_type, db = get_db()
    hashed = bcrypt.hash(password)
    if db_type == "postgres":
        engine = db
        with engine.begin() as conn:
            exists = conn.execute(text("SELECT id FROM users WHERE email = :email"), {"email": email}).fetchone()
            if exists:
                return False, "Email already registered."
            conn.execute(text("INSERT INTO users (name, email, password) VALUES (:name, :email, :pwd)"),
                         {"name": name, "email": email, "pwd": hashed})
            return True, "Registration successful."
    else:
        conn = db
        cur = conn.cursor()
        cur.execute("SELECT id FROM users WHERE email = ?", (email,))
        if cur.fetchone():
            return False, "Email already registered."
        cur.execute("INSERT INTO users (name, email, password) VALUES (?, ?, ?)", (name, email, hashed))
        conn.commit()
        return True, "Registration successful."


def login_user(email, password):
    """
    Attempt login. Returns (True, user_dict) or (False, message).
    user_dict = {"id": id, "name": name, "email": email}
    """
    db_type, db = get_db()
    if db_type == "postgres":
        engine = db
        with engine.connect() as conn:
            row = conn.execute(text("SELECT id, password, name FROM users WHERE email = :email"), {"email": email}).fetchone()
            if not row:
                return False, "No such user."
            user_id, hashed, name = row
            if bcrypt.verify(password, hashed):
                return True, {"id": int(user_id), "name": name, "email": email}
            return False, "Invalid credentials."
    else:
        conn = db
        cur = conn.cursor()
        cur.execute("SELECT id, password, name FROM users WHERE email = ?", (email,))
        row = cur.fetchone()
        if not row:
            return False, "No such user."
        user_id, hashed, name = row
        if bcrypt.verify(password, hashed):
            return True, {"id": int(user_id), "name": name, "email": email}
        return False, "Invalid credentials."


# wrapper compatibility for previous naming
def signup(name, email, password):
    return register_user(name, email, password)

def login(email, password):
    return login_user(email, password)

def logout():
    # clear session state
    for k in list(st.session_state.keys()):
        st.session_state.pop(k, None)

def is_authenticated():
    return st.session_state.get("user") is not None
