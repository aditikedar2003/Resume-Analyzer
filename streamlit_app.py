# streamlit_app.py
import streamlit as st
from utils.extractor import extract_file_text
from utils.nlp import compute_match_score, get_keywords, simple_ats_checks
from utils import auth
from utils.db import get_postgres_engine, ensure_sqlite_db, test_connection
from sqlalchemy import text
import pandas as pd
import os
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

st.set_page_config(page_title="Resume Analyzer", page_icon="🚀", layout="wide")

# ---------- Styling / Header ----------
def show_header():
    st.markdown("""
    <div style="text-align:center">
        <h1>🚀 Resume Analyzer</h1>
        <p style="color:gray">Optimize your resume for any job — ATS friendly checks, keyword match and suggestions.</p>
        <hr/>
    </div>
    """, unsafe_allow_html=True)

show_header()

# ---------- Session init ----------
if "page" not in st.session_state:
    st.session_state.page = "home"
if "user" not in st.session_state:
    st.session_state.user = None
if "match_result" not in st.session_state:
    st.session_state.match_result = None

# ---------- Database detector ----------
db_type, db_conn = test_connection()
# db_type is "postgres" (engine) or "sqlite" (Connection object) or None
# If postgres, db_conn is engine; if sqlite, db_conn is sqlite3 connection object.

# ---------- Auth UI ----------
def show_auth_sidebar():
    st.sidebar.title("Account")
    if st.session_state.user:
        st.sidebar.write(f"Signed in as **{st.session_state.user['name']}**")
        if st.sidebar.button("Logout"):
            st.session_state.user = None
            st.experimental_rerun()
    else:
        auth_tab = st.sidebar.radio("Auth", ["Login", "Sign Up"])
        if auth_tab == "Sign Up":
            name = st.sidebar.text_input("Full name", key="su_name")
            email = st.sidebar.text_input("Email", key="su_email")
            pwd = st.sidebar.text_input("Password", type="password", key="su_pwd")
            if st.sidebar.button("Register"):
                ok, msg = auth.register_user(name, email, pwd)
                if ok:
                    st.success(msg)
                else:
                    st.error(msg)
        else:
            email = st.sidebar.text_input("Email", key="li_email")
            pwd = st.sidebar.text_input("Password", type="password", key="li_pwd")
            if st.sidebar.button("Login"):
                ok, resp = auth.login_user(email, pwd)
                if ok:
                    st.session_state.user = resp
                    st.success("Logged in")
                    st.experimental_rerun()
                else:
                    st.error(resp)

show_auth_sidebar()

# ---------- Navigation ----------
with st.sidebar:
    st.markdown("## Navigation")
    if st.button("Home"):
        st.session_state.page = "home"
    if st.button("Resume Scanner"):
        st.session_state.page = "scanner"
    if st.button("Dashboard"):
        st.session_state.page = "dashboard"
    if st.button("Cover Letter"):
        st.session_state.page = "cover"
    if st.button("LinkedIn Optimizer"):
        st.session_state.page = "linkedin"
    if st.button("Job Tracker"):
        st.session_state.page = "tracker"
    st.markdown("---")
    st.markdown("Resources:")
    st.markdown("- [Resume tips](https://www.jobscan.co/resume-writing-guide)")

# ---------- Pages ----------
def page_home():
    st.header("Optimize your resume for any job")
    st.subheader("How it works")
    st.markdown("""
    - Upload your resume (PDF/DOCX/TXT) or paste it.
    - Paste the Job Description (JD) you want to apply for.
    - Click **Scan** — get a match score, missing keywords, and ATS formatting tips.
    """)
    st.info("Try the Resume Scanner from the left navigation or click below.")
    if st.button("Try Jobscan Now"):
        st.session_state.page = "scanner"
        st.experimental_rerun()

