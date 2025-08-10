# File: streamlit_app.py
"""
Main Streamlit app. Single-file UI + routing.
Header navigation (no left sidebar). Auth expander in header.
"""
import streamlit as st
from utils.extractor import extract_file_text
from utils.nlp import compute_match_score, get_keywords, simple_ats_checks
import utils.auth as auth
from utils.db import detect_db
from sqlalchemy import text
from dotenv import load_dotenv
import os

load_dotenv()

st.set_page_config(page_title="Resume Analyzer Pro", page_icon="🚀", layout="wide")

# DB detection (engine or sqlite conn)
db_type, db_conn = detect_db()

# Session defaults
if "page" not in st.session_state:
    st.session_state.page = "home"
if "user" not in st.session_state:
    st.session_state.user = None
if "show_auth" not in st.session_state:
    st.session_state.show_auth = False
if "match_result" not in st.session_state:
    st.session_state.match_result = None

# Header
col_logo, col_title, col_actions = st.columns([1,6,2])
with col_logo:
    st.image("https://via.placeholder.com/72", width=72)
with col_title:
    st.markdown("<h1 style='margin:0'>Resume Analyzer Pro</h1>", unsafe_allow_html=True)
    st.markdown("<div style='color:gray'>Optimize your resume for any job — ATS checks & keyword match.</div>", unsafe_allow_html=True)
with col_actions:
    if st.session_state.user:
        st.write(f"Signed in: **{st.session_state.user['name']}**")
        if st.button("Logout"):
            st.session_state.user = None
            st.experimental_rerun()
    else:
        if st.button("Login / Sign Up"):
            st.session_state.show_auth = True

# Auth expander below header
if st.session_state.show_auth:
    with st.expander("Account"):
        tabs = st.tabs(["Login", "Sign Up"])
        with tabs[0]:
            le = st.text_input("Email", key="login_email")
            lp = st.text_input("Password", type="password", key="login_pwd")
            if st.button("Sign in"):
                ok, resp = auth.login_user(le, lp)
                if ok:
                    st.session_state.user = resp
                    st.session_state.show_auth = False
                    st.success("Logged in")
                    st.experimental_rerun()
                else:
                    st.error(resp)
        with tabs[1]:
            sn = st.text_input("Full name", key="su_name")
            se = st.text_input("Email", key="su_email")
            sp = st.text_input("Password", type="password", key="su_pwd")
            if st.button("Register"):
                ok, msg = auth.register_user(sn, se, sp)
                if ok:
                    st.success("Registered successfully — logging you in...")
                    ok2, user = auth.login_user(se, sp)
                    if ok2:
                        st.session_state.user = user
                        st.session_state.show_auth = False
                        st.experimental_rerun()
                    else:
                        st.info("Please login now.")
                else:
                    st.error(msg)

# Navigation bar (header style)
nav_cols = st.columns(5)
if nav_cols[0].button("Home"):
    st.session_state.page = "home"
    st.experimental_rerun()
if nav_cols[1].button("Scanner"):
    st.session_state.page = "scanner"
    st.experimental_rerun()
if nav_cols[2].button("Dashboard"):
    st.session_state.page = "dashboard"
    st.experimental_rerun()
if nav_cols[3].button("Cover Letter"):
    st.session_state.page = "cover"
    st.experimental_rerun()
if nav_cols[4].button("LinkedIn"):
    st.session_state.page = "linkedin"
    st.experimental_rerun()

# Pages
def page_home():
    st.header("Optimize your resume for any job")
    st.markdown("""
    - Upload resume (PDF/DOCX/TXT) or paste text.
    - Paste the Job Description (JD).
    - Click **Scan** to get match score, missing keywords, and ATS tips.
    """)
    if st.button("Try Scanner"):
        st.session_state.page = "scanner"
        st.experimental_rerun()

