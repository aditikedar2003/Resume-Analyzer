# streamlit_app.py
"""
Single-file final app for Resume Analyzer (DB-free mode).
Drop this into your repo root and run with `streamlit run streamlit_app.py`.

Features:
- No DB; accepts any credentials (signup/login succeed).
- Resume/JD analysis with cosine-similarity (numpy-based).
- File extraction with PyPDF2 / python-docx when available.
- Simple Dashboard stored in session_state.
- Top header navigation (centered) with responsive layout and smooth scrolling.
"""

import streamlit as st
from datetime import datetime
from io import BytesIO
import re
import os
import base64
import json

# optional libs - import when available; otherwise use fallbacks
try:
    import PyPDF2
except Exception:
    PyPDF2 = None

try:
    import docx
except Exception:
    docx = None

import numpy as np
from passlib.hash import bcrypt

st.set_page_config(page_title="Resume Analyzer Pro", page_icon="🚀", layout="wide")

# ---------- Utilities ----------
def safe_extract_text_from_pdf(fbytes: bytes):
    if not PyPDF2:
        return ""
    try:
        bio = BytesIO(fbytes)
        reader = PyPDF2.PdfReader(bio)
        pages = []
        for p in reader.pages:
            try:
                pages.append(p.extract_text() or "")
            except Exception:
                continue
        return "\n".join(pages)
    except Exception:
        return ""

def safe_extract_text_from_docx(fbytes: bytes):
    if not docx:
        return ""
    try:
        bio = BytesIO(fbytes)
        doc = docx.Document(bio)
        paragraphs = [p.text for p in doc.paragraphs if p.text]
        return "\n".join(paragraphs)
    except Exception:
        return ""

def extract_text_from_uploaded(uploaded_file):
    if uploaded_file is None:
        return ""
    name = uploaded_file.name.lower()
    raw = uploaded_file.read()
    # try recognized types
    if name.endswith(".pdf"):
        text = safe_extract_text_from_pdf(raw)
        if text:
            return text
    if name.endswith(".docx") or name.endswith(".doc"):
        text = safe_extract_text_from_docx(raw)
        if text:
            return text
    # fallback to text decode
    try:
        return raw.decode("utf-8", errors="ignore")
    except Exception:
        try:
            return raw.decode("latin-1", errors="ignore")
        except Exception:
            return ""

# text cleaning & tokenization
TOKEN_RE = re.compile(r"\b[a-z0-9\+\#\-\.]+\b", re.I)
def tokenize(s: str):
    if not s:
        return []
    s = s.lower()
    return TOKEN_RE.findall(s)

def build_term_vector(tokens, vocab_index):
    vec = np.zeros(len(vocab_index), dtype=float)
    for t in tokens:
        if t in vocab_index:
            vec[vocab_index[t]] += 1.0
    # length-normalize to avoid length bias
    if np.linalg.norm(vec) > 0:
        return vec / np.linalg.norm(vec)
    return vec

def compute_match_score(resume_text: str, jd_text: str):
    # build vocabulary of top tokens from both
    r_tokens = tokenize(resume_text)
    j_tokens = tokenize(jd_text)
    if not r_tokens or not j_tokens:
        return 0.0
    vocab = sorted(set(r_tokens + j_tokens))
    vocab_index = {w: i for i, w in enumerate(vocab)}
    r_vec = build_term_vector(r_tokens, vocab_index)
    j_vec = build_term_vector(j_tokens, vocab_index)
    # cosine similarity
    denom = (np.linalg.norm(r_vec) * np.linalg.norm(j_vec))
    if denom == 0:
        return 0.0
    sim = float(np.dot(r_vec, j_vec))
    return round(sim * 100, 2)

def get_keywords_and_missing(resume_text: str, jd_text: str, top_n=50):
    r_words = set(tokenize(resume_text))
    jd_words = set(tokenize(jd_text))
    matched = sorted(list(jd_words & r_words))
    missing = sorted(list(jd_words - r_words))
    return matched[:top_n], missing[:top_n]

def simple_ats_checks(resume_text: str):
    checks = []
    if not resume_text:
        return checks
    if "\t" in resume_text or "  " in resume_text:
        checks.append("Possible columns or table-like formatting (avoid for ATS).")
    if "<img" in resume_text.lower() or "image:" in resume_text.lower():
        checks.append("Images detected or image tags present (remove images for ATS).")
    if len(resume_text.splitlines()) < 5:
        checks.append("Very short resume text detected (add more content).")
    return checks

