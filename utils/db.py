import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
import sqlite3

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
SQLITE_PATH = os.getenv("SQLITE_PATH", "./data/resume_analyzer.db")

# Return either ('postgres', engine) or ('sqlite', sqlite_conn)
def detect_db():
    if DATABASE_URL:
        try:
            engine = create_engine(DATABASE_URL, future=True)
            # quick check
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return ("postgres", engine)
        except Exception as e:
            print("Postgres detect failed:", e)
            # fallback to sqlite
    # sqlite fallback
    os.makedirs(os.path.dirname(SQLITE_PATH), exist_ok=True)
    conn = sqlite3.connect(SQLITE_PATH, check_same_thread=False)
    return ("sqlite", conn)

# Helper to create core tables if missing (for sqlite fallback)
def init_sqlite_tables(conn):
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS resumes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        filename TEXT,
        content TEXT,
        uploaded_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS job_descriptions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        filename TEXT,
        content TEXT,
        uploaded_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS scan_results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        resume_id INTEGER,
        job_id INTEGER,
        match_score REAL,
        matched_keywords TEXT,
        missing_keywords TEXT,
        scanned_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS job_tracker (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        job_title TEXT,
        company_name TEXT,
        application_date TEXT,
        status TEXT
    )
    """)
    conn.commit()

# convenience function to return the db object (engine or conn)
def get_db():
    db_type, db_obj = detect_db()
    if db_type == 'sqlite':
        init_sqlite_tables(db_obj)
    return db_type, db_obj