def page_scanner():
    st.header("Resume Scanner")
    c1, c2 = st.columns([1,1])
    with c1:
        uploaded = st.file_uploader("Upload Resume (pdf/docx/txt)", type=["pdf","docx","txt"])
        manual = st.text_area("Or paste resume text (optional)", height=240)
    with c2:
        jd_text = st.text_area("Paste Job Description (JD) here", height=400)
        if st.button("Scan"):
            resume_text = extract_file_text(uploaded) if uploaded else (manual or "").strip()
            if not resume_text:
                st.warning("Please provide resume text (upload or paste).")
                return
            if not jd_text.strip():
                st.warning("Please paste a job description to compare.")
                return
            score = compute_match_score(resume_text, jd_text)
            matched, missing = get_keywords(resume_text, jd_text, top_n=200)
            warnings = simple_ats_checks(resume_text)

            # Persist (non-fatal)
            try:
                if db_type == "postgres":
                    engine = db_conn
                    with engine.begin() as conn:
                        r = conn.execute(text("INSERT INTO resumes (user_id, filename, content) VALUES (:uid, :fn, :content) RETURNING id"),
                                         {"uid": st.session_state.user["id"] if st.session_state.user else None, "fn": (uploaded.name if uploaded else "pasted"), "content": resume_text})
                        resume_id = int(r.fetchone()[0])
                        r2 = conn.execute(text("INSERT INTO job_descriptions (user_id, filename, content) VALUES (:uid, :fn, :content) RETURNING id"),
                                          {"uid": st.session_state.user["id"] if st.session_state.user else None, "fn": "jd.txt", "content": jd_text})
                        job_id = int(r2.fetchone()[0])
                        conn.execute(text("INSERT INTO scan_results (user_id, resume_id, job_id, match_score, missing_keywords, matched_keywords) VALUES (:uid, :rid, :jid, :score, :missing, :matched)"),
                                     {"uid": st.session_state.user["id"] if st.session_state.user else None, "rid": resume_id, "jid": job_id, "score": score, "missing": ", ".join(missing[:200]), "matched": ", ".join(matched[:200])})
                else:
                    conn = db_conn
                    cur = conn.cursor()
                    cur.execute("CREATE TABLE IF NOT EXISTS resumes (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, filename TEXT, content TEXT, uploaded_at TEXT DEFAULT CURRENT_TIMESTAMP)")
                    cur.execute("CREATE TABLE IF NOT EXISTS job_descriptions (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, filename TEXT, content TEXT, uploaded_at TEXT DEFAULT CURRENT_TIMESTAMP)")
                    cur.execute("CREATE TABLE IF NOT EXISTS scan_results (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, resume_id INTEGER, job_id INTEGER, match_score REAL, missing_keywords TEXT, matched_keywords TEXT, scanned_at TEXT DEFAULT CURRENT_TIMESTAMP)")
                    conn.commit()
                    cur.execute("INSERT INTO resumes (user_id, filename, content) VALUES (?, ?, ?)", (st.session_state.user["id"] if st.session_state.user else None, (uploaded.name if uploaded else "pasted"), resume_text))
                    resume_id = cur.lastrowid
                    cur.execute("INSERT INTO job_descriptions (user_id, filename, content) VALUES (?, ?, ?)", (st.session_state.user["id"] if st.session_state.user else None, "jd.txt", jd_text))
                    job_id = cur.lastrowid
                    cur.execute("INSERT INTO scan_results (user_id, resume_id, job_id, match_score, missing_keywords, matched_keywords) VALUES (?, ?, ?, ?, ?, ?)", (st.session_state.user["id"] if st.session_state.user else None, resume_id, job_id, score, ", ".join(missing[:200]), ", ".join(matched[:200])))
                    conn.commit()
            except Exception as e:
                st.warning("DB save failed (non-fatal): " + str(e))

            st.session_state.match_result = {"score": score, "matched": matched, "missing": missing, "warnings": warnings}
            st.session_state.page = "results"
            st.experimental_rerun()

def page_results():
    st.header("Match Results")
    r = st.session_state.get("match_result")
    if not r:
        st.info("Nothing to show. Run a scan.")
        return
    st.metric("Match Score", f"{r['score']}%")
    st.subheader("Matched Keywords")
    st.write(", ".join(r.get("matched", [])[:200]) or "None")
    st.subheader("Missing Keywords (from JD)")
    st.write(", ".join(r.get("missing", [])[:200]) or "None")
    st.subheader("ATS Formatting Warnings")
    for w in r.get("warnings", []):
        st.warning(w)
    if st.button("Scan another resume"):
        st.session_state.page = "scanner"
        st.experimental_rerun()

def page_dashboard():
    st.header("Dashboard - recent scans")
    if not st.session_state.user:
        st.info("Please sign in to view your scans.")
        return
    try:
        if db_type == "postgres":
            engine = db_conn
            with engine.connect() as conn:
                rows = conn.execute(text("""SELECT s.scanned_at, s.match_score, r.filename, jd.content
                                            FROM scan_results s
                                            LEFT JOIN resumes r ON r.id = s.resume_id
                                            LEFT JOIN job_descriptions jd ON jd.id = s.job_id
                                            WHERE s.user_id = :uid
                                            ORDER BY s.scanned_at DESC LIMIT 20"""), {"uid": st.session_state.user["id"]}).fetchall()
                for row in rows:
                    st.markdown("---")
                    st.write(f"**Date:** {row[0]}  |  **Score:** {row[1]}%")
                    st.write(f"**Resume file:** {row[2]}")
                    st.write(f"**JD excerpt:** {row[3][:250] if row[3] else ''}...")
        else:
            conn = db_conn
            cur = conn.cursor()
            cur.execute("SELECT scanned_at, match_score, resume_id, job_id FROM scan_results ORDER BY scanned_at DESC LIMIT 20")
            rows = cur.fetchall()
            for row in rows:
                st.markdown("---")
                st.write(f"**Date:** {row[0]}  |  **Score:** {row[1]}%")
    except Exception as e:
        st.error("Could not load dashboard: " + str(e))

def page_cover():
    st.header("Cover Letter Analyzer")
    st.info("Paste your cover letter and JD; get simple suggestions.")
    cover = st.text_area("Paste Cover Letter", height=240)
    jd = st.text_area("Paste Job Description (optional)", height=160)
    if st.button("Analyze Cover Letter"):
        if not cover.strip():
            st.warning("Paste your cover letter.")
        else:
            st.success("Basic checks completed.")
            st.write("Tip: Start with a strong opening line; mention 2-3 quantifiable achievements; tailor to the JD.")

def page_linkedin():
    st.header("LinkedIn Optimizer")
    st.info("Paste your LinkedIn 'About' summary for quick optimizations.")
    summary = st.text_area("Paste LinkedIn Summary", height=300)
    if st.button("Optimize"):
        if not summary.strip():
            st.warning("Paste your LinkedIn summary.")
        else:
            st.write("Suggestions: Add keywords from JD; open with role+impact; highlight 2 achievements; include contact CTA.")

# Router
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
else:
    page_home()
