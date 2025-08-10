# utils/db.py
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
import sqlite3

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
SQLITE_PATH = os.getenv("SQLITE_PATH", "./data/resume_analyzer.db")

_engine = None

_POSTGRES_INIT_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS resumes (
    id SERIAL PRIMARY KEY,
    user_id INT,
    filename TEXT,
    content TEXT,
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS job_descriptions (
    id SERIAL PRIMARY KEY,
    user_id INT,
    filename TEXT,
    content TEXT,
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS scan_results (
    id SERIAL PRIMARY KEY,
    user_id INT,
    resume_id INT,
    job_id INT,
    match_score FLOAT,
    missing_keywords TEXT,
    matched_keywords TEXT,
    scanned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS job_tracker (
    id SERIAL PRIMARY KEY,
    user_id INT,
    job_title TEXT,
    company_name TEXT,
    application_date DATE,
    status TEXT
);
"""

def get_engine():
    """
    Returns SQLAlchemy engine if DATABASE_URL present & reachable, else None.
    """
    global _engine
    if not DATABASE_URL:
        return None
    if _engine is None:
        # ensure SSL when connecting to cloud DBs if needed
        try:
            if "sslmode" not in DATABASE_URL:
                _engine = create_engine(DATABASE_URL, future=True, connect_args={"sslmode": "require"})
            else:
                _engine = create_engine(DATABASE_URL, future=True)
        except Exception:
            _engine = None
    return _engine

def ensure_sqlite_conn():
    os.makedirs(os.path.dirname(SQLITE_PATH), exist_ok=True)
    conn = sqlite3.connect(SQLITE_PATH, check_same_thread=False)
    return conn

def init_postgres_tables(engine):
    with engine.begin() as conn:
        conn.execute(text(_POSTGRES_INIT_SQL))

def detect_db():
    """
    Return ("postgres", engine) or ("sqlite", sqlite_conn)
    """
    engine = get_engine()
    if engine:
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            # create tables if missing
            init_postgres_tables(engine)
            return ("postgres", engine)
        except OperationalError:
            # fallback to sqlite
            sqlite_conn = ensure_sqlite_conn()
            return ("sqlite", sqlite_conn)
        except Exception:
            sqlite_conn = ensure_sqlite_conn()
            return ("sqlite", sqlite_conn)
    else:
        sqlite_conn = ensure_sqlite_conn()
        return ("sqlite", sqlite_conn)
