# streamlit_app.py
"""
Resume Analyzer Pro — Jobscan-style single-file Streamlit app (no DB).
Features:
- Upload PDF/DOCX/TXT or paste resume and paste JD
- Jobscan-like top metrics: Match Rate, Searchability, Hard Skills, Soft Skills, Recruiter Tips, Formatting
- Clickable metrics (scroll to sections)
- Category-based keyword matching (Hard/Soft/Action verbs)
- ATS checks (contact info, sections, job title, dates, education, formatting)
- Defensive: optional libraries (PyPDF2, docx, sklearn) handled gracefully
No database. All session-state only.
"""

import streamlit as st
from datetime import datetime
from io import BytesIO
import re
import os
import base64
from collections import Counter
import math

# Optional libs
try:
    import PyPDF2
except Exception:
    PyPDF2 = None

try:
    import docx
except Exception:
    docx = None

# Optional sklearn for TF-IDF
try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    SKLEARN_AVAILABLE = True
except Exception:
    SKLEARN_AVAILABLE = False

import numpy as np

# Page config
st.set_page_config(page_title="Resume Analyzer Pro", page_icon="🚀", layout="wide")

# -------------------------
# Safe session defaults
# -------------------------
DEFAULTS = {
    "page": "home",
    "user": None,
    "scan_history": [],
    "current_result": None,
    "paste_resume": "",
    "paste_jd": "",
    "paste_cover_letter": "",
    "paste_linkedin": ""
}
for k, v in DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v

# -------------------------
# Simple stopword list (no NLTK required)
# -------------------------
STOPWORDS = set("""
a about above after again against all am an and any are aren't as at be because been before being below between both but by
could couldn't did didn't do does doesn't doing don't down during each few for from further had hadn't has hasn't have haven't
having he he'd he'll he's her here here's hers herself him himself his how how's i i'd i'll i'm i've if in into is isn't it
it's its itself let's me more most mustn't my myself no nor not of off on once only or other ought our ours ourselves out over
own same shan't she she'd she'll she's should shouldn't so some such than that that's the their theirs them themselves then there
there's these they they'd they'll they're they've this those through to too under until up very was wasn't we we'd we'll we're we've
were weren't what what's when when's where where's which while who who's whom why why's with won't would wouldn't you you'd you'll
you're you've your yours yourself yourselves the s t
""".split())

# -------------------------
# Expanded keyword sets (Java-focused + general)
# -------------------------
HARD_SKILLS = {
    "java", "core java", "spring", "spring boot", "hibernate", "jpa", "microservices", "rest", "rest api",
    "restful", "postgre", "postgresql", "mysql", "mariadb", "oracle", "sql", "nosql", "mongodb",
    "junit", "mockito", "maven", "gradle", "docker", "kubernetes", "k8s", "aws", "azure", "gcp",
    "jdbc", "jsp", "servlet", "spring mvc", "spring security", "redis", "rabbitmq", "kafka",
    "ci cd", "jenkins", "git", "github", "gitlab", "bitbucket", "graphql", "soap", "hibernate orm",
    "design patterns", "data structures", "algorithms", "multithreading", "concurrency", "rest api development",
    "unit testing", "integration testing", "performance tuning"
}

SOFT_SKILLS = {
    "communication", "teamwork", "collaboration", "leadership", "problem solving", "adaptability",
    "time management", "mentoring", "coaching", "critical thinking", "attention to detail",
    "constructive feedback", "client facing", "stakeholder management"
}

ACTION_VERBS = {
    "develop", "design", "implement", "build", "maintain", "optimize", "lead", "manage", "create",
    "improve", "deploy", "test", "debug", "integrate", "automate", "document", "refactor"
}

# -------------------------
# Utilities: extract text
# -------------------------
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
        document = docx.Document(bio)
        paragraphs = [p.text for p in document.paragraphs if p.text]
        return "\n".join(paragraphs)
    except Exception:
        return ""

def extract_text_from_uploaded(uploaded_file):
    if uploaded_file is None:
        return ""
    name = uploaded_file.name.lower()
    raw = uploaded_file.read()
    if name.endswith(".pdf"):
        text = safe_extract_text_from_pdf(raw)
        if text:
            return text
    if name.endswith(".docx") or name.endswith(".doc"):
        text = safe_extract_text_from_docx(raw)
        if text:
            return text
    try:
        return raw.decode("utf-8", errors="ignore")
    except Exception:
        try:
            return raw.decode("latin-1", errors="ignore")
        except Exception:
            return ""

