import streamlit as st
from .db import get_connection
import hashlib

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def register_user(name, email, password):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO users (name, email, password) VALUES (%s, %s, %s)",
                (name, email, hash_password(password)))
    conn.commit()
    cur.close()
    conn.close()

def login_user(email, password):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE email=%s AND password=%s",
                (email, hash_password(password)))
    user = cur.fetchone()
    cur.close()
    conn.close()
    return user
