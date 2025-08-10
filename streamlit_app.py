# streamlit_app.py
"""
Resume Analyzer Pro — single-file (session-only).
Features:
- Resume/JD cosine similarity + TF keyword ranking
- Jobscan-like UI: circular score, chips, ATS checks, suggestions
- Cover Letter & LinkedIn analyzers with consistent UI
- Interactive "Suggested Sentence" generator for missing keywords (add to resume)
- Downloadable report (PDF via reportlab if available, otherwise TXT)
- No database — session-only
"""

import streamlit as st
from datetime import datetime
from io import BytesIO
import re
import os
import base64
from collections import Counter
import numpy as np
import math
import textwrap

# optional libs
try:
    import PyPDF2
except Exception:
    PyPDF2 = None

try:
    import docx
except Exception:
    docx = None

# try reportlab for PDF generation
try:
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    REPORTLAB = True
except Exception:
    REPORTLAB = False

# Page config
st.set_page_config(page_title="Resume Analyzer Pro", page_icon="🚀", layout="wide")

# -------------------- Utilities --------------------
TOKEN_RE = re.compile(r"\b[a-z0-9\+\#\-\.]+\b", re.I)

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

def tokenize(s: str):
    if not s:
        return []
    s = s.lower()
    return TOKEN_RE.findall(s)

def top_keywords(text: str, top_n=40, min_len=3, stopwords=None):
    tokens = tokenize(text)
    if stopwords is None:
        stopwords = set([
            "the","and","with","from","that","this","will","for","are","you","your",
            "have","not","but","our","their","they","be","we","role","skills","responsibilities",
            "required","using","experience","years","year","work","ability"
        ])
    filtered = [t for t in tokens if len(t) > min_len and t not in stopwords and not t.isdigit()]
    counts = Counter(filtered)
    return counts.most_common(top_n)

def build_term_vector(tokens, vocab_index):
    vec = np.zeros(len(vocab_index), dtype=float)
    for t in tokens:
        if t in vocab_index:
            vec[vocab_index[t]] += 1.0
    if np.linalg.norm(vec) > 0:
        return vec / np.linalg.norm(vec)
    return vec

def compute_cosine_similarity(resume_text: str, jd_text: str):
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
    return float(sim)

def get_matched_and_missing(resume_text: str, jd_text: str, top_n=200):
    jd_top = top_keywords(jd_text, top_n)
    jd_terms = [w for w, c in jd_top]
    r_tokens = set(tokenize(resume_text))
    matched = [w for w in jd_terms if w in r_tokens]
    missing = [w for w in jd_terms if w not in r_tokens]
    jd_freq = {w: c for w, c in jd_top}
    missing_sorted = sorted(missing, key=lambda w: jd_freq.get(w, 0), reverse=True)
    return matched, missing_sorted, jd_freq

def simple_ats_checks(resume_text: str):
    checks = []
    if not resume_text:
        return checks
    if "\t" in resume_text or re.search(r" {4,}", resume_text):
        checks.append("Possible columns or table-like formatting — convert to a simple vertical layout.")
    if "<img" in resume_text.lower() or "image:" in resume_text.lower():
        checks.append("Images detected in the resume — remove images or convert content to plain text for ATS.")
    if len(resume_text.splitlines()) < 6 or len(resume_text.split()) < 130:
        checks.append("Resume looks short — aim for 1–2 pages with clear bullets for each role.")
    if re.search(r"[■♦▸►]", resume_text):
        checks.append("Unusual bullet characters detected — use simple hyphens or standard bullets for safer parsing.")
    return checks

def detect_quantifications(text: str):
    nums = re.findall(r"\b\d{1,3}%|\b\d{2,4}\b", text)
    return len(nums) > 0, nums[:10]

