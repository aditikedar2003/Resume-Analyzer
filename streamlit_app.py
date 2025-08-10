# streamlit_app.py
"""
Final single-file Resume Analyzer (session-only mode).
- Single-page app with centered header navigation.
- No st.experimental_rerun() used.
- Resume/JD analysis (cosine similarity), keyword suggestions, ATS checks.
- PDF/DOCX extraction when libraries available.
- Dashboard (session-only), Cover Letter drag/drop upload.
"""

import streamlit as st
from datetime import datetime
from io import BytesIO
import re
import os
import base64

# optional libs - import when available; otherwise fallback
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

# page config
st.set_page_config(page_title="Resume Analyzer Pro", page_icon="🚀", layout="wide")

# ---------- Utilities (unchanged from your original) ----------
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
    r_tokens = tokenize(resume_text)
    j_tokens = tokenize(jd_text)
    if not r_tokens or not j_tokens:
        return 0.0
    vocab = sorted(set(r_tokens + j_tokens))
    vocab_index = {w: i for i, w in enumerate(vocab)}
    r_vec = build_term_vector(r_tokens, vocab_index)
    j_vec = build_term_vector(j_tokens, vocab_index)
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

# ---------- Navigation helper ----------
def navigate_to(page_name: str):
    """Set session page (no experimental_rerun)."""
    st.session_state.page = page_name

# ---------- Header / Top-nav (center-aligned, responsive) ----------
st.markdown("""
    <style>
    /* header */
    .header-wrap {
      display:flex;
      justify-content:center;
      align-items:center;
      padding:14px 0;
      border-bottom:1px solid #eee;
      background: white;
      position: sticky;
      top: 0;
      z-index: 9999;
    }
    /* nav buttons container */
    .nav-buttons {
      display:flex;
      gap: 14px;
      align-items:center;
      justify-content:center;
      flex-wrap:wrap;
      max-width: 1100px;
      width: 100%;
    }
    /* apply to Streamlit button */
    div.stButton > button {
      background-color: #800080;
      color: white !important;
      padding: 9px 18px;
      border-radius: 10px;
      border: none;
      font-weight: 600;
      min-width: 120px;
      font-size: 14px;
    }
    div.stButton > button:hover {
      background-color: #9932CC;
    }
    /* wide page container */
    .content-wrap {
      max-width: 1100px;
      margin: 30px auto;
      padding: 0 20px;
    }
    /* center headings/content on HOME and results */
    .center-text { text-align: center; }
    /* scrollable keyword boxes */
    .scroll-box {
      max-height: 220px;
      overflow-y: auto;
      padding: 10px;
      border: 1px solid #eee;
      border-radius: 6px;
      background: #fafafa;
    }
    @media (max-width: 900px) {
      div.stButton > button { min-width: 100px; padding: 8px 14px; font-size:13px; }
      .content-wrap { margin: 18px auto; max-width: 760px; }
    }
    @media (max-width: 480px) {
      div.stButton > button { min-width: 84px; padding: 7px 10px; font-size:12px; }
      .content-wrap { margin: 12px auto; max-width: 420px; padding: 0 10px; }
    }
    </style>
""", unsafe_allow_html=True)

# build header
st.markdown('<div class="header-wrap"><div class="nav-buttons">', unsafe_allow_html=True)
# produce buttons using Streamlit so they are interactive
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
# create a row of buttons
btn_cols = st.columns([1]*len(nav_map))
for i, (label, key) in enumerate(nav_map):
    with btn_cols[i]:
        if st.button(label, key=f"nav_{key}"):
            navigate_to(key)
st.markdown('</div></div>', unsafe_allow_html=True)

# ---------- Smooth scroll anchor helper ----------
def smooth_scroll_to_current():
    page_id = st.session_state.get("page", "home")
    safe_page = str(page_id).replace('"', '')
    scroll_js = f"""
    <script>
    (function() {{
        const pageId = "{safe_page}";
        setTimeout(function() {{
            const el = document.getElementById("section-" + pageId);
            if (el) {{
                el.scrollIntoView({{behavior: "smooth", block: "start"}});
            }}
        }}, 100);
    }})();
    </script>
    """
    st.markdown(scroll_js, unsafe_allow_html=True)

