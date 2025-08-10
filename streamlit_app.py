# streamlit_app.py
"""
Final single-file Resume Analyzer (session-only mode).
- Keeps your original UI layout & nav (minimal UI changes).
- Improved backend logic: TF-IDF cosine similarity (sklearn if available, fallback to simple cosine),
  keyword extraction, lightweight stemming-like normalization, prioritized missing keywords,
  actionable suggestions, improved Cover Letter & LinkedIn checks.
- No DB. Session-only.
"""

import streamlit as st
from datetime import datetime
from io import BytesIO
import re
import os
import base64
import math
from collections import Counter

# optional libs - prefer sklearn if available for TF-IDF; otherwise fallback
try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    SKLEARN_AVAILABLE = True
except Exception:
    SKLEARN_AVAILABLE = False

# optional file readers
try:
    import PyPDF2
except Exception:
    PyPDF2 = None

try:
    import docx
except Exception:
    docx = None

# Keep bcrypt import optional (you used passlib.hash)
try:
    from passlib.hash import bcrypt
except Exception:
    bcrypt = None

import numpy as np

# Page config
st.set_page_config(page_title="Resume Analyzer Pro", page_icon="🚀", layout="wide")

# ---------- Utilities: file extraction ----------
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

# ---------- Text normalization & lightweight stemming ----------
TOKEN_RE = re.compile(r"\b[a-z0-9\+\#\-\.]+\b", re.I)

def normalize_word(w: str):
    """Lowercase and apply light stemming heuristics (remove common suffixes)."""
    w = w.lower()
    # strip punctuation (already tokenized usually)
    w = re.sub(r'[^a-z0-9\+\#\-\.]', '', w)
    # light stemming heuristics (not a full stemmer, but helps match variants)
    for suf in ('ings','ing','ed','es','s','ment'):
        if w.endswith(suf) and len(w) - len(suf) >= 3:
            return w[: -len(suf)]
    return w

def tokenize(s: str):
    if not s:
        return []
    tokens = TOKEN_RE.findall(s.lower())
    return [normalize_word(t) for t in tokens if t.strip()]

# ---------- TF-IDF & similarity (sklearn if available, else fallback) ----------
def compute_match_score(resume_text: str, jd_text: str):
    r = (resume_text or "").strip()
    j = (jd_text or "").strip()
    if not r or not j:
        return 0.0
    if SKLEARN_AVAILABLE:
        try:
            # Use scikit-learn TF-IDF + cosine similarity
            vec = TfidfVectorizer(token_pattern=r"(?u)\b\w+\b", lowercase=True)
            mats = vec.fit_transform([r, j])
            sim = cosine_similarity(mats[0:1], mats[1:2])[0][0]
            return round(float(sim) * 100, 2)
        except Exception:
            pass
    # Fallback: normalized bag-of-words cosine
    r_tokens = tokenize(r)
    j_tokens = tokenize(j)
    vocab = sorted(set(r_tokens + j_tokens))
    vocab_index = {w: i for i, w in enumerate(vocab)}
    def build_vec(tokens):
        vec = np.zeros(len(vocab_index), dtype=float)
        for t in tokens:
            if t in vocab_index:
                vec[vocab_index[t]] += 1.0
        if np.linalg.norm(vec) > 0:
            return vec / np.linalg.norm(vec)
        return vec
    rvec = build_vec(r_tokens)
    jvec = build_vec(j_tokens)
    denom = (np.linalg.norm(rvec) * np.linalg.norm(jvec))
    if denom == 0:
        return 0.0
    sim = float(np.dot(rvec, jvec))
    return round(sim * 100, 2)

# ---------- Keywords extraction & prioritization ----------
def extract_top_terms(text: str, top_n=60, min_len=3):
    tokens = tokenize(text)
    tokens = [t for t in tokens if len(t) >= min_len]
    counts = Counter(tokens)
    most = counts.most_common(top_n)
    return [w for w,c in most], {w:c for w,c in most}

def get_keywords_and_missing(resume_text: str, jd_text: str, top_n=50):
    jd_terms_list, jd_freq = extract_top_terms(jd_text, top_n)
    r_tokens = set(tokenize(resume_text))
    matched = [t for t in jd_terms_list if t in r_tokens]
    missing = [t for t in jd_terms_list if t not in r_tokens]
    # sort missing by jd frequency (already in that order), ensure uniqueness
    return matched[:top_n], missing[:top_n]