# -------------------------
# Text normalization & tokenization
# -------------------------
TOKEN_RE = re.compile(r"\b[a-zA-Z\+\#0-9\-]+\b")

def normalize_word(w: str):
    w = w.lower()
    # strip punctuation-like -._ at ends
    w = re.sub(r'^[^a-z0-9]+|[^a-z0-9]+$', '', w)
    # light stemming heuristics
    for suf in ('ings','ing','ed','es','s'):
        if w.endswith(suf) and len(w) - len(suf) >= 2:
            return w[: -len(suf)]
    return w

def tokenize(text: str):
    if not text:
        return []
    tokens = TOKEN_RE.findall(text)
    norm = [normalize_word(t) for t in tokens if t]
    filtered = [t for t in norm if t and t not in STOPWORDS and len(t) >= 2]
    return filtered

# -------------------------
# Section detection heuristics
# -------------------------
def detect_sections(text: str):
    lowered = text.lower()
    has_summary = bool(re.search(r'\bsummary\b|\babout\b|\bprofile\b', lowered))
    has_education = bool(re.search(r'\beducation\b|\bdegree\b|\bgraduat', lowered))
    has_experience = bool(re.search(r'\bexperience\b|\bwork history\b|\bemployment\b|\bprojects\b', lowered))
    return {"summary": has_summary, "education": has_education, "experience": has_experience}

# -------------------------
# Simple ATS checks
# -------------------------
def simple_ats_checks(resume_text: str):
    issues = []
    if not resume_text:
        return issues
    # columns / tables detection: many long spaces or tabs
    if "\t" in resume_text or re.search(r' {4,}', resume_text):
        issues.append("Possible columns or table-like formatting — convert to a simple vertical layout.")
    # images
    if "<img" in resume_text.lower() or "image:" in resume_text.lower():
        issues.append("Images detected — remove images for ATS-friendly resume.")
    # bullets: weird bullets
    if re.search(r"[■♦▸►✦]", resume_text):
        issues.append("Unusual bullet characters detected — use simple hyphens or standard bullets.")
    # length
    words = len(resume_text.split())
    if words < 200:
        issues.append("Resume looks short — aim for ~400–1000 words depending on experience.")
    return issues

def detect_contact_info(resume_text: str):
    info = {"email": False, "phone": False, "address": False, "linkedin": False, "website": False}
    if not resume_text:
        return info
    if re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", resume_text):
        info["email"] = True
    if re.search(r"(?<!\d)(?:\+?\d{1,3}[-.\s]?)?(?:\(?\d{2,4}\)?[-.\s]?)?\d{6,10}(?!\d)", resume_text):
        info["phone"] = True
    # address heuristics: presence of city/state keywords or pin codes
    if re.search(r"\b(city|state|province|street|road|ave|avenue|lane|pune|mumbai|delhi|bangalore|hyderabad)\b", resume_text.lower()) or re.search(r"\b\d{5,6}\b", resume_text):
        info["address"] = True
    if "linkedin.com" in resume_text.lower():
        info["linkedin"] = True
    if re.search(r"https?://(www\.)?[a-z0-9\-_]+\.[a-z]{2,}", resume_text.lower()):
        info["website"] = True
    return info

# -------------------------
# Keyword extraction & scoring
# -------------------------
def extract_top_terms(text: str, top_n=100):
    toks = tokenize(text)
    if not toks:
        return [], {}
    counts = Counter(toks)
    most = counts.most_common(top_n)
    return [w for w, c in most], {w: c for w, c in most}

def categorize_and_compare(resume_text: str, jd_text: str):
    # build freq dictionaries
    jd_tokens = tokenize(jd_text)
    r_tokens = tokenize(resume_text)
    jd_counts = Counter(jd_tokens)
    r_counts = Counter(r_tokens)

    # find matches within category sets (use normalized tokens)
    hard_req = {w for w in HARD_SKILLS if any(part in " ".join(jd_tokens) for part in [w])}
    soft_req = {w for w in SOFT_SKILLS if any(part in " ".join(jd_tokens) for part in [w])}
    verb_req = {w for w in ACTION_VERBS if any(part in " ".join(jd_tokens) for part in [w])}

    # map normalized keyword to token form - treat multi-word keys by splitting
    def present_set(req_set, source_counts):
        present = {}
        missing = {}
        for kw in sorted(req_set):
            parts = [normalize_word(p) for p in kw.split()]
            # approximate membership by checking presence of main token
            main = parts[-1] if parts else kw
            present_count = sum(v for k, v in source_counts.items() if main in k or kw in k)
            if present_count > 0:
                present[kw] = present_count
            else:
                missing[kw] = 0
        return present, missing

    hard_matched, hard_missing = present_set(hard_req, r_counts)
    soft_matched, soft_missing = present_set(soft_req, r_counts)
    verb_matched, verb_missing = present_set(verb_req, r_counts)

    # fallback: detect top jd terms not in resume
    jd_top, jd_freq = extract_top_terms(jd_text, top_n=150)
    matched_simple = [t for t in jd_top if t in r_counts]
    missing_simple = [t for t in jd_top if t not in r_counts]

    return {
        "hard": {"matched": hard_matched, "missing": hard_missing},
        "soft": {"matched": soft_matched, "missing": soft_missing},
        "verb": {"matched": verb_matched, "missing": verb_missing},
        "matched_simple": matched_simple,
        "missing_simple": missing_simple,
        "jd_freq": jd_freq,
        "r_counts": r_counts
    }