# small helper to display a download link for resume text
def get_download_link(text, filename="resume.txt"):
    b64 = base64.b64encode(text.encode()).decode()
    href = f'<a href="data:file/txt;base64,{b64}" download="{filename}">Download extracted resume text</a>'
    return href

# ---------- Session state init ----------
if "page" not in st.session_state:
    st.session_state.page = "home"
if "user" not in st.session_state:
    st.session_state.user = None
if "last_registration" not in st.session_state:
    st.session_state.last_registration = None
if "last_login_prefill" not in st.session_state:
    st.session_state.last_login_prefill = {"email":"","password":""}
if "scan_history" not in st.session_state:
    st.session_state.scan_history = []  # list of dicts
if "current_result" not in st.session_state:
    st.session_state.current_result = None

# --------- Navigation helper (safe) ----------
def navigate_to(page_name: str):
    """
    Set session page (no experimental_rerun). Streamlit will rerun on next interaction.
    We also set a little flag so the JS smooth-scroll knows which section to scroll to.
    """
    st.session_state.page = page_name

# ---------- Header / Top-nav (center-aligned) ----------
# Styling: purple accent, slightly wider buttons; responsive
st.markdown("""
    <style>
    /* center header container */
    .header-wrap {
      display:flex;
      justify-content:center;
      align-items:center;
      padding:10px 0;
      border-bottom:1px solid #eee;
      background: white;
      position: sticky;
      top: 0;
      z-index: 9999;
    }
    /* container for buttons */
    .nav-buttons {
      display:flex;
      gap: 18px;
      align-items:center;
      justify-content:center;
      flex-wrap:wrap;
    }
    /* style Streamlit buttons inside header (applies globally but OK) */
    div.stButton > button {
      background-color: #800080;
      color: white !important;
      padding: 8px 18px;
      border-radius: 8px;
      border: none;
      font-weight: 600;
      font-size: 14px;
      min-width: 120px;
    }
    div.stButton > button:hover {
      background-color: #9932CC;
    }
    /* Make header responsive and centered */
    @media (max-width: 900px) {
      div.stButton > button {
         padding: 7px 12px;
         min-width: 100px;
         font-size: 13px;
      }
    }
    @media (max-width: 480px) {
      .nav-buttons { gap: 8px; }
      div.stButton > button {
         padding: 6px 10px;
         min-width: 88px;
         font-size: 12px;
      }
    }
    </style>
    """, unsafe_allow_html=True)

# Build header with logo at left and buttons centered visually (we keep it simple & centered)
# Using columns so logo can remain left but buttons appear visually centered (as requested)
cols = st.columns([1, 6, 1])
with cols[0]:
    # small left area for logo (keeps layout balanced). Use repo root logo.png if present.
    logo_path = "logo.png"
    if os.path.exists(logo_path):
        st.image(logo_path, width=56)
    else:
        st.write("")  # keep space

with cols[1]:
    # center column - navigation buttons displayed horizontally
    nav_cols = st.columns([1,1,1,1,1,1,1,1])  # enough columns for each button so they align well
    # names and mapping to internal page keys (must match router below)
    nav_map = [
        ("HOME", "home"),
        ("Scanner", "scanner"),
        ("Results", "results"),
        ("Dashboard", "dashboard"),
        ("Cover Letter", "cover_letter"),
        ("LinkedIn", "linkedin"),
        ("Job Tracker", "job_tracker"),
        ("Account", "account")
    ]
    # render buttons in nav_cols (wrap if screen narrow)
    for i, (label, key) in enumerate(nav_map):
        # choose a column: if more nav items than nav_cols, wrap using modulo
        col = nav_cols[i % len(nav_cols)]
        with col:
            if st.button(label, key=f"nav_{key}"):
                navigate_to(key)

with cols[2]:
    # right area reserved (could be "Sign Up / Login" link), keep empty to ensure centering
    st.markdown("")  # keep as placeholder

st.markdown("")  # spacing
# ---------- End header ----------

