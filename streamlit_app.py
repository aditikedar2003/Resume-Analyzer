### FILE: streamlit_app.py
# streamlit_app.py - final integrated app
import streamlit as st
from utils.db import init_db, get_db
from utils import auth
from utils.extractor import extract_file_text
from utils.nlp import analyze_resume_and_jd
from sqlalchemy import text
import os
import tempfile

# Initialize DB (creates tables if missing)
init_db()

# Page config and logo (put assets/logo.png in repo)
st.set_page_config(page_title="Resume Analyzer Pro", page_icon="assets/logo.png" if os.path.exists("assets/logo.png") else None, layout="wide")

# Header with logo and nav
col1, col2, col3 = st.columns([1, 6, 1])
with col1:
    if os.path.exists("assets/logo.png"):
        st.image("assets/logo.png", width=80)
with col2:
    st.markdown("<h1 style='text-align: left; margin:0;'>Resume Analyzer Pro</h1>", unsafe_allow_html=True)
    st.markdown("<div style='color:gray; margin-top: -6px;'>Optimize your resume for any job — ATS checks, keyword match & suggestions.</div>", unsafe_allow_html=True)
with col3:
    # auth quick controls
    if auth.is_authenticated():
        user = st.session_state.get("user", {})
        st.write(f"Hi, **{user.get('name','') }**")
        if st.button("Logout"):
            auth.logout()
            st.experimental_rerun()

# Navigation in header style
nav_cols = st.columns(6)
pages = ["Home", "Resume Scanner", "Dashboard", "Cover Letter", "LinkedIn Optimizer", "Job Tracker"]
for i, p in enumerate(pages):
    if nav_cols[i].button(p):
        st.session_state.page = p.lower().replace(" ", "_")

# Default page
if "page" not in st.session_state:
    st.session_state.page = "home"

# Local DB handle for queries
db_type, db = get_db()


# ---- AUTH SECTION (Signup & Login modal-like) ----
def show_signup():
    st.header("Create account")
    name = st.text_input("Full name", key="su_name")
    email = st.text_input("Email", key="su_email")
    pwd = st.text_input("Password", type="password", key="su_pwd")
    if st.button("Register"):
        if not (name and email and pwd):
            st.error("Please fill all fields.")
            return
        ok, msg = auth.register_user(name, email, pwd)
        if ok:
            st.success(msg)
            # Prefill login fields and auto open login: set session and switch page
            st.session_state.prefill_email = email
            st.session_state.prefill_password = pwd
            st.session_state.page = "home"
            st.experimental_rerun()
        else:
            st.error(msg)

def show_login():
    st.header("Login")
    email = st.text_input("Email", key="li_email", value=st.session_state.get("prefill_email", ""))
    pwd = st.text_input("Password", type="password", key="li_pwd", value=st.session_state.get("prefill_password", ""))
    if st.button("Login Now"):
        ok, resp = auth.login_user(email, pwd)
        if ok:
            st.session_state.user = resp
            st.success("Logged in")
            st.session_state.page = "resume_scanner"
            st.experimental_rerun()
        else:
            st.error(resp)


# ---- PAGES ----
def page_home():
    st.header("Optimize your resume for any job")
    st.markdown("""
    - Upload your resume (PDF/DOCX/TXT) or paste it.
    - Paste the Job Description (JD) you want to apply for.
    - Click **Scan** — get a match score, missing keywords, and ATS formatting tips.
    """)
    if not auth.is_authenticated():
        st.info("You should sign up or login to save scans. Use the Sign up / Login controls below.")
        show_signup()
        st.markdown("---")
        show_login()


def page_scanner():
    st.header("Resume Scanner")
    col1, col2 = st.columns([1,1])
    with col1:
        uploaded = st.file_uploader("Upload Resume (pdf/docx/txt)", type=["pdf", "docx", "txt"])
        resume_text_manual = st.text_area("Or paste resume text (optional, used if uploaded file missing)")
    with col2:
        jd_text = st.text_area("Paste Job Description (JD) here")
        ck_linkedin = st.checkbox("Also optimize for LinkedIn (summary)", value=False)
    if st.button("Scan"):
        # prefer uploaded file
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

        result = analyze_resume_and_jd(rtext, jd_text)
        # Persist result
        try:
            user_id = st.session_state.get("user", {}).get("id") if auth.is_authenticated() else None
            resume_id = None
            job_id = None
            if db_type == "postgres":
                engine = db
                with engine.begin() as conn:
                    res = conn.execute(text("INSERT INTO resumes (user_id, filename, content) VALUES (:uid, :fn, :content) RETURNING id"),
                                       {"uid": user_id, "fn": uploaded.name if uploaded else "pasted_resume.txt", "content": rtext})
                    resume_id = int(res.fetchone()[0])
                    res2 = conn.execute(text("INSERT INTO job_descriptions (user_id, filename, content) VALUES (:uid, :fn, :content) RETURNING id"),
                                        {"uid": user_id, "fn": "jd.txt", "content": jd_text})
                    job_id = int(res2.fetchone()[0])
                    conn.execute(text("""INSERT INTO scan_results (user_id, resume_id, job_id, match_score, matched_keywords, missing_keywords)
                                        VALUES (:uid, :rid, :jid, :score, :matched, :missing)"""),
                                 {"uid": user_id, "rid": resume_id, "jid": job_id, "score": result["score"],
                                  "matched": ", ".join(result["matched"][:200]), "missing": ", ".join(result["missing"][:200])})
            else:
                conn = db
                cur = conn.cursor()
                cur.execute("INSERT INTO resumes (user_id, filename, content) VALUES (?, ?, ?)",
                            (user_id, uploaded.name if uploaded else "pasted_resume.txt", rtext))
                resume_id = cur.lastrowid
                cur.execute("INSERT INTO job_descriptions (user_id, filename, content) VALUES (?, ?, ?)",
                            (user_id, "jd.txt", jd_text))
                job_id = cur.lastrowid
                cur.execute("INSERT INTO scan_results (user_id, resume_id, job_id, match_score, matched_keywords, missing_keywords) VALUES (?, ?, ?, ?, ?, ?)",
                            (user_id, resume_id, job_id, result["score"], ", ".join(result["matched"][:200]), ", ".join(result["missing"][:200])))
                conn.commit()
        except Exception as e:
            st.error("Warning: could not persist to DB: " + str(e))

        # show results inline
        st.success(f"Match Score: {result['score']}%")
        st.subheader("Matched Keywords")
        st.write(", ".join(result["matched"][:200]) or "None found")
        st.subheader("Missing Keywords (from JD)")
        st.write(", ".join(result["missing"][:200]) or "None")
        st.subheader("ATS Formatting Warnings")
        if result["warnings"]:
            for w in result["warnings"]:
                st.warning(w)
        else:
            st.success("No obvious ATS formatting problems found.")