def compute_weighted_score(cat_compare):
    # weights
    w_hard = 0.55
    w_soft = 0.2
    w_verb = 0.1
    # counts
    hard_total = len(cat_compare["hard"]["matched"]) + len(cat_compare["hard"]["missing"])
    soft_total = len(cat_compare["soft"]["matched"]) + len(cat_compare["soft"]["missing"])
    verb_total = len(cat_compare["verb"]["matched"]) + len(cat_compare["verb"]["missing"])
    # avoid zero division
    hard_score = (len(cat_compare["hard"]["matched"]) / hard_total) if hard_total else 1.0
    soft_score = (len(cat_compare["soft"]["matched"]) / soft_total) if soft_total else 1.0
    verb_score = (len(cat_compare["verb"]["matched"]) / verb_total) if verb_total else 1.0
    # base weighted
    base = (hard_score * w_hard) + (soft_score * w_soft) + (verb_score * w_verb)
    # normalize to 0-100
    score_pct = base / (w_hard + w_soft + w_verb) * 100
    return round(score_pct, 2)

# Optionally, better global similarity using TF-IDF/cosine
def compute_similarity_score(resume_text: str, jd_text: str):
    if not resume_text or not jd_text:
        return 0.0
    if SKLEARN_AVAILABLE:
        try:
            vec = TfidfVectorizer(token_pattern=r"(?u)\b\w+\b", lowercase=True)
            mats = vec.fit_transform([resume_text, jd_text])
            sim = cosine_similarity(mats[0:1], mats[1:2])[0][0]
            return round(float(sim) * 100, 2)
        except Exception:
            pass
    # fallback to token-based cosine
    r_tokens = tokenize(resume_text)
    j_tokens = tokenize(jd_text)
    vocab = sorted(set(r_tokens + j_tokens))
    if not vocab:
        return 0.0
    v_index = {w: i for i, w in enumerate(vocab)}
    def build_vec(tokens):
        v = np.zeros(len(vocab), dtype=float)
        for t in tokens:
            v[v_index[t]] += 1.0
        if np.linalg.norm(v) > 0:
            return v / np.linalg.norm(v)
        return v
    rvec = build_vec(r_tokens)
    jvec = build_vec(j_tokens)
    denom = (np.linalg.norm(rvec) * np.linalg.norm(jvec))
    if denom == 0:
        return 0.0
    sim = float(np.dot(rvec, jvec))
    return round(sim * 100, 2)

