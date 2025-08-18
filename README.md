# Resume Analyzer url- https://resume-analyzer-prolevel.streamlit.app/

A Streamlit-based Resume Analyzer: Upload resume and job description, get a TF-IDF match score, matched/missing keywords, basic ATS formatting checks, scan history, and simple account auth. Works with Postgres (Render) or SQLite fallback.

## Quick start (local)
1. Copy files into project folder.
2. Create virtualenv: `python -m venv .venv && .\.venv\Scripts\activate` (Windows) or `source .venv/bin/activate` (mac/linux)
3. Install: `pip install -r requirements.txt`
4. Copy `.env.example` to `.env` and fill `DATABASE_URL` (or leave blank to use SQLite fallback).
5. If using Postgres, run `schema.sql` against your DB.
6. Run: `streamlit run streamlit_app.py`
7. Open `http://localhost:8501`.

## Render Postgres (your DB)
Use the Render connection info to fill `.env` like:
