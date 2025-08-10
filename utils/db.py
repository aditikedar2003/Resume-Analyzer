# File: utils/db.py
"""
utils/db.py
Database detection and helpers. Exports:
- get_engine()
- ensure_sqlite_conn()
- detect_db() -> ("postgres", engine) or ("sqlite", sqlite_conn)
"""
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
import sqlite3

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
SQLITE_PATH = os.getenv("SQLITE_PATH", "./data/resume_analyzer.db")

_engine = None

def get_engine():
    global _engine
    if not DATABASE_URL:
        return None
    if _engine is None:
        # create engine once
        try:
            # add sslmode=require for many cloud Postgres providers. If connection fails, it will fallback.
            _engine = create_engine(DATABASE_URL, future=True, connect_args={"sslmode": "require"})
        except Exception:
            _engine = create_engine(DATABASE_URL, future=True)
    return _engine

def ensure_sqlite_conn():
    os.makedirs(os.path.dirname(SQLITE_PATH), exist_ok=True)
    conn = sqlite3.connect(SQLITE_PATH, check_same_thread=False)
    return conn

# SQL table creation scripts (Postgres flavor)
_CREATE_TABLES = [
"""
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""",
"""
CREATE TABLE IF NOT EXISTS resumes (
    id SERIAL PRIMARY KEY,
    user_id INT,
    filename TEXT,
    content TEXT,
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""",
"""
CREATE TABLE IF NOT EXISTS job_descriptions (
    id SERIAL PRIMARY KEY,
    user_id INT,
    filename TEXT,
    content TEXT,
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""",
"""
CREATE TABLE IF NOT EXISTS scan_results (
    id SERIAL PRIMARY KEY,
    user_id INT,
    resume_id INT,
    job_id INT,
    match_score FLOAT,
    missing_keywords TEXT,
    matched_keywords TEXT,
    scanned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""",
"""
CREATE TABLE IF NOT EXISTS job_tracker (
    id SERIAL PRIMARY KEY,
    user_id INT,
    job_title TEXT,
    company_name TEXT,
    application_date DATE,
    status TEXT DEFAULT 'Applied'
)
""",
"""
CREATE TABLE IF NOT EXISTS feedback (
    id SERIAL PRIMARY KEY,
    user_id INT,
    feedback TEXT,
    submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
"""
]

def init_postgres_tables(engine):
    # create required tables if missing
    with engine.begin() as conn:
        for stmt in _CREATE_TABLES:
            conn.execute(text(stmt))

def detect_db():
    """
    Returns ("postgres", engine) or ("sqlite", sqlite_conn)
    """
    engine = get_engine()
    if engine:
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            # ensure tables exist
            init_postgres_tables(engine)
            return ("postgres", engine)
        except OperationalError:
            # Postgres unreachable, fallback to sqlite
            sqlite_conn = ensure_sqlite_conn()
            return ("sqlite", sqlite_conn)
        except Exception:
            sqlite_conn = ensure_sqlite_conn()
            return ("sqlite", sqlite_conn)
    else:
        sqlite_conn = ensure_sqlite_conn()
        return ("sqlite", sqlite_conn)