# ---------- ATS checks & heuristics ----------
def simple_ats_checks(resume_text: str):
    checks = []
    if not resume_text:
        return checks
    if "\t" in resume_text or re.search(r" {4,}", resume_text):
        checks.append("Possible columns or table-like formatting — convert to simple vertical layout.")
    if "<img" in resume_text.lower() or "image:" in resume_text.lower():
        checks.append("Images detected — remove images for ATS-friendly resume.")
    if len(resume_text.splitlines()) < 6 or len(resume_text.split()) < 140:
        checks.append("Resume looks short — aim for 1–2 pages with 4–6 bullets per recent role.")
    if re.search(r"[■♦▸►]", resume_text):
        checks.append("Unusual bullet characters detected — use standard hyphens or simple bullets.")
    return checks

def detect_quantifications(text: str):
    nums = re.findall(r"\b\d{1,3}%|\b\d{2,4}\b", text)
    return len(nums) > 0, nums[:10]

# ---------- Suggestions generator ----------
def generate_actionable_suggestions(score_pct, matched, missing, resume_text, jd_freq=None):
    suggestions = []
    if score_pct >= 85:
        suggestions.append("Excellent alignment. Minor wording & formatting polish recommended.")
    elif score_pct >= 65:
        suggestions.append("Good match — add some high-priority JD keywords and metrics to boost further.")
    elif score_pct >= 40:
        suggestions.append("Partial match — prioritize top missing keywords and quantify achievements.")
    else:
        suggestions.append("Low match — update resume to include role-specific skills, responsibilities and keywords from the JD.")

    if missing:
        suggestions.append("Top missing keywords to add: " + ", ".join(missing[:8]))

    has_q, nums = detect_quantifications(resume_text)
    if not has_q:
        suggestions.append("Add quantifiable outcomes (numbers, %, metrics) to your bullets.")
    else:
        suggestions.append("Quantified items detected: " + ", ".join(nums))

    ats = simple_ats_checks(resume_text)
    if ats:
        suggestions.append("ATS & formatting fixes: " + " | ".join(ats))

    if matched:
        suggestions.append("For LinkedIn: place top 4 matched keywords in your headline and the first two lines of About.")
    return suggestions

# ---------- Download helper ----------
def get_download_link(text, filename="resume.txt"):
    b64 = base64.b64encode(text.encode()).decode()
    href = f'<a href="data:file/txt;base64,{b64}" download="{filename}">Download extracted text</a>'
    return href

# ---------- Session init ----------
if "page" not in st.session_state:
    st.session_state.page = "home"
if "current_result" not in st.session_state:
    st.session_state.current_result = None
if "scan_history" not in st.session_state:
    st.session_state.scan_history = []
if "paste_resume" not in st.session_state:
    st.session_state.paste_resume = ""

# ---------- Navigation helper ----------
def navigate_to(page_name: str):
    st.session_state.page = page_name

# ---------- Header / Top-nav (centered, responsive) ----------
st.markdown("""
    <style>
    .header-wrap {
      display:flex;
      justify-content:center;
      align-items:center;
      padding:12px 0;
      border-bottom:1px solid #eee;
      background: #ffffff;
      position: sticky;
      top: 0;
      z-index: 9999;
    }
    .nav-container {
      display:flex;
      gap: 18px;             /* increased gap for spacing between buttons */
      align-items:center;
      justify-content:center;
      flex-wrap:wrap;
      max-width: 1200px;
      width: 100%;
      padding: 0 12px;
    }
    div.stButton > button {
      background-color: #800080;
      color: white !important;
      padding: 8px 18px;
      border-radius: 8px;
      border: none;
      font-weight: 600;
      min-width: 110px;
      font-size: 14px;
      margin: 0 6px;         /* add breathing room around each button */
    }
    div.stButton > button:hover {
      background-color: #9932CC;
    }
    .content-wrap { max-width: 1100px; margin: 28px auto; padding: 0 18px; }
    .center-text { text-align: center; }
    .scroll-box { max-height: 220px; overflow-y: auto; padding: 10px; border: 1px solid #eee; border-radius: 6px; background: #fafafa; }
    .chip { display:inline-block; padding:6px 10px; margin:4px; border-radius:12px; font-size:13px; }
    .chip-match { background:#e6f4ea; color:#155724; border:1px solid #c6eed3; }
    .chip-miss { background:#fff0f0; color:#7a1a1a; border:1px solid #f5c6cb; }
    @media (max-width: 900px) {
      div.stButton > button { min-width: 96px; padding: 7px 12px; font-size: 13px; }
      .content-wrap { margin: 18px auto; max-width: 760px; }
    }
    @media (max-width: 480px) {
      div.stButton > button { min-width: 84px; padding: 6px 10px; font-size: 12px; }
      .content-wrap { margin: 12px auto; max-width: 420px; padding: 0 10px; }
    }
    </style>
""", unsafe_allow_html=True)