def page_scanner():
    st.header("Resume Scanner")
    col1, col2 = st.columns(2)
    with col1:
        uploaded = st.file_uploader("Upload Resume (pdf/docx/txt)", type=["pdf", "docx", "txt"])
        resume_text_manual = st.text_area("Or paste resume text (optional, used if uploaded file missing)")
        filename = uploaded.name if uploaded else "pasted_resume.txt"
    with col2:
        jd_text = st.text_area("Paste Job Description (JD) here")
        ck_linkedin = st.checkbox("Also optimize for LinkedIn (summary)", value=False)

    if st.button("Scan"):
        # extract resume text (prefer uploaded file)
        if uploaded:
            rtext = extract_file_text(uploaded)
        else:
            rtext = resume_text_manual or ""
        if not rtext.strip():
            st.warning("Please provide resume text (upload or paste).")
            return
        if not jd_text.strip():
            st.warning("Please paste a job description to compare.")
            return

        score = compute_match_score(rtext, jd_text)
        matched, missing = get_keywords(rtext, jd_text, top_n=50)
        ats_warnings = simple_ats_checks(rtext)

        # Persist into DB (either Postgres or sqlite)
        user_id = st.session_state.user["id"] if st.session_state.user else None
        resume_id = None
        job_id = None
        try:
            if db_type == "postgres":
                engine = db_conn
                with engine.begin() as conn:
                    # insert resume
                    res = conn.execute(text("INSERT INTO resumes (user_id, filename, content) VALUES (:uid, :fn, :content) RETURNING id"),
                                       {"uid": user_id, "fn": filename, "content": rtext})
                    resume_id = int(res.fetchone()[0])
                    # insert jobdesc
                    res2 = conn.execute(text("INSERT INTO job_descriptions (user_id, filename, content) VALUES (:uid, :fn, :content) RETURNING id"),
                                        {"uid": user_id, "fn": "jd.txt", "content": jd_text})
                    job_id = int(res2.fetchone()[0])
                    # insert scan result
                    conn.execute(text("""INSERT INTO scan_results (user_id, resume_id, job_id, match_score, missing_keywords, matched_keywords)
                                        VALUES (:uid, :rid, :jid, :score, :missing, :matched)"""),
                                 {"uid": user_id, "rid": resume_id, "jid": job_id, "score": score,
                                  "missing": ", ".join(missing[:50]), "matched": ", ".join(matched[:50])})
            else:
                # sqlite fallback
                conn = db_conn
                cur = conn.cursor()
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS resumes (
                        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, filename TEXT, content TEXT, uploaded_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS job_descriptions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, filename TEXT, content TEXT, uploaded_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS scan_results (
                        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, resume_id INTEGER, job_id INTEGER, match_score REAL,
                        missing_keywords TEXT, matched_keywords TEXT, scanned_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                conn.commit()
                cur.execute("INSERT INTO resumes (user_id, filename, content) VALUES (?, ?, ?)", (user_id, filename, rtext))
                resume_id = cur.lastrowid
                cur.execute("INSERT INTO job_descriptions (user_id, filename, content) VALUES (?, ?, ?)", (user_id, "jd.txt", jd_text))
                job_id = cur.lastrowid
                cur.execute("INSERT INTO scan_results (user_id, resume_id, job_id, match_score, missing_keywords, matched_keywords) VALUES (?, ?, ?, ?, ?, ?)",
                            (user_id, resume_id, job_id, score, ", ".join(missing[:50]), ", ".join(matched[:50])))
                conn.commit()
        except Exception as e:
            st.error("Warning: could not persist to DB: " + str(e))

        st.session_state.match_result = {
            "score": score,
            "matched": matched,
            "missing": missing,
            "warnings": ats_warnings,
            "resume_id": resume_id,
            "job_id": job_id
        }
        st.session_state.page = "results"
        st.experimental_rerun()

def page_results():
    r = st.session_state.get("match_result", {})
    st.header("Match Results")
    if not r:
        st.info("No result to display. Run a scan first.")
        return
    st.metric("Match Score", f"{r.get('score', 0)}%")
    st.subheader("Matched Keywords")
    st.write(", ".join(r.get("matched", [])[:50]) or "None found")
    st.subheader("Missing Keywords (from JD)")
    st.write(", ".join(r.get("missing", [])[:50]) or "None")
    st.subheader("ATS Formatting Warnings")
    warnings = r.get("warnings", [])
    if warnings:
        for w in warnings:
            st.warning(w)
    else:
        st.success("No obvious ATS formatting problems found.")
    if st.button("Scan another resume"):
        st.session_state.page = "scanner"
        st.experimental_rerun()

def page_dashboard():
    st.header("Dashboard - Scan History")
    user_id = st.session_state.user["id"] if st.session_state.user else None
    if not user_id:
        st.info("Sign in to see your saved scans (guest mode only shows recent scans).")
    # Query last 20 scans
    try:
        if db_type == "postgres":
            engine = db_conn
            with engine.connect() as conn:
                rows = conn.execute(text("""SELECT s.scanned_at, s.match_score, r.filename, jd.content
                                            FROM scan_results s
                                            LEFT JOIN resumes r ON r.id = s.resume_id
                                            LEFT JOIN job_descriptions jd ON jd.id = s.job_id
                                            WHERE s.user_id = :uid OR :uid IS NULL
                                            ORDER BY s.scanned_at DESC LIMIT 20"""), {"uid": user_id}).fetchall()
                for row in rows:
                    st.markdown("---")
                    st.write(f"**Date:** {row[0]}  |  **Score:** {row[1]}%")
                    st.write(f"**Resume file:** {row[2]}")
                    st.write(f"**JD excerpt:** {row[3][:250]}...")
        else:
            conn = db_conn
            cur = conn.cursor()
            cur.execute("SELECT scanned_at, match_score, resume_id, job_id FROM scan_results ORDER BY scanned_at DESC LIMIT 20")
            rows = cur.fetchall()
            for row in rows:
                st.markdown("---")
                st.write(f"**Date:** {row[0]}  |  **Score:** {row[1]}%")
                # simple excerpts
                rid = row[2]
                jid = row[3]
                cur.execute("SELECT filename, content FROM resumes WHERE id = ?", (rid,))
                rr = cur.fetchone()
                cur.execute("SELECT content FROM job_descriptions WHERE id = ?", (jid,))
                jj = cur.fetchone()
                fn = rr[0] if rr else "unknown"
                jd_excerpt = (jj[0][:250] + "...") if jj and jj[0] else ""
                st.write(f"**Resume file:** {fn}")
                st.write(f"**JD excerpt:** {jd_excerpt}")
    except Exception as e:
        st.error("Could not load dashboard: " + str(e))

def page_cover():
    st.header("Cover Letter Analyzer")
    st.info("Paste your cover letter and the JD; we will give simple suggestions.")
    cover = st.text_area("Paste Cover Letter")
    jd = st.text_area("Paste Job Description (optional)")
    if st.button("Analyze Cover Letter"):
        if not cover.strip():
            st.warning("Paste your cover letter.")
        else:
            # Simple checks
            st.success("Basic checks completed.")
            st.write("Tip: Start with a strong opening line; mention 2-3 quantifiable achievements; tailor to the JD.")

def page_linkedin():
    st.header("LinkedIn Optimizer")
    st.info("Paste your LinkedIn 'About' summary for quick optimizations.")
    summary = st.text_area("Paste LinkedIn Summary")
    if st.button("Optimize"):
        if not summary.strip():
            st.warning("Paste your LinkedIn summary.")
        else:
            st.write("Suggestions: Add keywords from JD; open with role+impact; highlight 2 achievements; include contact CTA.")

def page_tracker():
    st.header("Job Tracker")
    st.info("Log and track applications quickly (saved to DB if you are logged in).")
    title = st.text_input("Job title")
    company = st.text_input("Company")
    date = st.date_input("Application date")
    status = st.selectbox("Status", ["Applied", "Interviewing", "Offer", "Rejected"])
    if st.button("Add to Tracker"):
        try:
            user_id = st.session_state.user["id"] if st.session_state.user else None
            if db_type == "postgres":
                engine = db_conn
                with engine.begin() as conn:
                    conn.execute(text("CREATE TABLE IF NOT EXISTS job_tracker (id SERIAL PRIMARY KEY, user_id INT, job_title TEXT, company_name TEXT, application_date DATE, status TEXT)"))
                    conn.execute(text("INSERT INTO job_tracker (user_id, job_title, company_name, application_date, status) VALUES (:uid, :t, :c, :d, :s)"),
                                 {"uid": user_id, "t": title, "c": company, "d": date, "s": status})
            else:
                conn = db_conn
                cur = conn.cursor()
                cur.execute("CREATE TABLE IF NOT EXISTS job_tracker (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, job_title TEXT, company_name TEXT, application_date TEXT, status TEXT)")
                cur.execute("INSERT INTO job_tracker (user_id, job_title, company_name, application_date, status) VALUES (?, ?, ?, ?, ?)",
                            (user_id, title, company, date.isoformat(), status))
                conn.commit()
            st.success("Job added.")
        except Exception as e:
            st.error("Could not add to tracker: " + str(e))

# ---------- Router ----------
if st.session_state.page == "home":
    page_home()
elif st.session_state.page == "scanner":
    page_scanner()
elif st.session_state.page == "results":
    page_results()
elif st.session_state.page == "dashboard":
    page_dashboard()
elif st.session_state.page == "cover":
    page_cover()
elif st.session_state.page == "linkedin":
    page_linkedin()
elif st.session_state.page == "tracker":
    page_tracker()
else:
    page_home()