# ---------- Smooth-scroll helper ----------
# Insert section anchors at the start of each page and add JS to smooth-scroll to current section
def smooth_scroll_to_current():
    # Ensure 'page' value is available in JS
    page_id = st.session_state.get("page", "home")
    safe_page = str(page_id).replace('"', '')
    scroll_js = f"""
    <script>
    (function() {{
        const pageId = "{safe_page}";
        // wait a bit for DOM to stabilise, then scroll
        setTimeout(function() {{
            const el = document.getElementById("section-" + pageId);
            if (el) {{
                el.scrollIntoView({{behavior: "smooth", block: "start"}});
            }}
        }}, 120);
    }})();
    </script>
    """
    st.markdown(scroll_js, unsafe_allow_html=True)

# ---------- Pages (unchanged logic; experimental_rerun removed) ----------
# Each page starts with an anchor div id="section-<page_key>"

def page_home():
    st.markdown('<div id="section-home"></div>', unsafe_allow_html=True)
    st.header("Welcome — How Resume Analyzer Pro helps you")
    st.markdown("""
    - Upload your resume (PDF / DOCX / TXT) or paste it — we'll extract and analyze it.
    - Paste the Job Description (JD) you want to apply for.
    - Get a percentage match, matched & missing keywords, and ATS formatting tips — instantly.
    """)
    st.markdown("**Try it:** Click `Scanner` in the top nav and upload a resume to begin.")
    # note: per request, removed the "This version runs without a database..." message

def page_scanner():
    st.markdown('<div id="section-scanner"></div>', unsafe_allow_html=True)
    st.header("Resume Scanner")
    left, right = st.columns([1,1])
    with left:
        uploaded = st.file_uploader("Upload Resume (pdf/docx/txt)", type=["pdf","docx","doc","txt"], key="upload_resume")
        resume_text_manual = st.text_area("Or paste resume text (optional, used if uploaded file missing)", height=200, key="paste_resume")
        # display extracted preview when file present
        if uploaded:
            st.info(f"Uploaded: {uploaded.name}")
    with right:
        jd_text = st.text_area("Paste Job Description (JD) here", height=300, key="paste_jd")
        ck_linkedin = st.checkbox("Also optimize for LinkedIn summary (produce suggestions)", value=False, key="ck_linkedin")
        weight = st.slider("Importance weight: match vs. readability", 0.0, 1.0, 0.7, help="Higher = match-focused; lower = readability-focused", key="weight_slider")
    if st.button("Scan / Analyze", key="scan_analyze"):
        # get resume text
        uploaded_local = st.session_state.get("upload_resume")
        # if file uploader was used, Streamlit stores it in session_state under that key
        uploaded_obj = uploaded_local if uploaded_local else None
        if uploaded_obj:
            rtext = extract_text_from_uploaded(uploaded_obj)
        else:
            rtext = (st.session_state.get("paste_resume", "") or "").strip()
        if not rtext:
            st.warning("Please provide resume text by uploading a file or pasting it.")
            return
        if not (st.session_state.get("paste_jd", "") or jd_text.strip()):
            st.warning("Please paste a job description to compare.")
            return

        jd_val = st.session_state.get("paste_jd", "") or jd_text

        # compute score & keywords
        score = compute_match_score(rtext, jd_val)
        matched, missing = get_keywords_and_missing(rtext, jd_val, top_n=200)
        warnings = simple_ats_checks(rtext)
        # generate simple suggestions
        suggestions = []
        if score < 40:
            suggestions.append("Increase keyword density for important JD terms. Add measurable outcomes and technical keywords.")
        elif score < 70:
            suggestions.append("You're on the right track. Add more role-specific keywords and quantify achievements.")
        else:
            suggestions.append("Great match — ensure formatting is ATS-friendly and proofread for clarity.")
        # LinkedIn suggestions if asked
        linkedin_suggestions = None
        if ck_linkedin:
            linkedin_suggestions = [
                "Start headline with your role + 1-line impact (e.g., 'Full-stack dev — built X that reduced Y').",
                "List top 4 technical keywords from JD near top.",
                "Add 2 quantifiable achievements and a contact CTA."
            ]
        # store in session_result
        result = {
            "timestamp": datetime.utcnow().isoformat(),
            "score": score,
            "matched": matched,
            "missing": missing,
            "warnings": warnings,
            "suggestions": suggestions,
            "linkedin_suggestions": linkedin_suggestions,
            "resume_text_excerpt": (rtext[:2000] + "...") if len(rtext) > 2000 else rtext,
            "jd_excerpt": (jd_val[:1000] + "...") if len(jd_val) > 1000 else jd_val,
            "resume_name": uploaded_obj.name if uploaded_obj else "pasted_resume.txt"
        }
        st.session_state.current_result = result
        # add to ephemeral history
        st.session_state.scan_history.insert(0, result)
        # navigate to results (no experimental_rerun)
        st.session_state.page = "results"
        # allow rerun naturally by returning (Streamlit will rerun on next interaction)
        return

