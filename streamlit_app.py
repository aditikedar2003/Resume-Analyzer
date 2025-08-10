# streamlit_app.py
import streamlit as st
from utils.extractor import extract_file_text
from utils.nlp import compute_match_score, get_keywords, simple_ats_checks
import utils.auth as auth
from utils.db import detect_db
from sqlalchemy import text
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(page_title="Resume Analyzer Pro", page_icon="🚀", layout="wide")

# detect DB
db_type, db_conn = detect_db()

# session init
if "page" not in st.session_state:
    st.session_state.page = "home"
if "user" not in st.session_state:
    st.session_state.user = None
if "just_registered" not in st.session_state:
    st.session_state.just_registered = None
if "show_auth" not in st.session_state:
    st.session_state.show_auth = False
if "match_result" not in st.session_state:
    st.session_state.match_result = None

# HEADER: logo / title / nav
logo_col, title_col, nav_col = st.columns([1, 4, 3])
with logo_col:
    st.image("https://via.placeholder.com/64", width=64)
with title_col:
    st.markdown("<h1 style='margin:0'>Resume Analyzer Pro</h1>", unsafe_allow_html=True)
    st.markdown("<div style='color:gray;margin-top:4px'>Optimize your resume for any job — ATS checks & keyword match.</div>", unsafe_allow_html=True)
with nav_col:
    c1, c2, c3, c4 = st.columns(4)
    if c1.button("Home"):
        st.session_state.page = "home"
        st.rerun()
    if c2.button("Scanner"):
        st.session_state.page = "scanner"
        st.rerun()
    if c3.button("Dashboard"):
        st.session_state.page = "dashboard"
        st.rerun()
    if c4.button("Resources"):
        st.session_state.page = "resources"
        st.rerun()

# RIGHT SIDE AUTH controls in header area
auth_col1, auth_col2 = st.columns([4,1])
with auth_col2:
    if st.session_state.user:
        if st.button("Logout"):
            st.session_state.user = None
            st.success("Logged out")
            st.rerun()
    else:
        if st.button("Login / Sign Up"):
            st.session_state.show_auth = True

# AUTH expander when requested
if st.session_state.show_auth:
    with st.expander("Account"):
        tabs = st.tabs(["Login","Sign Up"])
        with tabs[0]:
            login_email = st.text_input("Email", key="login_email", value=(st.session_state.get("just_registered") or {}).get("email", ""))
            login_pwd = st.text_input("Password", type="password", key="login_pwd", value=(st.session_state.get("just_registered") or {}).get("password", ""))
            if st.button("Sign in"):
                ok, resp = auth.login_user(login_email, login_pwd)
                if ok:
                    st.session_state.user = resp
                    st.session_state.show_auth = False
                    st.success("Logged in")
                    st.rerun()
                else:
                    st.error(resp)
        with tabs[1]:
            su_name = st.text_input("Full name", key="su_name")
            su_email = st.text_input("Email", key="su_email")
            su_pwd = st.text_input("Password", type="password", key="su_pwd")
            if st.button("Register"):
                ok, msg = auth.register_user(su_name, su_email, su_pwd)
                if ok:
                    st.session_state.just_registered = {"email": su_email, "password": su_pwd}
                    st.success("Registered successfully — signing you in...")
                    ok2, user = auth.login_user(su_email, su_pwd)
                    if ok2:
                        st.session_state.user = user
                        st.session_state.show_auth = False
                        st.rerun()
                    else:
                        st.info("Please sign in from Login tab.")
                else:
                    st.error(msg)

# PAGES
def page_home():
    st.header("Optimize your resume for any job")
    st.markdown("""
    - Upload resume (PDF/DOCX/TXT)
    - Paste Job Description (JD)
    - Click **Scan** to get match score, missing keywords and ATS tips.
    """)
    if st.button("Try Jobscan Now"):
        st.session_state.page = "scanner"
        st.rerun()