# ---------- Page implementations (preserve your original logic; replaced experimental_rerun) ----------
# Each page begins with an anchor div id="section-<page_key>" and all content wrapped in .content-wrap

def page_home():
    st.markdown('<div id="section-home"></div>', unsafe_allow_html=True)
    st.markdown('<div class="content-wrap center-text">', unsafe_allow_html=True)
    st.markdown("<h1 style='margin-bottom:8px'>Welcome — How Resume Analyzer Pro helps you</h1>", unsafe_allow_html=True)
    st.markdown("<div style='max-width:900px; margin: 0 auto; font-size:16px; color:#333'>"
                "<ul style='text-align:left; display:inline-block; margin:0; padding-left:20px;'>"
                "<li>Upload your resume (PDF / DOCX / TXT) or paste it — we'll extract and analyze it.</li>"
                "<li>Paste the Job Description (JD) you want to apply for.</li>"
                "<li>Get a percentage match, matched & missing keywords, and ATS formatting tips — instantly.</li>"
                "</ul>"
                "</div>", unsafe_allow_html=True)
    st.markdown("<p style='margin-top:18px'><strong>Try it:</strong> Click <span style='background:#eef7ee; padding:4px 8px; border-radius:6px'>Scanner</span> in the top nav and upload a resume to begin.</p>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

def page_scanner():
    st.markdown('<div id="section-scanner"></div>', unsafe_allow_html=True)
    st.markdown('<div class="content-wrap">', unsafe_allow_html=True)
    st.header("Resume Scanner")
    left, right = st.columns([1,1])
    with left:
        st.markdown("**Upload Resume (drag & drop or click)**")
        uploaded = st.file_uploader("", type=["pdf","docx","doc","txt"], key="upload_resume")
        st.markdown("---")
        st.markdown("**Or paste resume text (optional)**")
        resume_text_manual = st.text_area("", height=220, key="paste_resume")
        if uploaded:
            st.info(f"Uploaded: {uploaded.name}")
    with right:
        st.markdown("**Paste Job Description (JD)**")
        jd_text = st.text_area("", height=320, key="paste_jd")
        ck_linkedin = st.checkbox("Also optimize for LinkedIn summary (produce suggestions)", value=False, key="ck_linkedin")
        weight = st.slider("Importance weight: match vs. readability", 0.0, 1.0, 0.7, key="weight_slider")
    st.markdown("")  # spacing
    if st.button("Scan / Analyze", key="scan_analyze"):
        # Obtain resume text
        uploaded_obj = st.session_state.get("upload_resume")
        if uploaded_obj:
            rtext = extract_text_from_uploaded(uploaded_obj)
        else:
            rtext = (st.session_state.get("paste_resume", "") or "").strip()
        jd_val = (st.session_state.get("paste_jd", "") or "").strip()
        if not rtext:
            st.warning("Please provide resume text by uploading a file or pasting it.")
            return
        if not jd_val:
            st.warning("Please paste a job description to compare.")
            return

        # Compute
        score = compute_match_score(rtext, jd_val)
        matched, missing = get_keywords_and_missing(rtext, jd_val, top_n=500)
        warnings = simple_ats_checks(rtext)
        # suggestions
        suggestions = []
        if score < 40:
            suggestions.append("Increase keyword density for important JD terms. Add measurable outcomes and technical keywords.")
        elif score < 70:
            suggestions.append("You're on the right track. Add more role-specific keywords and quantify achievements.")
        else:
            suggestions.append("Great match — ensure formatting is ATS-friendly and proofread for clarity.")
        # linkedin suggestions
        linkedin_suggestions = None
        if ck_linkedin:
            linkedin_suggestions = [
                "Start headline with your role + one-line impact.",
                "Place top 4 technical keywords from JD near top of about summary.",
                "Add 2 quantifiable achievements and a contact CTA."
            ]
            # Make a short tailored LinkedIn suggestion that includes some matched keywords
            top_kw = matched[:6]
            if top_kw:
                linkedin_suggestions.insert(0, "Consider adding keywords: " + ", ".join(top_kw))

        # store result
        uploaded_name = uploaded_obj.name if uploaded_obj else ("pasted_resume.txt")
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
            "resume_name": uploaded_name
        }
        st.session_state.current_result = result
        st.session_state.scan_history.insert(0, result)
        st.session_state.page = "results"
        return
    st.markdown("</div>", unsafe_allow_html=True)