def page_results():
    st.markdown('<div id="section-results"></div>', unsafe_allow_html=True)
    r = st.session_state.get("current_result")
    st.header("Match Results")
    if not r:
        st.info("No result to display. Run a scan first from the Scanner page.")
        return
    # show score
    st.metric("Match Score", f"{r['score']}%")
    # matched & missing keywords
    st.subheader("Matched Keywords")
    if r["matched"]:
        st.write(", ".join(r["matched"][:200]))
    else:
        st.write("None found")
    st.subheader("Missing Keywords (from JD)")
    if r["missing"]:
        st.write(", ".join(r["missing"][:200]))
    else:
        st.write("None")
    # ATS warnings
    st.subheader("ATS Formatting Warnings")
    if r["warnings"]:
        for w in r["warnings"]:
            st.warning(w)
    else:
        st.success("No obvious ATS formatting problems found.")
    # suggestions
    st.subheader("Suggestions")
    for s in r.get("suggestions", []):
        st.write("• " + s)
    # LinkedIn suggestions
    if r.get("linkedin_suggestions"):
        st.subheader("LinkedIn Optimization Suggestions")
        for s in r["linkedin_suggestions"]:
            st.write("• " + s)
    st.markdown("---")
    st.write("**Resume excerpt:**")
    st.code(r.get("resume_text_excerpt", "")[:5000])
    st.markdown(get_download_link(r.get("resume_text_excerpt",""), filename="extracted_resume.txt"), unsafe_allow_html=True)
    if st.button("Scan another resume", key="scan_another"):
        st.session_state.page = "scanner"
        return

def page_dashboard():
    st.markdown('<div id="section-dashboard"></div>', unsafe_allow_html=True)
    st.header("Dashboard — Recent Scans (session only)")
    history = st.session_state.get("scan_history", [])
    if not history:
        st.info("No scans yet. Run a scan on the Scanner page.")
        return
    for item in history[:20]:
        st.markdown("---")
        ts = item.get("timestamp", "")
        st.write(f"**Date:** {ts}  |  **Score:** {item.get('score')}%  |  **Resume:** {item.get('resume_name')}")
        st.write("Matched: " + (", ".join(item.get("matched", [])[:20]) or "None"))
        st.write("Missing: " + (", ".join(item.get("missing", [])[:20]) or "None"))

def page_cover_letter():
    st.markdown('<div id="section-cover_letter"></div>', unsafe_allow_html=True)
    st.header("Cover Letter Analyzer")
    st.info("Paste your cover letter and optional JD; get quick suggestions.")
    cover = st.text_area("Paste Cover Letter", height=250, key="cover_text")
    jd = st.text_area("Paste Job Description (optional)", height=200, key="cover_jd")
    if st.button("Analyze Cover Letter", key="analyze_cover"):
        if not cover.strip():
            st.warning("Please paste a cover letter.")
            return
        tips = []
        tips.append("Open with a strong one-line introduction (role + impact).")
        # simple checks
        if len(cover.split()) < 100:
            tips.append("Cover letter is short. Aim for ~200-300 words.")
        if jd.strip():
            # compare keywords
            matched, missing = get_keywords_and_missing(cover, jd, top_n=20)
            if matched:
                tips.append(f"Keywords from JD found in cover: {', '.join(matched[:8])}")
            if missing:
                tips.append(f"Keywords to add: {', '.join(missing[:8])}")
        tips.append("Quantify 2-3 achievements and finish with a contact CTA.")
        st.success("Basic checks completed.")
        for t in tips:
            st.write("• " + t)