def page_scanner():
    st.header("Resume Scanner")
    col1, col2 = st.columns([1,1])
    with col1:
        uploaded = st.file_uploader("Upload Resume (pdf/docx/txt)", type=["pdf","docx","txt"])
        resume_text_manual = st.text_area("Or paste resume text (optional)", height=250)
    with col2:
        jd_text = st.text_area("Paste Job Description (JD) here", height=400)
        if st.button("Scan"):
            if uploaded:
                rtext = extract_file_text(uploaded)
            else:
                rtext = (resume_text_manual or "").strip()
            if not rtext:
                st.warning("Please provide resume text (upload or paste).")
                return
            if not jd_text.strip():
                st.warning("Please paste a job description to compare.")
                return
            score = compute_match_score(rtext, jd_text)
            matched, missing = get_keywords(rtext, jd_text, top_n=200)
            warnings = simple_ats_checks(rtext)
            # Save to DB (best effort)
            resume_id = None
            job_id = None
            try:
                if db_type == "postgres":
                    engine = db_conn
                    with engine.begin() as conn:
                        res = conn.execute(text("INSERT INTO resumes (user_id, filename, content) VALUES (:uid, :fn, :content) RETURNING id"),
                                           {"uid": st.session_state.user["id"] if st.session_state.user else None, "fn": (uploaded.name if uploaded else "pasted"), "content": rtext})
                        resume_id = int(res.fetchone()[0])
                        res2 = conn.execute(text("INSERT INTO job_descriptions (user_id, filename, content) VALUES (:uid, :fn, :content) RETURNING id"),
                                            {"uid": st.session_state.user["id"] if st.session_state.user else None, "fn": "jd.txt", "content": jd_text})
                        job_id = int(res2.fetchone()[0])
                        conn.execute(text("INSERT INTO scan_results (user_id, resume_id, job_id, match_score, missing_keywords, matched_keywords) VALUES (:uid, :rid, :jid, :score, :missing, :matched)"),
                                     {"uid": st.session_state.user["id"] if st.session_state.user else None, "rid": resume_id, "jid": job_id, "score": score, "missing": ", ".join(missing[:200]), "matched": ", ".join(matched[:200])})
                else:
                    conn = db_conn
                    cur = conn.cursor()
                    cur.execute("""CREATE TABLE IF NOT EXISTS resumes (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, filename TEXT, content TEXT, uploaded_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
                    cur.execute("""CREATE TABLE IF NOT EXISTS job_descriptions (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, filename TEXT, content TEXT, uploaded_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
                    cur.execute("""CREATE TABLE IF NOT EXISTS scan_results (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, resume_id INTEGER, job_id INTEGER, match_score REAL, missing_keywords TEXT, matched_keywords TEXT, scanned_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
                    conn.commit()
                    cur.execute("INSERT INTO resumes (user_id, filename, content) VALUES (?, ?, ?)", (st.session_state.user["id"] if st.session_state.user else None, (uploaded.name if uploaded else "pasted"), rtext))
                    resume_id = cur.lastrowid
                    cur.execute("INSERT INTO job_descriptions (user_id, filename, content) VALUES (?, ?, ?)", (st.session_state.user["id"] if st.session_state.user else None, "jd.txt", jd_text))
                    job_id = cur.lastrowid
                    cur.execute("INSERT INTO scan_results (user_id, resume_id, job_id, match_score, missing_keywords, matched_keywords) VALUES (?, ?, ?, ?, ?, ?)", (st.session_state.user["id"] if st.session_state.user else None, resume_id, job_id, score, ", ".join(missing[:200]), ", ".join(matched[:200])))
                    conn.commit()
            except Exception as e:
                st.warning("DB save failed (non-fatal): " + str(e))
            st.session_state.match_result = {"score": score, "matched": matched, "missing": missing, "warnings": warnings}
            st.session_state.page = "results"
            st.rerun()

def page_results():
    st.header("Match Results")
    r = st.session_state.get("match_result")
    if not r:
        st.info("No results yet. Run a scan first.")
        return
    st.metric("Match Score", f"{r['score']}%")
    st.subheader("Matched Keywords")
    st.write(", ".join(r.get("matched", [])[:200]) or "None")
    st.subheader("Missing Keywords (from JD)")
    st.write(", ".join(r.get("missing", [])[:200]) or "None")
    st.subheader("ATS Warnings")
    for w in r.get("warnings", []):
        st.warning(w)
    if st.button("Scan another resume"):
        st.session_state.page = "scanner"
        st.rerun()

def page_dashboard():
    st.header("Dashboard")
    if not st.session_state.user:
        st.info("Sign in to see your saved scans.")
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

def page_resources():
    st.header("Resources")
    st.markdown("- [Resume tips - Jobscan](https://www.jobscan.co/blog/how-to-write-a-resume/)")
    st.markdown("- Templates & articles coming soon.")

# Routing
if st.session_state.page == "home":
    page_home()
elif st.session_state.page == "scanner":
    page_scanner()
elif st.session_state.page == "results":
    page_results()
elif st.session_state.page == "dashboard":
    page_dashboard()
elif st.session_state.page == "resources":
    page_resources()
else:
    page_home()
