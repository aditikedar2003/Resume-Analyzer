### FILE: utils/db.py
# utils/db.py
import os
import sqlite3
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
SQLITE_PATH = os.getenv("SQLITE_PATH", "./data/resume_analyzer.db")


def _create_sqlite_dir():
    os.makedirs(os.path.dirname(SQLITE_PATH), exist_ok=True)


def get_db():
    """
    Returns a tuple ('postgres', engine) or ('sqlite', sqlite3.Connection)
    """
    if DATABASE_URL:
        # SQLAlchemy expects postgresql:// not postgres:// in some environments
        db_url = DATABASE_URL
        if db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql://", 1)
        engine = create_engine(db_url, future=True)
        try:
            # quick test
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return "postgres", engine
        except OperationalError:
            # if postgres provided but cannot connect, fallback to sqlite
            pass

    # sqlite fallback
    _create_sqlite_dir()
    conn = sqlite3.connect(SQLITE_PATH, check_same_thread=False)
    return "sqlite", conn


def init_db():
    """
    Create minimal tables automatically if they don't exist.
    Works for both Postgres (via SQLAlchemy) and SQLite.
    """
    db_type, db = get_db()
    if db_type == "postgres":
        engine = db
        with engine.begin() as conn:
            conn.execute(text("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                email VARCHAR(100) UNIQUE NOT NULL,
                password TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """))
            conn.execute(text("""
            CREATE TABLE IF NOT EXISTS resumes (
                id SERIAL PRIMARY KEY,
                user_id INT REFERENCES users(id),
                filename TEXT NOT NULL,
                content TEXT,
                uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """))
            conn.execute(text("""
            CREATE TABLE IF NOT EXISTS job_descriptions (
                id SERIAL PRIMARY KEY,
                user_id INT REFERENCES users(id),
                filename TEXT NOT NULL,
                content TEXT,
                uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """))
            conn.execute(text("""
            CREATE TABLE IF NOT EXISTS scan_results (
                id SERIAL PRIMARY KEY,
                user_id INT,
                resume_id INT REFERENCES resumes(id),
                job_id INT REFERENCES job_descriptions(id),
                match_score FLOAT,
                matched_keywords TEXT,
                missing_keywords TEXT,
                scanned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """))
            conn.execute(text("""
            CREATE TABLE IF NOT EXISTS job_tracker (
                id SERIAL PRIMARY KEY,
                user_id INT REFERENCES users(id),
                job_title TEXT NOT NULL,
                company_name TEXT,
                application_date DATE,
                status TEXT DEFAULT 'Applied'
            );
            """))
    else:
        conn = db
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
            filename TEXT NOT NULL,
            content TEXT,
            uploaded_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS job_descriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            filename TEXT NOT NULL,
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