def page_linkedin():
    st.markdown('<div id="section-linkedin"></div>', unsafe_allow_html=True)
    st.header("LinkedIn Optimizer")
    st.info("Paste your LinkedIn 'About' summary and optional JD for suggestions.")
    summary = st.text_area("Paste LinkedIn Summary", height=250, key="linkedin_summary")
    jd = st.text_area("Paste Job Description (optional)", height=200, key="linkedin_jd")
    if st.button("Optimize LinkedIn", key="opt_linkedin"):
        if not summary.strip():
            st.warning("Please paste your LinkedIn summary.")
            return
        suggestions = []
        suggestions.append("Start with role + impact in the first sentence.")
        suggestions.append("Add top 4 technical keywords from JD near the top.")
        # quick keyword check if JD exists
        if jd.strip():
            matched, missing = get_keywords_and_missing(summary, jd, top_n=20)
            suggestions.append(f"Keywords present: {', '.join(matched[:8])}" if matched else "No JD keywords found in summary.")
            if missing:
                suggestions.append(f"Consider adding: {', '.join(missing[:8])}")
        suggestions.append("Add a CTA for contact and 2 quantifiable achievements.")
        for s in suggestions:
            st.write("• " + s)

def page_tracker():
    st.markdown('<div id="section-job_tracker"></div>', unsafe_allow_html=True)
    st.header("Job Tracker (session-only)")
    st.info("Log job applications (stored only for this session).")
    title = st.text_input("Job title", key="tracker_title")
    company = st.text_input("Company", key="tracker_company")
    date = st.date_input("Application date", key="tracker_date")
    status = st.selectbox("Status", ["Applied", "Interviewing", "Offer", "Rejected"], key="tracker_status")
    if st.button("Add to Tracker", key="add_tracker"):
        entry = {
            "title": title,
            "company": company,
            "date": date.isoformat(),
            "status": status
        }
        if "job_tracker" not in st.session_state:
            st.session_state.job_tracker = []
        st.session_state.job_tracker.insert(0, entry)
        st.success("Added to tracker.")
    # list
    if st.session_state.get("job_tracker"):
        for e in st.session_state.job_tracker:
            st.markdown(f"- {e['date']} — **{e['title']}** at *{e['company']}* — {e['status']}")

def page_account():
    st.markdown('<div id="section-account"></div>', unsafe_allow_html=True)
    st.header("Account (session-only) — simplified auth")
    if st.session_state.user:
        st.success(f"Signed in as **{st.session_state.user.get('name')}** ({st.session_state.user.get('email')})")
        if st.button("Logout", key="logout_btn"):
            st.session_state.user = None
            st.session_state.page = "home"
            return
        return
    # Registration form
    st.subheader("Sign Up")
    su_name = st.text_input("Full name", key="su_name")
    su_email = st.text_input("Email", key="su_email")
    su_pwd = st.text_input("Password", type="password", key="su_pwd")
    if st.button("Register", key="register_btn"):
        # accept anything, store hashed password in session as example
        hashed = bcrypt.hash(su_pwd or "temp123")
        st.session_state.last_registration = {"name": su_name, "email": su_email, "hashed": hashed}
        # prefill login
        st.session_state.last_login_prefill = {"email": su_email or "", "password": su_pwd or ""}
        st.success("Registration successful. Please log in (we prefilled your login).")
    st.markdown("---")
    st.subheader("Login")
    li_email = st.text_input("Email", key="li_email", value=st.session_state.last_login_prefill.get("email",""))
    li_pwd = st.text_input("Password", type="password", key="li_pwd", value=st.session_state.last_login_prefill.get("password",""))
    if st.button("Login", key="login_btn"):
        # ACCEPT ANY credentials (as requested)
        user = {"id": 1, "name": st.session_state.last_registration.get("name","Guest") if st.session_state.last_registration else "Guest", "email": li_email}
        st.session_state.user = user
        st.success("Logged in successfully.")
        st.session_state.page = "dashboard"
        return

# Router
page = st.session_state.page

if page == "home":
    page_home()
elif page == "scanner":
    page_scanner()
elif page == "results":
    page_results()
elif page == "dashboard":
    page_dashboard()
elif page == "cover_letter" or page == "cover":
    page_cover_letter()
elif page == "linkedin":
    page_linkedin()
elif page == "job_tracker":
    page_tracker()
elif page == "account":
    page_account()
else:
    page_home()

# scroll to the section for smooth UX
smooth_scroll_to_current()
