# utils/db.py
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
import sqlite3

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
SQLITE_PATH = os.getenv("SQLITE_PATH", "./data/resume_analyzer.db")

def get_postgres_engine():
    if DATABASE_URL:
        engine = create_engine(DATABASE_URL, future=True)
        return engine
    return None

def ensure_sqlite_db():
    os.makedirs(os.path.dirname(SQLITE_PATH), exist_ok=True)
    conn = sqlite3.connect(SQLITE_PATH, check_same_thread=False)
    return conn

def test_connection():
    engine = get_postgres_engine()
    if engine:
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return ("postgres", engine)
        except OperationalError:
            return (None, None)
    else:
        sqlite_conn = ensure_sqlite_db()
        return ("sqlite", sqlite_conn)