# header with optional logo left (keeps visual balance) and centered nav
cols = st.columns([1,6,1])
with cols[0]:
    logo_path = "logo.png"
    if os.path.exists(logo_path):
        st.image(logo_path, width=56)
    else:
        st.write("")  # placeholder to keep header centered
with cols[1]:
    nav_items = [
        ("HOME", "home"),
        ("Scanner", "scanner"),
        ("Results", "results"),
        ("Dashboard", "dashboard"),
        ("Cover Letter", "cover_letter"),
        ("LinkedIn", "linkedin"),
        ("Job Tracker", "job_tracker"),
        ("Account", "account")
    ]
    nav_cols = st.columns([1]*len(nav_items))
    for i, (label, key) in enumerate(nav_items):
        with nav_cols[i]:
            if st.button(label, key=f"nav_{key}"):
                navigate_to(key)
with cols[2]:
    st.write("")

# ---------- Smooth scroll helper ----------
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
        }}, 120);
    }})();
    </script>
    """
    st.markdown(scroll_js, unsafe_allow_html=True)

# ---------- Pages (UI preserved, backend improved) ----------
def page_home():
    st.markdown('<div id="section-home"></div>', unsafe_allow_html=True)
    st.markdown('<div class="content-wrap center-text">', unsafe_allow_html=True)
    st.markdown("<h1 style='margin-bottom:6px'>Welcome — How Resume Analyzer Pro helps you</h1>", unsafe_allow_html=True)
    st.markdown("<div style='max-width:900px; margin: 0 auto; font-size:16px; color:#333'>"
                "<ul style='text-align:left; display:inline-block; margin:0; padding-left:20px;'>"
                "<li>Upload your resume (PDF / DOCX / TXT) or paste it — we'll extract and analyze it.</li>"
                "<li>Paste the Job Description (JD) you want to apply for.</li>"
                "<li>Get a percentage match, prioritized matched & missing keywords, and ATS formatting tips — instantly.</li>"
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
        # keep session copy
        if resume_text_manual is not None:
            st.session_state.paste_resume = resume_text_manual
        if uploaded:
            st.info(f"Uploaded: {uploaded.name}")
    with right:
        st.markdown("**Paste Job Description (JD)**")
        jd_text = st.text_area("", height=320, key="paste_jd")
        ck_linkedin = st.checkbox("Also optimize for LinkedIn summary (produce suggestions)", value=False, key="ck_linkedin")
        weight = st.slider("Importance weight: match vs. readability", 0.0, 1.0, 0.7, key="weight_slider")
    st.markdown("")  # spacing
    if st.button("Scan / Analyze", key="scan_analyze"):
        # get resume text
        uploaded_obj = uploaded  # local variable
        if uploaded_obj:
            rtext = extract_text_from_uploaded(uploaded_obj) or ""
        else:
            rtext = (st.session_state.get("paste_resume", "") or "").strip()
        jd_val = (st.session_state.get("paste_jd", "") or "").strip()
        if not rtext:
            st.warning("Please provide resume text by uploading a file or pasting it.")
            return
        if not jd_val:
            st.warning("Please paste a job description to compare.")
            return

        score = compute_match_score(rtext, jd_val)
        matched, missing = get_keywords_and_missing(rtext, jd_val, top_n=200)
        warnings = simple_ats_checks(rtext)
        suggestions = generate_actionable_suggestions(score, matched, missing, rtext)
        linkedin_suggestions = None
        if ck_linkedin:
            linkedin_suggestions = []
            top_kw = matched[:6]
            if top_kw:
                linkedin_suggestions.append("Consider adding keywords: " + ", ".join(top_kw))
            linkedin_suggestions.extend([
                "Start headline with your role + one-line impact.",
                "Place top 4 technical keywords from JD near top of About summary.",
                "Add 2 quantifiable achievements and a contact CTA."
            ])

        uploaded_name = uploaded_obj.name if uploaded_obj else "pasted_resume.txt"
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
            "resume_name": uploaded_name,
            "full_resume": rtext,
            "full_jd": jd_val
        }
        st.session_state.current_result = result
        st.session_state.scan_history.insert(0, result)
        st.session_state.page = "results"
        return
    st.markdown("</div>", unsafe_allow_html=True)

def render_chips(words, kind="match", limit=100):
    if not words:
        return "<div class='small'>None</div>"
    cls = "chip-match" if kind == "match" else "chip-miss"
    html = " ".join([f"<span class='chip {cls}'>{w}</span>" for w in words[:limit]])
    return html

def page_results():
    st.markdown('<div id="section-results"></div>', unsafe_allow_html=True)
    st.markdown('<div class="content-wrap">', unsafe_allow_html=True)
    r = st.session_state.get("current_result")
    st.header("Match Results")
    if not r:
        st.info("No result to display. Run a scan first from the Scanner page.")
        st.markdown("</div>", unsafe_allow_html=True)
        return

    # Score card + quick suggestions
    col_score, col_detail = st.columns([1,2])
    with col_score:
        # big visual score
        score_val = r.get("score", 0)
        color = "#28a745" if score_val >= 70 else "#ffc107" if score_val >= 40 else "#dc3545"
        st.markdown(f"""
            <div style='background:#f6f0fb; padding:18px; border-radius:12px; text-align:center;'>
              <div style='font-size:36px; font-weight:800; color:{color};'>{score_val}%</div>
              <div style='color:gray; margin-top:6px;'>Match Score</div>
            </div>
        """, unsafe_allow_html=True)

    with col_detail:
        st.markdown("<div style='font-weight:600; margin-bottom:6px;'>Quick suggestions</div>", unsafe_allow_html=True)
        for s in r.get("suggestions", [])[:4]:
            st.write("• " + s)

    # top keywords (compact)
    st.markdown("### Top matches & gaps")
    matched = r.get("matched", [])
    missing = r.get("missing", [])
    # show top 10 each
    st.markdown("<div style='display:flex; gap:18px; flex-wrap:wrap;'>", unsafe_allow_html=True)
    st.markdown("<div style='flex:1; min-width:300px;'>", unsafe_allow_html=True)
    st.markdown("<div style='font-weight:700; margin-bottom:6px;'>✅ Top used keywords</div>", unsafe_allow_html=True)
    st.markdown(render_chips(matched, kind="match", limit=10), unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("<div style='flex:1; min-width:300px;'>", unsafe_allow_html=True)
    st.markdown("<div style='font-weight:700; margin-bottom:6px;'>❌ Top missing keywords (prioritized)</div>", unsafe_allow_html=True)
    st.markdown(render_chips(missing, kind="miss", limit=10), unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    # compact ATS & LinkedIn suggestions
    st.markdown("<br/>")
    col_a, col_b = st.columns([1,1])
    with col_a:
        st.markdown("<div style='font-weight:700; margin-bottom:6px;'>⚠️ ATS & Formatting Checks</div>", unsafe_allow_html=True)
        if r.get("warnings"):
            for w in r["warnings"]:
                st.warning(w)
        else:
            st.success("No obvious ATS formatting problems found.")
    with col_b:
        st.markdown("<div style='font-weight:700; margin-bottom:6px;'>🔗 LinkedIn Suggestions</div>", unsafe_allow_html=True)
        if r.get("linkedin_suggestions"):
            for s in r.get("linkedin_suggestions", []):
                st.write("• " + s)
        else:
            st.write("• Start headline with role + impact.")
            st.write("• Add top 4 JD keywords in the About section.")

    # details expander
    st.markdown("---")
    with st.expander("View detailed analysis and full lists"):
        st.markdown("**All matched keywords (from JD)**")
        st.markdown(render_chips(matched, kind="match", limit=500), unsafe_allow_html=True)
        st.markdown("**All missing keywords (from JD)**")
        st.markdown(render_chips(missing, kind="miss", limit=500), unsafe_allow_html=True)
        st.markdown("**Resume excerpt**")
        st.code(r.get("resume_text_excerpt", "")[:8000])
        st.markdown(get_download_link(r.get("resume_text_excerpt",""), filename="extracted_resume.txt"), unsafe_allow_html=True)

    st.markdown("<br/>")
    if st.button("Scan another resume", key="scan_another"):
        st.session_state.page = "scanner"
        return
    st.markdown("</div>", unsafe_allow_html=True)

def page_dashboard():
    st.markdown('<div id="section-dashboard"></div>', unsafe_allow_html=True)
    st.markdown('<div class="content-wrap">', unsafe_allow_html=True)
    st.header("Dashboard — Recent Scans")
    history = st.session_state.get("scan_history", [])
    if not history:
        st.info("No scans yet. Run a scan on the Scanner page.")
        st.markdown("</div>", unsafe_allow_html=True)
        return
    # show as clean table
    rows = []
    for item in history:
        rows.append({
            "Date": item.get("timestamp",""),
            "Score": f"{item.get('score')}%",
            "Resume": item.get("resume_name","")
        })
    st.table(rows)
    for item in history[:10]:
        st.markdown("---")
        st.write(f"**{item.get('resume_name','')}** — {item.get('timestamp','')} — **{item.get('score')}%**")
        st.write("Matched: " + (", ".join(item.get("matched", [])[:20]) or "None"))
        st.write("Missing: " + (", ".join(item.get("missing", [])[:20]) or "None"))
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
    st.markdown("**(Optional)** Paste Job Description for contextual suggestions")
    cover_jd = st.text_area("", height=160, key="cover_jd")
    if st.button("Analyze Cover Letter", key="analyze_cover"):
        if cover_file:
            ctext = extract_text_from_uploaded(cover_file) or ""
        else:
            ctext = (st.session_state.get("cover_text", "") or "").strip()
        if not ctext:
            st.warning("Please upload or paste a cover letter.")
            return
        tips = []
        # opening line
        first_line = ""
        for ln in ctext.splitlines():
            if ln.strip():
                first_line = ln.strip()
                break
        if not first_line or len(first_line.split()) < 6:
            tips.append("Start with a strong one-line opener mentioning the role & impact.")
        if len(ctext.split()) < 160:
            tips.append("Cover letter is short. Aim for ~200–350 words for good context.")
        # JD keyword overlap
        if cover_jd and cover_jd.strip():
            matched, missing = get_keywords_and_missing(ctext, cover_jd, top_n=80)
            tips.append("Keywords from JD present: " + (", ".join(matched[:8]) or "None"))
            if missing:
                tips.append("Consider adding (priority): " + ", ".join(missing[:8]))
        # quant
        has_q, nums = detect_quantifications(ctext)
        if not has_q:
            tips.append("Add 1–2 quantified achievements (numbers or %) to strengthen impact.")
        else:
            tips.append("Quantified items found: " + ", ".join(nums[:5]))
        st.success("Cover letter analysis complete.")
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
        suggestions.append("Add top 4 technical keywords from JD near the top (if applicable).")
        if jd.strip():
            matched, missing = get_keywords_and_missing(summary, jd, top_n=40)
            suggestions.append(f"Keywords present: {', '.join(matched[:8])}" if matched else "No JD keywords found in summary.")
            if missing:
                suggestions.append(f"Consider adding: {', '.join(missing[:8])}")
        has_q, nums = detect_quantifications(summary)
        if not has_q:
            suggestions.append("Add 1–2 quantifiable achievements in the first 2–3 lines.")
        else:
            suggestions.append("Quantified items found: " + ", ".join(nums[:6]))
        suggestions.append("Include a simple CTA (e.g., 'Open to roles — contact: you@example.com').")
        for s in suggestions:
            st.write("• " + s)
    st.markdown("</div>", unsafe_allow_html=True)

def page_tracker():
    st.markdown('<div id="section-job_tracker"></div>', unsafe_allow_html=True)
    st.markdown('<div class="content-wrap">', unsafe_allow_html=True)
    st.header("Job Tracker")
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
        st.session_state.job_tracker.insert(0, entry)
        st.success("Added to tracker.")
    if st.session_state.get("job_tracker"):
        for e in st.session_state.job_tracker:
            st.markdown(f"- {e['date']} — **{e['title']}** at *{e['company']}* — {e['status']}")
    st.markdown("</div>", unsafe_allow_html=True)

def page_account():
    st.markdown('<div id="section-account"></div>', unsafe_allow_html=True)
    st.markdown('<div class="content-wrap">', unsafe_allow_html=True)
    st.header("Account — simplified auth")
    if st.session_state.get("user"):
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
        if bcrypt:
            hashed = bcrypt.hash(su_pwd or "temp123")
        else:
            hashed = "session-placeholder"
        st.session_state.last_registration = {"name": su_name, "email": su_email, "hashed": hashed}
        st.session_state.last_login_prefill = {"email": su_email or "", "password": su_pwd or ""}
        st.success("Registration successful. Please log in (session-only).")
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

# ---------- Router ----------
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