# -------------------------
# Suggestions & recruiter tips
# -------------------------
def generate_recruiter_tips(resume_text: str, jd_text: str, cat_compare, sections, contact_info, score_pct):
    tips = []
    # Searchability issues
    if not contact_info["address"]:
        tips.append("Add your location/address — recruiters use it to validate location matches.")
    if not contact_info["email"]:
        tips.append("Add a professional email address for recruiter contact.")
    if not contact_info["phone"]:
        tips.append("Add a phone number to improve contactability.")
    # Summary & sections
    if not sections["summary"]:
        tips.append("Add a 2–3 line Summary at the top describing your role and impact.")
    if not sections["experience"]:
        tips.append("Add at least one Work Experience entry (internship or project counts).")
    # Job title in resume
    jd_title_match = bool(re.search(r'\b(java developer|software engineer|developer|backend engineer)\b', jd_text.lower()))
    if jd_title_match and not re.search(r'\bjava developer\b', resume_text.lower()):
        tips.append("Include the exact job title (e.g. 'Java Developer') in your Summary or Experience for better matches.")
    # Education
    if re.search(r'\bbachelor\b|\bbs\b|\bba\b|\bbsc\b', jd_text.lower()) and not re.search(r'\bbachelor\b|\bbsc\b|\bba\b|\bbs\b|\bengineering\b', resume_text.lower()):
        tips.append("The JD prefers a Bachelor's degree — if you have relevant experience, highlight it in Summary.")
    # Quantifiable achievements
    nums = re.findall(r"\b\d{1,3}%|\b\d{2,5}\b", resume_text)
    if not nums:
        tips.append("Add measurable results (numbers, %, time saved, users served) to at least a few bullets.")
    # Formatting
    ats = simple_ats_checks(resume_text)
    if ats:
        tips.append("Formatting suggestions: " + " | ".join(ats))
    # top missing skills
    top_missing = list(cat_compare["hard"]["missing"].keys())[:5] if cat_compare["hard"]["missing"] else cat_compare["missing_simple"][:5]
    if top_missing:
        tips.append("Top missing skills to add: " + ", ".join(top_missing))
    # final tone
    if score_pct >= 80:
        tips.insert(0, "Excellent match — minor polish recommended.")
    elif score_pct >= 60:
        tips.insert(0, "Good match — consider addressing the top missing skills.")
    elif score_pct >= 40:
        tips.insert(0, "Partial match — prioritize high-impact JD keywords and measurable outcomes.")
    else:
        tips.insert(0, "Low match — rework resume to include role-specific skills and structure.")
    return tips

# -------------------------
# Small helpers for UI & downloads
# -------------------------
def get_download_link(text, filename="extracted_resume.txt"):
    if not text:
        return ""
    b64 = base64.b64encode(text.encode()).decode()
    return f'<a href="data:file/txt;base64,{b64}" download="{filename}">Download extracted text</a>'

def render_chip_html(label, count, color="#f0f0f0", link_id=None):
    style = f"background:{color}; padding:10px 14px; border-radius:10px; font-weight:700; display:inline-block; cursor:pointer; margin-right:12px; text-align:center;"
    if link_id:
        return f'<div onclick="document.getElementById(\'{link_id}\').scrollIntoView({{behavior:\'smooth\'}})" style="{style}">{label}<div style="font-size:14px; font-weight:600; color:#222; margin-top:6px">{count}</div></div>'
    return f'<div style="{style}">{label}<div style="font-size:14px; font-weight:600; color:#222; margin-top:6px">{count}</div></div>'

# -------------------------
# Top CSS (buttons, layout, responsive)
# -------------------------
st.markdown("""
<style>
:root {
  --purple: #6c63ff;
  --purple-dark: #5a54e6;
}
body { font-family: Inter, Arial, sans-serif; }
.header-wrap { display:flex; justify-content:center; align-items:center; padding:12px 0; border-bottom:1px solid #eee; background:#fff; position: sticky; top:0; z-index:9999; }
div.stButton > button { background-color: var(--purple) !important; color: white !important; padding: 10px 18px !important; border-radius:10px !important; border:none !important; font-weight:700 !important; font-size:16px !important; min-width:120px; }
div.stButton > button:hover { filter: brightness(0.98); transform: translateY(-1px); }
.content-wrap { max-width:1150px; margin:20px auto; padding: 12px; }
.center-card { text-align:center; padding:22px; background:#fbfcff; border-radius:12px; border:1px solid #eef2ff; }
.metric-row { display:flex; gap:12px; flex-wrap:wrap; justify-content:center; margin-bottom:16px; }
.section-box { padding:14px; border-radius:10px; border:1px solid #eee; background:#fff; margin-bottom:12px; box-shadow: 0 1px 6px rgba(20,20,20,0.03); }
.kv { font-weight:700; margin-bottom:6px; font-size:15px; }
.small { color:#666; font-size:14px; }
.badge-good { color:#155724; background:#e6f4ea; padding:6px 10px; border-radius:8px; display:inline-block; margin-right:8px; }
.badge-warn { color:#856404; background:#fff3cd; padding:6px 10px; border-radius:8px; display:inline-block; margin-right:8px; }
.badge-bad { color:#721c24; background:#f8d7da; padding:6px 10px; border-radius:8px; display:inline-block; margin-right:8px; }
.score-circle { width:120px; height:120px; border-radius:50%; background:var(--purple); color:white; display:flex; align-items:center; justify-content:center; font-weight:800; font-size:28px; margin:12px auto; box-shadow: 0 6px 18px rgba(108,99,255,0.18); }
@media (max-width: 720px) {
  div.stButton > button { font-size:15px !important; padding:10px !important; }
  .content-wrap { padding:10px; }
  .score-circle { width:100px; height:100px; font-size:24px; }
}
table.skills { width:100%; border-collapse:collapse; margin-top:8px;}
table.skills th, table.skills td { border:1px solid #eee; padding:8px; text-align:left; vertical-align:top; font-size:14px;}
</style>
""", unsafe_allow_html=True)