def generate_actionable_suggestions(score_pct, matched, missing, resume_text, jd_freq):
    suggestions = []
    if score_pct >= 85:
        suggestions.append("Excellent alignment. Double-check formatting and tailor small role-specific phrases.")
    elif score_pct >= 65:
        suggestions.append("Good match — add a few high-priority JD keywords and more quantifiable achievements.")
    elif score_pct >= 40:
        suggestions.append("Fair match — prioritize top missing keywords below and quantify your achievements.")
    else:
        suggestions.append("Low match — rework your resume to include role-specific skills, responsibilities and keywords from the JD.")

    if missing:
        top_missing = missing[:8]
        suggestions.append("Top missing keywords to add (prioritized): " + ", ".join(top_missing))

    has_q, nums = detect_quantifications(resume_text)
    if not has_q:
        suggestions.append("Add quantifiable outcomes (numbers or %) — e.g., 'Reduced bugs by 30%' or 'Handled 20+ tickets/week'.")
    else:
        suggestions.append("Quantified items detected: " + ", ".join(nums))

    ats = simple_ats_checks(resume_text)
    if ats:
        suggestions.append("ATS & formatting fixes: " + " | ".join(ats))

    if matched:
        suggestions.append("For LinkedIn: put top 4 matched keywords in your headline & first two lines of the About section.")
    return suggestions

def get_download_link_bytes(b: bytes, filename="report.pdf"):
    b64 = base64.b64encode(b).decode()
    href = f'<a href="data:application/octet-stream;base64,{b64}" download="{filename}">Download {filename}</a>'
    return href

def get_download_link_text(text, filename="report.txt"):
    b64 = base64.b64encode(text.encode()).decode()
    href = f'<a href="data:file/txt;base64,{b64}" download="{filename}">Download {filename}</a>'
    return href

# -------------------- Suggested sentence generator --------------------
VERBS = [
    "Implemented", "Designed", "Developed", "Led", "Optimized", "Built", "Integrated",
    "Automated", "Architected", "Improved", "Migrated", "Tested", "Configured"
]

def generate_sentence_for_keyword(keyword, jd_excerpt="", resume_excerpt=""):
    # Use jd context to choose verb if keywords like 'test', 'deploy', 'design' appear
    kw = keyword.replace("-", " ").lower()
    verb = "Implemented"
    if any(x in kw for x in ["test", "testing", "qa", "automation"]):
        verb = "Developed automated tests for"
    elif any(x in kw for x in ["design", "ui", "ux", "figma"]):
        verb = "Designed"
    elif any(x in kw for x in ["migrate","migration","deploy","deployment"]):
        verb = "Led migration for"
    elif any(x in kw for x in ["optimize","performance","latency","scalability"]):
        verb = "Optimized"
    elif any(x in kw for x in ["integrat","api","rest","graphql"]):
        verb = "Integrated"
    else:
        # choose a random-ish verb from list based on hash for determinism
        verb = VERBS[hash(keyword) % len(VERBS)]
    # short templates — encourage quantification placeholder
    templates = [
        f"{verb} {keyword} to { 'improve ' + ('performance by X%' if 'perform' in kw else 'deliver Y% faster results') } (add metric).",
        f"{verb} {keyword} in a cross-functional team; achieved measurable improvements in delivery (add metric).",
        f"{verb} {keyword} for production services, improving reliability and maintainability (add metric)."
    ]
    # pick first template that's not too long
    return templates[0]

# -------------------- PDF report generation (reportlab fallback) --------------------
def create_pdf_report_bytes(title, report_lines):
    """
    Try to create a simple PDF using reportlab and return bytes.
    If reportlab not available, raise RuntimeError.
    """
    if not REPORTLAB:
        raise RuntimeError("reportlab not available")
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    styles = getSampleStyleSheet()
    normal = styles['Normal']
    normal.spaceAfter = 6
    heading = ParagraphStyle('Heading', parent=styles['Heading1'], fontSize=14, leading=16, spaceAfter=8)
    story = []
    story.append(Paragraph(title, heading))
    story.append(Spacer(1, 6))
    for line in report_lines:
        # wrap lines
        para = Paragraph(line.replace("\n", "<br/>"), normal)
        story.append(para)
    doc.build(story)
    pdf_bytes = buf.getvalue()
    buf.close()
    return pdf_bytes

# -------------------- Session init --------------------
if "page" not in st.session_state:
    st.session_state.page = "home"
if "current_result" not in st.session_state:
    st.session_state.current_result = None
if "scan_history" not in st.session_state:
    st.session_state.scan_history = []
if "paste_resume" not in st.session_state:
    st.session_state.paste_resume = ""

