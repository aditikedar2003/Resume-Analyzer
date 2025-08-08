# utils/nlp.py
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import re

def clean_text(s: str):
    if not s:
        return ""
    s = s.lower()
    s = re.sub(r'\s+', ' ', s).strip()
    return s

def compute_match_score(resume_text: str, jd_text: str):
    resume_text = clean_text(resume_text)
    jd_text = clean_text(jd_text)
    if not resume_text or not jd_text:
        return 0.0
    vectorizer = TfidfVectorizer(stop_words='english')
    try:
        tfidf = vectorizer.fit_transform([resume_text, jd_text])
        sim = cosine_similarity(tfidf[0:1], tfidf[1:2])[0][0]
        return round(float(sim) * 100, 2)
    except Exception:
        return 0.0

def get_keywords(resume_text: str, jd_text: str, top_n=50):
    # simple whitespace tokenization approach for matched/missing keywords
    r_words = set(re.findall(r'\b[a-z0-9\+\#\-\.]+\b', resume_text.lower()))
    jd_words = set(re.findall(r'\b[a-z0-9\+\#\-\.]+\b', jd_text.lower()))
    matched = sorted(list(jd_words & r_words))
    missing = sorted(list(jd_words - r_words))
    return matched[:top_n], missing[:top_n]

def simple_ats_checks(resume_text: str):
    """
    Basic heuristics: flags presence of tables (by lots of tabs / multiple consecutive spaces),
    images (not parsable in text extraction — we detect tags), and columns (many double-spaces)
    """
    checks = []
    if not resume_text:
        return checks
    if "\t" in resume_text or "  " in resume_text:
        checks.append("Possible columns or table-like formatting (avoid for ATS).")
    if "<img" in resume_text or "image:" in resume_text.lower():
        checks.append("Images detected or image tags present (remove images for ATS).")
    if len(resume_text.splitlines()) < 5:
        checks.append("Short resume text detected (check content).")
    return checks