def page_dashboard():
    st.header("Dashboard - Scan History")
    if not auth.is_authenticated():
        st.info("Sign in to see your saved scans.")
        return
    user_id = st.session_state.get("user", {}).get("id")
    try:
        if db_type == "postgres":
            engine = db
            with engine.connect() as conn:
                rows = conn.execute(text("""SELECT s.scanned_at, s.match_score, r.filename, jd.content
                                            FROM scan_results s
                                            LEFT JOIN resumes r ON r.id = s.resume_id
                                            LEFT JOIN job_descriptions jd ON jd.id = s.job_id
                                            WHERE s.user_id = :uid
                                            ORDER BY s.scanned_at DESC LIMIT 50"""), {"uid": user_id}).fetchall()
                for row in rows:
                    st.markdown("---")
                    st.write(f"**Date:** {row[0]}  |  **Score:** {row[1]}%")
                    st.write(f"**Resume file:** {row[2]}")
                    st.write(f"**JD excerpt:** { (row[3] or '')[:300] }...")
        else:
            conn = db
            cur = conn.cursor()
            cur.execute("SELECT scanned_at, match_score, resume_id, job_id FROM scan_results WHERE user_id = ? ORDER BY scanned_at DESC LIMIT 50", (user_id,))
            rows = cur.fetchall()
            for row in rows:
                st.markdown("---")
                st.write(f"**Date:** {row[0]}  |  **Score:** {row[1]}%")
                rid = row[2]; jid = row[3]
                cur.execute("SELECT filename FROM resumes WHERE id = ?", (rid,))
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
    cover = st.text_area("Paste Cover Letter")
    jd = st.text_area("Paste Job Description (optional)")
    if st.button("Analyze Cover Letter"):
        if not cover.strip():
            st.warning("Paste your cover letter.")
        else:
            st.success("Basic checks completed.")
            st.write("Tip: Start with a strong opening line; mention 2-3 quantifiable achievements; tailor to the JD.")


def page_linkedin():
    st.header("LinkedIn Optimizer")
    summary = st.text_area("Paste LinkedIn Summary")
    if st.button("Optimize"):
        if not summary.strip():
            st.warning("Paste your LinkedIn summary.")
        else:
            st.write("Suggestions: Add keywords from JD; open with role+impact; highlight 2 achievements; include contact CTA.")


def page_tracker():
    st.header("Job Tracker")
    title = st.text_input("Job title")
    company = st.text_input("Company")
    date = st.date_input("Application date")
    status = st.selectbox("Status", ["Applied", "Interviewing", "Offer", "Rejected"])
    if st.button("Add to Tracker"):
        try:
            user_id = st.session_state.get("user", {}).get("id") if auth.is_authenticated() else None
            if db_type == "postgres":
                engine = db
                with engine.begin() as conn:
                    conn.execute(text("INSERT INTO job_tracker (user_id, job_title, company_name, application_date, status) VALUES (:uid, :t, :c, :d, :s)"),
                                 {"uid": user_id, "t": title, "c": company, "d": date, "s": status})
            else:
                conn = db
                cur = conn.cursor()
                cur.execute("INSERT INTO job_tracker (user_id, job_title, company_name, application_date, status) VALUES (?, ?, ?, ?, ?)",
                            (user_id, title, company, date.isoformat(), status))
                conn.commit()
            st.success("Job added.")
        except Exception as e:
            st.error("Could not add to tracker: " + str(e))


# Router
page = st.session_state.page
if page == "home":
    page_home()
elif page == "resume_scanner" or page == "resume_scanner":
    page_scanner()
elif page == "dashboard":
    page_dashboard()
elif page == "cover_letter" or page == "cover_letter":
    page_cover()
elif page == "linkedin_optimizer" or page == "linkedin_optimizer":
    page_linkedin()
elif page == "job_tracker" or page == "job_tracker":
    page_tracker()
else:
    # map simplified names
    if page == "resume_scanner":
        page_scanner()
    elif page == "dashboard":
        page_dashboard()
    elif page == "cover_letter":
        page_cover()
    elif page == "linkedin_optimizer":
        page_linkedin()
    elif page == "job_tracker":
        page_tracker()
    else:
        page_home()