# -------------------- Top CSS & header --------------------
st.markdown("""
<style>
.header-wrap { display:flex; justify-content:center; align-items:center; padding:14px 0; border-bottom:1px solid #eee; background:#fff; position:sticky; top:0; z-index:9999; }
.nav-container { display:flex; gap:14px; align-items:center; justify-content:center; max-width:1200px; width:100%; padding:0 12px; }
.nav-item { background:#f7f7fb; padding:8px 14px; border-radius:10px; font-weight:600; color:#333; text-decoration:none; border:1px solid #f0eff5; }
.nav-item:hover { background:#efe8ff; color:#4b0082; }
.content-wrap { max-width:1100px; margin:24px auto; padding: 0 18px; }
.tag { display:inline-block; padding:6px 10px; margin:4px; border-radius:12px; font-size:13px; }
.tag-match { background:#e8f6ea; color:#1b5e20; }
.tag-miss { background:#fff0f0; color:#7a1a1a; }
.card { background:#fff; padding:16px; border-radius:12px; box-shadow: 0 1px 6px rgba(20,20,40,0.04); border:1px solid #f0eef5; }
.small { font-size:13px; color:#666; }
.suggestion { background:#f6f8ff; padding:10px; border-radius:8px; margin-bottom:8px; }
.keyword-row { display:flex; align-items:center; gap:8px; margin-bottom:6px; flex-wrap:wrap; }
.btn-small { padding:6px 10px; border-radius:8px; border:none; background:#6b46c1; color:white; font-weight:600; cursor:pointer; }
</style>
""", unsafe_allow_html=True)

# header
cols = st.columns([1,6,1])
with cols[0]:
    logo_path = "logo.png"
    if os.path.exists(logo_path):
        st.image(logo_path, width=56)
    else:
        st.write("")