# -------------------------
# Header / Nav
# -------------------------
cols = st.columns([1, 6, 1])
with cols[0]:
    logo_path = "logo.png"
    if os.path.exists(logo_path):
        st.image(logo_path, width=56)
    else:
        st.write("")
with cols[1]:
    nav_items = [("HOME","home"), ("Scanner","scanner"), ("Results","results"), ("Dashboard","dashboard"),
                 ("Cover Letter","cover_letter"), ("LinkedIn","linkedin"), ("Job Tracker","job_tracker"), ("Account","account")]
    nav_cols = st.columns([1]*len(nav_items))
    for i, (label, key) in enumerate(nav_items):
        with nav_cols[i]:
            if st.button(label, key=f"nav_{key}"):
                st.session_state.page = key
with cols[2]:
    st.write("")

def scroll_to(section_id):
    st.markdown(f"<script>document.getElementById('{section_id}') && document.getElementById('{section_id}').scrollIntoView({{behavior:'smooth', block:'start'}});</script>", unsafe_allow_html=True)

# -------------------------
# Result renderer (used inline so we don't need rerun)
# -------------------------
def render_result_block(r):
    # top metric chips
    st.markdown('<div class="metric-row">', unsafe_allow_html=True)
    st.markdown(f'<div class="score-circle">{r["score"]}%</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div id="section-overview" class="section-box">', unsafe_allow_html=True)
    st.markdown(f"<div style='display:flex; justify-content:space-between; align-items:center'><div><div style='font-size:20px; font-weight:800'>{r['score']}%</div><div class='small'>Overall Match Score</div></div><div class='small'>Scored using keyword coverage & document similarity</div></div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    # Searchability
    st.markdown('<div id="section-search" class="section-box">', unsafe_allow_html=True)
    st.markdown("<div style='font-weight:700; margin-bottom:6px;'>Searchability</div>", unsafe_allow_html=True)
    ci = r["contact_info"]
    if ci["address"]:
        st.markdown("<div class='badge-good'>Address found</div>", unsafe_allow_html=True)
    else:
        st.markdown("<div class='badge-bad'>Address not found — add city or full address</div>", unsafe_allow_html=True)
    if ci["email"]:
        st.markdown("<div class='badge-good'>Email found</div>", unsafe_allow_html=True)
    else:
        st.markdown("<div class='badge-bad'>Email missing</div>", unsafe_allow_html=True)
    if ci["phone"]:
        st.markdown("<div class='badge-good'>Phone number found</div>", unsafe_allow_html=True)
    else:
        st.markdown("<div class='badge-bad'>Phone missing</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    # Hard/Soft Tips
    st.markdown('<div class="section-box">', unsafe_allow_html=True)
    st.markdown("<div style='font-weight:700; margin-bottom:6px;'>Top matched / missing skills</div>", unsafe_allow_html=True)
    hard = r["cat"]["hard"]
    soft = r["cat"]["soft"]
    if hard["matched"]:
        st.markdown("<div class='kv'>Matched technical skills</div>", unsafe_allow_html=True)
        st.write(", ".join([f"{k} ({v})" for k, v in hard["matched"].items()]))
    if hard["missing"]:
        st.markdown("<div style='margin-top:8px; font-weight:600'>Top missing technical skills</div>", unsafe_allow_html=True)
        st.write(", ".join(list(hard["missing"].keys())[:12]))
    if soft["matched"]:
        st.markdown("<div style='margin-top:10px' class='kv'>Matched soft skills</div>", unsafe_allow_html=True)
        st.write(", ".join(list(soft["matched"].keys())))
    if soft["missing"]:
        st.markdown("<div style='margin-top:8px; font-weight:600'>Missing soft skills</div>", unsafe_allow_html=True)
        st.write(", ".join(list(soft["missing"].keys())[:8]))
    st.markdown("</div>", unsafe_allow_html=True)

    # recruiter tips
    st.markdown('<div class="section-box">', unsafe_allow_html=True)
    st.markdown("<div style='font-weight:700; margin-bottom:6px;'>Recruiter Tips</div>", unsafe_allow_html=True)
    for t in r["suggestions"]:
        st.write("• " + t)
    st.markdown("</div>", unsafe_allow_html=True)

    # formatting issues
    st.markdown('<div class="section-box">', unsafe_allow_html=True)
    st.markdown("<div style='font-weight:700; margin-bottom:6px;'>Formatting</div>", unsafe_allow_html=True)
    fm = simple_ats_checks(r["full_resume"])
    if fm:
        for f in fm:
            st.warning(f)
    else:
        st.success("No obvious ATS formatting problems found.")
    st.markdown("</div>", unsafe_allow_html=True)

    # skills table (sample)
    st.markdown('<div class="section-box">', unsafe_allow_html=True)
    st.markdown("<div style='font-weight:700; margin-bottom:6px;'>Skills — Resume vs Job Description (sample)</div>", unsafe_allow_html=True)
    jd_freq = r["cat"]["jd_freq"]
    r_counts = r["cat"]["r_counts"]
    jd_top = sorted(jd_freq.items(), key=lambda x: -x[1])[:20]
    st.markdown("<table class='skills'><tr><th>Skill/Term</th><th>Resume count</th><th>JD count</th></tr>", unsafe_allow_html=True)
    for term, jdcount in jd_top:
        rc = r_counts.get(term, 0)
        st.markdown(f"<tr><td>{term}</td><td>{rc}</td><td>{jdcount}</td></tr>", unsafe_allow_html=True)
    st.markdown("</table>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    # additional insights + excerpt
    st.markdown('<div class="section-box">', unsafe_allow_html=True)
    secs = r["sections"]
    st.markdown("<div style='font-weight:700; margin-bottom:8px;'>Additional Insights</div>", unsafe_allow_html=True)
    st.markdown(f"• Summary section: <b>{'Found' if secs['summary'] else 'Missing'}</b>", unsafe_allow_html=True)
    st.markdown(f"• Work Experience section: <b>{'Found' if secs['experience'] else 'Missing'}</b>", unsafe_allow_html=True)
    st.markdown(f"• Education section: <b>{'Found' if secs['education'] else 'Missing'}</b>", unsafe_allow_html=True)
    quant_found = re.findall(r\"\\b\\d{1,3}%|\\b\\d{2,5}\\b\", r['full_resume'])
    st.markdown(f"• Measurable results found: <b>{len(quant_found)}</b>", unsafe_allow_html=True)
    tone_flag = "Positive" if "achieved" in r["full_resume"].lower() or "improved" in r["full_resume"].lower() else "Neutral"
    st.markdown(f"• Resume tone: <b>{tone_flag}</b>", unsafe_allow_html=True)
    st.markdown(f"• LinkedIn: <b>{'Found' if r['contact_info']['linkedin'] else 'Not found'}</b>", unsafe_allow_html=True)
    st.markdown(f"• Word count: <b>{len(r['full_resume'].split())}</b>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="section-box">', unsafe_allow_html=True)
    st.markdown("<div style='font-weight:700; margin-bottom:6px;'>Resume excerpt</div>", unsafe_allow_html=True)
    st.code(r.get("resume_excerpt", "")[:8000])
    dl = get_download_link(r.get("resume_excerpt",""), filename="extracted_resume.txt")
    if dl:
        st.markdown(dl, unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

# -------------------------
# Pages
# -------------------------
def page_home():
    st.markdown('<div id="section-home"></div>', unsafe_allow_html=True)
    st.markdown('<div class="content-wrap">', unsafe_allow_html=True)
    st.markdown('<div class="center-card">', unsafe_allow_html=True)
    st.markdown("<h1 style='margin-bottom:6px'>Welcome — Resume Analyzer Pro</h1>", unsafe_allow_html=True)
    st.markdown("<p class='small'>Upload or paste your resume and paste the Job Description (JD) you want to apply for. Click <strong>Scanner</strong> in the top nav to start.</p>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

def page_scanner():
    st.markdown('<div id="section-scanner"></div>', unsafe_allow_html=True)
    st.markdown('<div class="content-wrap">', unsafe_allow_html=True)
    st.header("Scanner — Upload Resume & Paste Job Description")
    left, right = st.columns([1,1])
    with left:
        st.markdown("**Upload Resume (PDF/DOCX/TXT)**")
        uploaded = st.file_uploader("", type=["pdf","docx","doc","txt"], key="u_resume")
        st.markdown("---")
        st.markdown("**Or paste resume text (optional)**")
        resume_text_manual = st.text_area("", height=260, key="paste_resume_area", value=st.session_state.get("paste_resume",""))
        st.session_state.paste_resume = resume_text_manual or ""
    with right:
        st.markdown("**Paste Job Description (JD)**")
        jd_text = st.text_area("", height=260, key="paste_jd_area", value=st.session_state.get("paste_jd",""))
        st.session_state.paste_jd = jd_text or ""
        st.markdown("---")
        st.markdown("Options")
        ck_linkedin = st.checkbox("Also show LinkedIn suggestions", value=False, key="opt_linkedin")
    st.markdown("")

    # When user clicks Scan, we'll analyze and render results right here (no rerun).
    if st.button("Scan / Analyze", key="do_scan"):
        # get resume text
        if uploaded:
            rtext = extract_text_from_uploaded(uploaded) or ""
            uploaded_name = uploaded.name
        else:
            rtext = (st.session_state.get("paste_resume","") or "").strip()
            uploaded_name = "pasted_resume.txt"
        jd_val = (st.session_state.get("paste_jd","") or "").strip()
        if not rtext:
            st.warning("Please provide resume text by uploading a file or pasting it.")
        elif not jd_val:
            st.warning("Please paste a job description to compare.")
        else:
            # section detection
            sections = detect_sections(rtext)
            contact_info = detect_contact_info(rtext)

            # categorization & comparisons
            cat = categorize_and_compare(rtext, jd_val)
            weighted_score = compute_weighted_score(cat)
            sim_score = compute_similarity_score(rtext, jd_val)
            # combine both (average)
            final_score = round((weighted_score * 0.7) + (sim_score * 0.3), 2)

            # top-level issue counts (Jobscan-style)
            searchability_issues = 0
            if not contact_info["address"]:
                searchability_issues += 1
            if not contact_info["email"]:
                searchability_issues += 1
            if not contact_info["phone"]:
                searchability_issues += 1
            # count hard/soft issues
            hard_issues = len(cat["hard"]["missing"]) if cat["hard"]["missing"] else len([m for m in cat["missing_simple"] if m in HARD_SKILLS])
            soft_issues = len(cat["soft"]["missing"]) if cat["soft"]["missing"] else len([m for m in cat["missing_simple"] if m in SOFT_SKILLS])
            formatting_issues = len(simple_ats_checks(rtext))

            suggestions = generate_recruiter_tips(rtext, jd_val, cat, sections, contact_info, final_score)

            # build result
            result = {
                "timestamp": datetime.utcnow().isoformat(),
                "score": final_score,
                "sim_score": sim_score,
                "weighted_score": weighted_score,
                "searchability_issues": searchability_issues,
                "hard_issues": hard_issues,
                "soft_issues": soft_issues,
                "recruiter_tips_count": len(suggestions),
                "formatting_issues": formatting_issues,
                "sections": sections,
                "contact_info": contact_info,
                "cat": cat,
                "suggestions": suggestions,
                "resume_excerpt": (rtext[:3000] + "...") if len(rtext) > 3000 else rtext,
                "resume_name": uploaded_name,
                "full_resume": rtext,
                "full_jd": jd_val,
                "linkedin_suggestions": ck_linkedin
            }

            # store in session for later retrieval and show results inline immediately
            st.session_state.current_result = result
            st.session_state.scan_history.insert(0, result)

            st.success("Scan complete — results below.")
            render_result_block(result)

    st.markdown("</div>", unsafe_allow_html=True)

def page_results():
    st.markdown('<div id="section-results"></div>', unsafe_allow_html=True)
    st.markdown('<div class="content-wrap">', unsafe_allow_html=True)
    st.header("Match Results")
    r = st.session_state.get("current_result")
    if not r:
        st.info("No result to display. Run a scan first from the Scanner page.")
    else:
        render_result_block(r)
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
    # show top 10
    for item in history[:10]:
        st.markdown("---")
        st.write(f"**{item.get('resume_name','Resume')}** — {item.get('timestamp','')} — **{item.get('score')}%**")
    st.markdown("</div>", unsafe_allow_html=True)

def page_cover_letter():
    st.markdown('<div id="section-cover_letter"></div>', unsafe_allow_html=True)
    st.markdown('<div class="content-wrap">', unsafe_allow_html=True)
    st.header("Cover Letter Analyzer")
    st.markdown("Upload or paste cover letter and optional JD for tailored suggestions.")
    cover_file = st.file_uploader("", type=["pdf","docx","doc","txt"], key="cover_u")
    cover_text = st.text_area("Paste cover letter text", height=220, key="cover_area", value=st.session_state.get("paste_cover_letter",""))
    st.session_state.paste_cover_letter = cover_text or ""
    cover_jd = st.text_area("Optional: Paste JD for contextual suggestions", height=160, key="cover_jd")
    if st.button("Analyze Cover Letter", key="analyze_cover"):
        if cover_file:
            ctext = extract_text_from_uploaded(cover_file) or ""
        else:
            ctext = (st.session_state.get("paste_cover_letter","") or "").strip()
        if not ctext:
            st.warning("Please provide a cover letter.")
            return
        tips = []
        # opener check
        first_line = next((ln for ln in ctext.splitlines() if ln.strip()), "")
        if not first_line or len(first_line.split()) < 6:
            tips.append("Start with a one-line opener mentioning role & impact.")
        if len(ctext.split()) < 180:
            tips.append("Cover letter looks short — aim for ~200–350 words.")
        if cover_jd and cover_jd.strip():
            matched, missing, _ = extract_top_terms(cover_jd, top_n=60), [], {}
            tips.append("Consider aligning first paragraph with the JD's top keywords.")
        st.success("Cover letter analysis complete.")
        for t in tips:
            st.write("• " + t)
    st.markdown("</div>", unsafe_allow_html=True)

def page_linkedin():
    st.markdown('<div id="section-linkedin"></div>', unsafe_allow_html=True)
    st.markdown('<div class="content-wrap">', unsafe_allow_html=True)
    st.header("LinkedIn Optimizer")
    summary = st.text_area("Paste LinkedIn About summary", height=220, key="linkedin_area", value=st.session_state.get("paste_linkedin",""))
    st.session_state.paste_linkedin = summary or ""
    opt_jd = st.text_area("Optional JD (for context)", height=160, key="linkedin_jd_area")
    if st.button("Optimize LinkedIn", key="do_linkedin"):
        if not summary.strip():
            st.warning("Please paste your LinkedIn About text.")
            return
        suggestions = []
        suggestions.append("Start with role + one-line measurable impact.")
        if opt_jd and opt_jd.strip():
            matched, missing, _ = extract_top_terms(opt_jd, top_n=40), [], {}
            suggestions.append("Place top 4 job keywords within first two sentences of About.")
        st.success("LinkedIn suggestions ready.")
        for s in suggestions:
            st.write("• " + s)
    st.markdown("</div>", unsafe_allow_html=True)

def page_tracker():
    st.markdown('<div id="section-job_tracker"></div>', unsafe_allow_html=True)
    st.markdown('<div class="content-wrap">', unsafe_allow_html=True)
    st.header("Job Tracker")
    title = st.text_input("Job title", key="t_title")
    comp = st.text_input("Company", key="t_company")
    date = st.date_input("Application date", key="t_date")
    status = st.selectbox("Status", ["Applied","Interviewing","Offer","Rejected"], key="t_status")
    if st.button("Add to Tracker", key="add_to_tracker"):
        st.session_state.scan_history.insert(0, {"resume_name": title or "Untitled", "timestamp": date.isoformat(), "score": "Tracked", "note": comp, "status": status})
        st.success("Added to tracker.")
    st.markdown("</div>", unsafe_allow_html=True)

def page_account():
    st.markdown('<div id="section-account"></div>', unsafe_allow_html=True)
    st.markdown('<div class="content-wrap">', unsafe_allow_html=True)
    st.header("Account")
    if st.session_state.get("user"):
        st.success(f"Signed in as **{st.session_state.user.get('name')}** ({st.session_state.user.get('email')})")
        if st.button("Logout", key="logout_btn"):
            st.session_state.user = None
            st.session_state.page = "home"
            st.success("Logged out.")
        st.markdown("</div>", unsafe_allow_html=True)
        return

    # Accept-any-credentials behaviour:
    st.subheader("Sign Up (optional)")
    su_name = st.text_input("Full name", key="su_name")
    su_email = st.text_input("Email", key="su_email")
    su_pwd = st.text_input("Password (any)", type="password", key="su_pwd")
    if st.button("Register", key="register_btn"):
        # accept any credential — create session user and proceed (no DB)
        st.session_state.user = {"name": su_name or "User", "email": su_email or ""}
        st.success("Registered. You are signed in.")
        # show account area (no rerun required)

    st.markdown("---")
    st.subheader("Login (press to continue)")
    li_email = st.text_input("Email", key="li_email", value="")
    li_pwd = st.text_input("Password (any)", type="password", key="li_pwd", value="")
    if st.button("Login", key="login_btn"):
        # accept any credentials and sign in
        st.session_state.user = {"name": li_email.split("@")[0] if li_email else "User", "email": li_email}
        st.success("Signed in.")
        # proceed to account view

    st.markdown("</div>", unsafe_allow_html=True)

# -------------------------
# Router
# -------------------------
page = st.session_state.get("page", "home")
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