def page_results():
    st.markdown('<div id="section-results"></div>', unsafe_allow_html=True)
    st.markdown('<div class="content-wrap">', unsafe_allow_html=True)
    r = st.session_state.get("current_result")
    st.header("Match Results")
    if not r:
        st.info("No result to display. Run a scan first from the Scanner page.")
        st.markdown("</div>", unsafe_allow_html=True)
        return

    # Score and top row
    col1, col2 = st.columns([1,2])
    with col1:
        st.metric("Match Score", f"{r['score']}%")
    with col2:
        # quick actionable line
        st.markdown("<div style='font-weight:600'>Quick suggestions</div>", unsafe_allow_html=True)
        for s in r.get("suggestions", [])[:3]:
            st.write("• " + s)

    st.markdown("### Matched Keywords")
    matched = r.get("matched", [])
    if matched:
        st.markdown('<div class="scroll-box">', unsafe_allow_html=True)
        st.write(", ".join(matched))
        st.markdown('</div>', unsafe_allow_html=True)
    else:
        st.write("None found")

    st.markdown("### Missing Keywords (from JD)")
    missing = r.get("missing", [])
    if missing:
        st.markdown('<div class="scroll-box">', unsafe_allow_html=True)
        st.write(", ".join(missing))
        st.markdown('</div>', unsafe_allow_html=True)
    else:
        st.write("None")

    st.markdown("### ATS Formatting Warnings")
    if r.get("warnings"):
        for w in r["warnings"]:
            st.warning(w)
    else:
        st.success("No obvious ATS formatting problems found.")

    # LinkedIn suggestions block (if available)
    if r.get("linkedin_suggestions"):
        st.markdown("### LinkedIn Optimization Suggestions")
        for s in r["linkedin_suggestions"]:
            st.write("• " + s)

    st.markdown("---")
    st.markdown("**Resume excerpt:**")
    st.code(r.get("resume_text_excerpt", "")[:5000])
    st.markdown(get_download_link(r.get("resume_text_excerpt",""), filename="extracted_resume.txt"), unsafe_allow_html=True)

    if st.button("Scan another resume", key="scan_another"):
        st.session_state.page = "scanner"
        return

    st.markdown("</div>", unsafe_allow_html=True)

def page_dashboard():
    st.markdown('<div id="section-dashboard"></div>', unsafe_allow_html=True)
    st.markdown('<div class="content-wrap">', unsafe_allow_html=True)
    st.header("Dashboard — Recent Scans (session only)")
    history = st.session_state.get("scan_history", [])
    if not history:
        st.info("No scans yet. Run a scan on the Scanner page.")
        st.markdown("</div>", unsafe_allow_html=True)
        return
    for item in history[:50]:
        st.markdown("---")
        ts = item.get("timestamp", "")
        st.write(f"**Date:** {ts}  |  **Score:** {item.get('score')}%  |  **Resume:** {item.get('resume_name')}")
        st.write("Matched: " + (", ".join(item.get("matched", [])[:30]) or "None"))
        st.write("Missing: " + (", ".join(item.get("missing", [])[:30]) or "None"))
    st.markdown("</div>", unsafe_allow_html=True)

def page_cover_letter():
    st.markdown('<div id="section-cover_letter"></div>', unsafe_allow_html=True)
    st.markdown('<div class="content-wrap">', unsafe_allow_html=True)
    st.header("Cover Letter Analyzer")
    st.markdown("**Upload cover letter (drag & drop or click)**")
    cover_file = st.file_uploader("", type=["pdf","docx","doc","txt"], key="cover_upload")
    st.markdown("---")
    st.markdown("**Or paste cover letter text**")
    cover_text = st.text_area("", height=260, key="cover_text")
    st.markdown("")
    if st.button("Analyze Cover Letter", key="analyze_cover"):
        # extract text
        if cover_file:
            ctext = extract_text_from_uploaded(cover_file)
        else:
            ctext = (st.session_state.get("cover_text", "") or "").strip()
        if not ctext:
            st.warning("Please upload or paste a cover letter.")
            return
        tips = []
        tips.append("Open with a strong one-line introduction (role + impact).")
        if len(ctext.split()) < 100:
            tips.append("Cover letter is short. Aim for ~200-300 words.")
        st.success("Basic checks completed.")
        for t in tips:
            st.write("• " + t)
    st.markdown("</div>", unsafe_allow_html=True)