with cols[1]:
    st.markdown('<div class="nav-container">', unsafe_allow_html=True)
    nav_items = [
        ("HOME","home"),
        ("Scanner","scanner"),
        ("Results","results"),
        ("Cover Letter","cover_letter"),
        ("LinkedIn","linkedin"),
        ("Job Tracker","job_tracker"),
        ("Account","account")
    ]
    for label,key in nav_items:
        st.markdown(f'<a class="nav-item" href="#section-{key}" onclick="window.location.hash=\'section-{key}\'">{label}</a>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
with cols[2]:
    st.write("")

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

# -------------------- Pages --------------------
def page_home():
    st.markdown('<div id="section-home"></div>', unsafe_allow_html=True)
    st.markdown('<div class="content-wrap center-text">', unsafe_allow_html=True)
    st.markdown("<h1 style='margin-bottom:6px'>Resume Analyzer Pro</h1>", unsafe_allow_html=True)
    st.markdown("<p style='max-width:900px; margin:0 auto;'>Upload or paste your resume, paste the job description, and get a professional match report with specific, actionable edits for resume, cover letter and LinkedIn.</p>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

def page_scanner():
    st.markdown('<div id="section-scanner"></div>', unsafe_allow_html=True)
    st.markdown('<div class="content-wrap">', unsafe_allow_html=True)
    st.header("Resume Scanner — Upload or Paste")
    left, right = st.columns([1,1])
    with left:
        st.markdown("**Upload Resume (PDF / DOCX / TXT)**")
        uploaded = st.file_uploader("", type=["pdf","docx","doc","txt"], key="upload_resume")
        st.markdown("---")
        st.markdown("**Or paste resume text (optional)**")
        paste_area = st.text_area("", height=280, key="paste_resume_area", value=st.session_state.get("paste_resume",""))
        # keep session copy updated
        st.session_state.paste_resume = paste_area
        if uploaded:
            st.info(f"Uploaded: {uploaded.name}")
    with right:
        st.markdown("**Paste Job Description (JD)**")
        jd_text = st.text_area("", height=400, key="paste_jd")
        ck_linkedin = st.checkbox("Also optimize for LinkedIn summary (produce suggestions)", value=False, key="ck_linkedin")
        st.markdown("**Options:**")
        st.write("• Match algorithm: cosine similarity (TF normalized).")
    st.markdown("")
    if st.button("Scan / Analyze", key="scan_analyze"):
        uploaded_obj = uploaded
        if uploaded_obj:
            rtext = extract_text_from_uploaded(uploaded_obj) or ""
        else:
            rtext = (st.session_state.get("paste_resume","") or "").strip()
        jd_val = (st.session_state.get("paste_jd","") or "").strip()
        if not rtext:
            st.warning("Please provide resume text by uploading a file or pasting it.")
            return
        if not jd_val:
            st.warning("Please paste a job description to compare.")
            return

        sim = compute_cosine_similarity(rtext, jd_val)
        score = round(sim * 100, 2)
        matched, missing, jd_freq = get_matched_and_missing(rtext, jd_val, top_n=400)
        warnings = simple_ats_checks(rtext)
        suggestions = generate_actionable_suggestions(score, matched, missing, rtext, jd_freq)
        linkedin_suggestions = None
        if ck_linkedin:
            linkedin_suggestions = []
            if matched:
                linkedin_suggestions.append("Add keywords near the top: " + ", ".join(matched[:4]))
            linkedin_suggestions.append("Start LinkedIn headline with role + one-line impact.")
            linkedin_suggestions.append("Include 2 quantifiable achievements in About for credibility.")

        uploaded_name = uploaded_obj.name if uploaded_obj else "pasted_resume.txt"
        result = {
            "timestamp": datetime.utcnow().isoformat(),
            "score": score,
            "matched": matched,
            "missing": missing,
            "warnings": warnings,
            "suggestions": suggestions,
            "linkedin_suggestions": linkedin_suggestions,
            "resume_text_excerpt": (rtext[:3000] + "...") if len(rtext) > 3000 else rtext,
            "jd_excerpt": (jd_val[:2000] + "...") if len(jd_val) > 2000 else jd_val,
            "resume_name": uploaded_name,
            "jd_freq": jd_freq,
            "full_resume": rtext,
            "full_jd": jd_val
        }
        st.session_state.current_result = result
        st.session_state.scan_history.insert(0, result)
        st.session_state.page = "results"
        return
    st.markdown("</div>", unsafe_allow_html=True)

def circular_score_html(score):
    sc = max(0, min(100, float(score)))
    html = f"""
    <div style="display:flex; justify-content:center; align-items:center;">
      <div style="width:150px; height:150px; border-radius:50%; display:flex; align-items:center; justify-content:center;
                  background: conic-gradient(#6b46c1 {sc}%, #eee {sc}%);">
        <div style="width:120px; height:120px; border-radius:50%; background:#fff; display:flex; flex-direction:column; align-items:center; justify-content:center;">
          <div style="font-size:28px; font-weight:700; color:#4b0082;">{sc:.0f}%</div>
          <div style="font-size:12px; color:#666; margin-top:4px;">Match Score</div>
        </div>
      </div>
    </div>
    """
    return html

def render_keyword_chips(words, kind="match", limit=200):
    if not words:
        return "<div class='small'>None</div>"
    chips = []
    css_class = "tag-match" if kind == "match" else "tag-miss"
    for w in words[:limit]:
        chips.append(f"<span class='tag {css_class}'>{w}</span>")
    return " ".join(chips)

def page_results():
    st.markdown('<div id="section-results"></div>', unsafe_allow_html=True)
    st.markdown('<div class="content-wrap">', unsafe_allow_html=True)
    r = st.session_state.get("current_result")
    st.header("Match Results — Professional Report")
    if not r:
        st.info("No result to display. Run a scan first from the Scanner page.")
        st.markdown("</div>", unsafe_allow_html=True)
        return

    col1, col2 = st.columns([1,2])
    with col1:
        st.markdown(circular_score_html(r["score"]), unsafe_allow_html=True)
        st.markdown("<div class='small center-text' style='margin-top:8px;'>Tip: prioritize top missing keywords shown to the right.</div>", unsafe_allow_html=True)
    with col2:
        score_val = r["score"]
        if score_val >= 85:
            headline = "Excellent match — you're highly aligned with this JD."
        elif score_val >= 65:
            headline = "Strong match — a few keyword & metrics updates can improve it more."
        elif score_val >= 40:
            headline = "Partial match — add role-specific skills & measurable outcomes."
        else:
            headline = "Low match — rework your resume to closely mirror job requirements."
        st.markdown(f"<div class='card'><div style='font-weight:700; font-size:18px'>{headline}</div>"
                    f"<div class='small' style='margin-top:8px'>Score: <strong>{score_val}%</strong> • Resume: <strong>{r.get('resume_name')}</strong></div>"
                    "</div>", unsafe_allow_html=True)
        st.markdown("<div style='margin-top:10px'>", unsafe_allow_html=True)
        for s in r.get("suggestions", [])[:4]:
            st.markdown(f"<div class='suggestion'>{s}</div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<br/>")
    matched = r.get("matched", [])
    missing = r.get("missing", [])
    coverage = (len(matched) / (len(matched) + len(missing))) if (matched or missing) else 0
    pct = int(coverage * 100)
    st.markdown(f"""
    <div class='card' style='padding:12px;'>
      <div style='display:flex; justify-content:space-between; align-items:center;'>
        <div style='font-weight:700;'>Keyword Coverage</div>
        <div style='font-size:13px; color:#666;'>{pct}% of JD keywords present</div>
      </div>
      <div style='margin-top:10px; background:#f1eef9; height:12px; border-radius:8px; overflow:hidden;'>
        <div style='width:{pct}%; height:100%; background:linear-gradient(90deg,#6b46c1,#9f7aea);'></div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    col_m, col_mm = st.columns([1,1])
    with col_m:
        st.markdown("<div class='card'><div style='font-weight:700; margin-bottom:8px;'>✅ Matched Keywords</div>", unsafe_allow_html=True)
        st.markdown(render_keyword_chips(matched, kind="match", limit=500), unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)
    with col_mm:
        st.markdown("<div class='card'><div style='font-weight:700; margin-bottom:8px;'>❌ Missing Keywords (prioritized)</div>", unsafe_allow_html=True)
        # Display missing keywords with "Generate suggested sentence" button for top N
        top_missing = missing[:30]
        # show chips and interactive generator for top 8
        st.markdown(render_keyword_chips(missing, kind="miss", limit=200), unsafe_allow_html=True)
        st.markdown("<hr/>", unsafe_allow_html=True)
        st.markdown("<div style='font-weight:700; margin-bottom:6px;'>Generate suggested sentences for top missing keywords</div>", unsafe_allow_html=True)
        for i, kw in enumerate(top_missing[:12]):
            k_id = f"gen_{i}"
            row = st.container()
            with row:
                cols = st.columns([3,1,1])
                cols[0].markdown(f"<div class='small'><strong>{kw}</strong></div>", unsafe_allow_html=True)
                if cols[1].button("Generate", key=f"gen_btn_{i}"):
                    # create suggested sentence and store in session for display
                    s = generate_sentence_for_keyword(kw, jd_excerpt=r.get("jd_excerpt",""), resume_excerpt=r.get("resume_text_excerpt",""))
                    st.session_state[f"sugg_{i}"] = s
                sugg = st.session_state.get(f"sugg_{i}", "")
                cols[2].markdown("", unsafe_allow_html=True)
                if sugg:
                    # show editable textbox + add-to-resume button
                    tkey = f"edit_sugg_{i}"
                    val = cols[0].text_area("", value=sugg, key=tkey, height=72)
                    if cols[2].button("Add to Resume", key=f"add_to_resume_{i}"):
                        # append to session paste resume text (with spacing)
                        cur = st.session_state.get("paste_resume","")
                        if cur and not cur.endswith("\n"):
                            cur = cur + "\n\n"
                        cur = cur + val.strip()
                        st.session_state.paste_resume = cur
                        # also update the visible paste box if present
                        try:
                            st.experimental_rerun()
                        except Exception:
                            st.success("Added to resume (reload to see in paste area).")
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<br/>")
    col_a, col_b = st.columns([1,1])
    with col_a:
        st.markdown("<div class='card'><div style='font-weight:700; margin-bottom:8px;'>⚠️ ATS & Formatting Checks</div>", unsafe_allow_html=True)
        if r.get("warnings"):
            for w in r["warnings"]:
                st.warning(w)
        else:
            st.success("No major ATS formatting issues detected.")
        st.markdown("<div class='small' style='margin-top:8px'>Common fixes: use standard headings (Experience, Education), avoid images & tables, use simple bullets and plain fonts.</div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)
    with col_b:
        st.markdown("<div class='card'><div style='font-weight:700; margin-bottom:8px;'>🔗 LinkedIn Optimization</div>", unsafe_allow_html=True)
        ls = r.get("linkedin_suggestions")
        if ls:
            for li in ls:
                st.markdown(f"- {li}")
        else:
            st.markdown("- Start headline with `Role — impact`.")
            st.markdown("- Put top 4 JD keywords in the first two lines of About.")
            st.markdown("- Include 2 quantifiable achievements.")
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<br/>")
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.markdown("**Resume excerpt (click to expand)**")
    with st.expander("View resume excerpt"):
        st.code(r.get("resume_text_excerpt","")[:8000])
        st.markdown(get_download_link_text(r.get("resume_text_excerpt",""), filename="extracted_resume.txt"), unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<br/>")
    c1, c2, c3 = st.columns([1,1,1])
    with c1:
        if st.button("Scan another resume"):
            st.session_state.page = "scanner"
            return
    with c2:
        if st.button("Download Report (PDF/TXT)"):
            # build report lines
            title = f"Resume Analyzer Report — {datetime.utcnow().date().isoformat()}"
            lines = []
            lines.append(f"<b>{title}</b>")
            lines.append(f"Score: {r['score']}%")
            lines.append(f"Resume: {r.get('resume_name')}")
            lines.append("")
            lines.append("Matched keywords (top): " + (", ".join(r.get("matched",[])[:50]) or "None"))
            lines.append("Missing keywords (top): " + (", ".join(r.get("missing",[])[:50]) or "None"))
            lines.append("")
            lines.append("Suggestions:")
            for s in r.get("suggestions", []):
                lines.append("- " + s)
            lines.append("")
            lines.append("ATS warnings:")
            for w in r.get("warnings", []):
                lines.append("- " + w)
            lines.append("")
            lines.append("Resume excerpt:")
            lines.append(r.get("resume_text_excerpt",""))
            # Try PDF first
            try:
                pdf_bytes = create_pdf_report_bytes(title, lines)
                st.markdown(get_download_link_bytes(pdf_bytes, filename="resume_report.pdf"), unsafe_allow_html=True)
            except Exception:
                # fallback to text
                text_report = "\n".join([re.sub(r'<[^>]*>', '', str(l)) for l in lines])
                st.markdown(get_download_link_text(text_report, filename="resume_report.txt"), unsafe_allow_html=True)

    with c3:
        if st.button("View Scan History"):
            st.session_state.page = "dashboard"
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
    for idx, item in enumerate(history[:20], start=1):
        st.markdown("<div class='card' style='margin-bottom:10px;'>", unsafe_allow_html=True)
        st.write(f"**{idx}. {item.get('resume_name','Resume')}** — {item.get('timestamp','')}")
        st.write(f"Score: **{item.get('score')}%**")
        st.write("Matched: " + (", ".join(item.get("matched", [])[:20]) or "None"))
        st.write("Missing: " + (", ".join(item.get("missing", [])[:20]) or "None"))
        st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

def page_cover_letter():
    st.markdown('<div id="section-cover_letter"></div>', unsafe_allow_html=True)
    st.markdown('<div class="content-wrap">', unsafe_allow_html=True)
    st.header("Cover Letter Analyzer — Tailor for the JD")
    left, right = st.columns([1,1])
    with left:
        st.markdown("**Upload Cover Letter (PDF/DOCX/TXT)**")
        cover_file = st.file_uploader("", type=["pdf","docx","doc","txt"], key="cover_upload")
        st.markdown("---")
        st.markdown("**Or paste cover letter text**")
        cover_text = st.text_area("", height=260, key="cover_text")
    with right:
        st.markdown("**Paste Job Description (for context)**")
        cover_jd = st.text_area("", height=360, key="cover_jd")
        st.markdown("**Checks performed:** Keyword coverage, length, opening line & CTA.")
    if st.button("Analyze Cover Letter", key="analyze_cover"):
        if cover_file:
            ctext = extract_text_from_uploaded(cover_file) or ""
        else:
            ctext = (st.session_state.get("cover_text","") or "").strip()
        if not ctext:
            st.warning("Please upload or paste a cover letter.")
            return
        jd_val = (st.session_state.get("cover_jd","") or "").strip()
        suggestions = []
        if len(ctext.split()) < 160:
            suggestions.append("Cover letter is short — target ~200-350 words for strong context.")
        first_line = ctext.splitlines()[0] if ctext.splitlines() else ""
        if len(first_line.split()) < 6:
            suggestions.append("Start with a strong one-line opener that mentions the role and impact.")
        if jd_val:
            matched, missing, jd_freq = get_matched_and_missing(ctext, jd_val, top_n=200)
            suggestions.append(f"Keywords from JD present: {', '.join(matched[:8]) or 'None'}")
            if missing:
                suggestions.append("Consider mentioning: " + ", ".join(missing[:8]))
        has_q, nums = detect_quantifications(ctext)
        if not has_q:
            suggestions.append("Add 1–2 quantified achievements (numbers or %).")
        else:
            suggestions.append("Quantified items detected: " + ", ".join(nums[:5]))
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.markdown("**Cover Letter Suggestions**")
        for s in suggestions:
            st.markdown(f"- {s}")
        st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

def page_linkedin():
    st.markdown('<div id="section-linkedin"></div>', unsafe_allow_html=True)
    st.markdown('<div class="content-wrap">', unsafe_allow_html=True)
    st.header("LinkedIn Optimizer — About & Headline")
    summary = st.text_area("Paste LinkedIn 'About' summary", height=260, key="linkedin_summary")
    jd = st.text_area("Paste Job Description (optional)", height=200, key="linkedin_jd")
    if st.button("Optimize LinkedIn", key="opt_linkedin"):
        if not summary.strip():
            st.warning("Please paste your LinkedIn About text.")
            return
        suggestions = []
        suggestions.append("Start with `YourRole — What you do + One-line impact`.")
        if jd.strip():
            matched, missing, jd_freq = get_matched_and_missing(summary, jd, top_n=200)
            if matched:
                suggestions.append("Keywords found from JD: " + ", ".join(matched[:6]))
            if missing:
                suggestions.append("Consider adding: " + ", ".join(missing[:6]))
        has_q, nums = detect_quantifications(summary)
        if not has_q:
            suggestions.append("Add 1–2 quantified achievements in the first 3 lines.")
        else:
            suggestions.append("Quantified achievements detected: " + ", ".join(nums[:6]))
        suggestions.append("Add a one-line CTA like 'Open to new roles — contact: email@example.com' (if comfortable).")
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        for s in suggestions:
            st.markdown(f"- {s}")
        st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

def page_tracker():
    st.markdown('<div id="section-job_tracker"></div>', unsafe_allow_html=True)
    st.markdown('<div class="content-wrap">', unsafe_allow_html=True)
    st.header("Job Tracker (session-only)")
    title = st.text_input("Job title", key="tracker_title")
    company = st.text_input("Company", key="tracker_company")
    date = st.date_input("Application date", key="tracker_date")
    status = st.selectbox("Status", ["Applied", "Interviewing", "Offer", "Rejected"], key="tracker_status")
    if st.button("Add to Tracker", key="add_tracker"):
        entry = {"title": title, "company": company, "date": date.isoformat(), "status": status}
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
    st.header("Account — session-based (no DB)")
    st.info("Registration & login are simulated and stored in session only.")
    if "user" in st.session_state and st.session_state.get("user"):
        st.success(f"Signed in as **{st.session_state.user.get('name')}** ({st.session_state.user.get('email')})")
        if st.button("Logout"):
            st.session_state.user = None
            st.session_state.page = "home"
            return
        st.markdown("</div>", unsafe_allow_html=True)
        return
    st.subheader("Sign Up (session-only)")
    su_name = st.text_input("Full name", key="su_name")
    su_email = st.text_input("Email", key="su_email")
    su_pwd = st.text_input("Password", type="password", key="su_pwd")
    if st.button("Register"):
        st.session_state.last_registration = {"name": su_name, "email": su_email}
        st.success("Registration saved to session. Please Login below.")
    st.markdown("---")
    st.subheader("Login")
    li_email = st.text_input("Email", key="li_email")
    li_pwd = st.text_input("Password", type="password", key="li_pwd")
    if st.button("Login"):
        user = {"id": 1, "name": st.session_state.get("last_registration", {}).get("name","Guest"), "email": li_email}
        st.session_state.user = user
        st.success("Signed in (session-only).")
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

smooth_scroll_to_current()
