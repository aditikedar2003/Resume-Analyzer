# utils/nlp.py
import re
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

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
    vectorizer = TfidfVectorizer(stop_words='english', max_features=5000)
    try:
        tfidf = vectorizer.fit_transform([resume_text, jd_text])
        sim = cosine_similarity(tfidf[0:1], tfidf[1:2])[0][0]
        return round(float(sim) * 100, 2)
    except Exception:
        return 0.0

def get_keywords(resume_text: str, jd_text: str, top_n=50):
    r_words = set(re.findall(r'\b[a-z0-9\+\#\-\.]+\b', (resume_text or "").lower()))
    jd_words = set(re.findall(r'\b[a-z0-9\+\#\-\.]+\b', (jd_text or "").lower()))
    matched = sorted(list(jd_words & r_words))
    missing = sorted(list(jd_words - r_words))
    return matched[:top_n], missing[:top_n]

def simple_ats_checks(resume_text: str):
    checks = []
    if not resume_text:
        return checks
    if "\t" in resume_text or resume_text.count("  ") > 5:
        checks.append("Possible columns or table-like formatting (avoid for ATS).")
    if "<img" in resume_text.lower() or "image:" in resume_text.lower():
        checks.append("Images detected or image tags present (remove images for ATS).")
    if len(resume_text.splitlines()) < 5:
        checks.append("Short resume text detected (check content).")
    return checks