def page_linkedin():
    st.markdown('<div id="section-linkedin"></div>', unsafe_allow_html=True)
    st.markdown('<div class="content-wrap">', unsafe_allow_html=True)
    st.header("LinkedIn Optimizer")
    st.info("Paste your LinkedIn 'About' summary and an optional JD for contextual suggestions.")
    summary = st.text_area("Paste LinkedIn Summary", height=260, key="linkedin_summary")
    jd = st.text_area("Paste Job Description (optional)", height=200, key="linkedin_jd")
    if st.button("Optimize LinkedIn", key="opt_linkedin"):
        if not summary.strip():
            st.warning("Please paste your LinkedIn summary.")
            return
        suggestions = []
        suggestions.append("Start with role + impact in the first sentence.")
        suggestions.append("Add top 4 technical keywords from JD near the top.")
        if jd.strip():
            matched, missing = get_keywords_and_missing(summary, jd, top_n=20)
            suggestions.append(f"Keywords present: {', '.join(matched[:8])}" if matched else "No JD keywords found in summary.")
            if missing:
                suggestions.append(f"Consider adding: {', '.join(missing[:8])}")
        suggestions.append("Add a CTA for contact and 2 quantifiable achievements.")
        for s in suggestions:
            st.write("• " + s)
    st.markdown("</div>", unsafe_allow_html=True)

def page_tracker():
    st.markdown('<div id="section-job_tracker"></div>', unsafe_allow_html=True)
    st.markdown('<div class="content-wrap">', unsafe_allow_html=True)
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
    if st.session_state.get("job_tracker"):
        for e in st.session_state.job_tracker:
            st.markdown(f"- {e['date']} — **{e['title']}** at *{e['company']}* — {e['status']}")
    st.markdown("</div>", unsafe_allow_html=True)

def page_account():
    st.markdown('<div id="section-account"></div>', unsafe_allow_html=True)
    st.markdown('<div class="content-wrap">', unsafe_allow_html=True)
    st.header("Account (session-only) — simplified auth")
    if st.session_state.user:
        st.success(f"Signed in as **{st.session_state.user.get('name')}** ({st.session_state.user.get('email')})")
        if st.button("Logout", key="logout_btn"):
            st.session_state.user = None
            st.session_state.page = "home"
            return
        st.markdown("</div>", unsafe_allow_html=True)
        return
    # Registration
    st.subheader("Sign Up")
    su_name = st.text_input("Full name", key="su_name")
    su_email = st.text_input("Email", key="su_email")
    su_pwd = st.text_input("Password", type="password", key="su_pwd")
    if st.button("Register", key="register_btn"):
        hashed = bcrypt.hash(su_pwd or "temp123")
        st.session_state.last_registration = {"name": su_name, "email": su_email, "hashed": hashed}
        st.session_state.last_login_prefill = {"email": su_email or "", "password": su_pwd or ""}
        st.success("Registration successful. Please log in (we prefilled your login).")
    st.markdown("---")
    st.subheader("Login")
    li_email = st.text_input("Email", key="li_email", value=st.session_state.last_login_prefill.get("email",""))
    li_pwd = st.text_input("Password", type="password", key="li_pwd", value=st.session_state.last_login_prefill.get("password",""))
    if st.button("Login", key="login_btn"):
        user = {"id": 1, "name": st.session_state.last_registration.get("name","Guest") if st.session_state.last_registration else "Guest", "email": li_email}
        st.session_state.user = user
        st.success("Logged in successfully.")
        st.session_state.page = "dashboard"
        return
    st.markdown("</div>", unsafe_allow_html=True)

# ---------- Router (single-page) ----------
page = st.session_state.page

if page == "home":
    page_home()
elif page == "scanner":
    page_scanner()
elif page == "results":
    page_results()
elif page == "dashboard":
    page_dashboard()
elif page == "cover_letter":
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
