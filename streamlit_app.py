import streamlit as st
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import re
import numpy as np

# --- Define Hard and Soft Skills Lists (can be extended or fetched dynamically) ---
HARD_SKILLS = [
    "java", "python", "sql", "mysql", "postgresql", "hibernate", "rest api", "docker",
    "kubernetes", "aws", "azure", "git", "linux", "c++", "react", "angular", "node.js"
]

SOFT_SKILLS = [
    "communication", "leadership", "teamwork", "problem solving", "adaptability",
    "time management", "collaboration", "critical thinking", "creativity"
]

# --- Utility functions ---
def clean_text(text):
    text = text.lower()
    text = re.sub(r'[^a-z0-9\s]', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def extract_skills(text, skill_list):
    skills_found = []
    for skill in skill_list:
        pattern = r'\b' + re.escape(skill.lower()) + r'\b'
        if re.search(pattern, text):
            skills_found.append(skill)
    return skills_found

def compute_cosine_similarity(text1, text2):
    vect = TfidfVectorizer(stop_words='english')
    tfidf = vect.fit_transform([text1, text2])
    cosine_sim = cosine_similarity(tfidf[0:1], tfidf[1:2])[0][0]
    return cosine_sim

def format_percentage(value):
    return round(value * 100, 2)

# --- Streamlit app starts here ---
st.set_page_config(page_title="Professional Resume Analyzer", page_icon="📄", layout="centered")

st.title("📄 Professional Resume Analyzer")
st.markdown("Upload your resume and job description to get a detailed match analysis.")

with st.form("upload_form"):
    resume_text = st.text_area("Paste your Resume text here", height=200)
    jd_text = st.text_area("Paste the Job Description here", height=200)
    submitted = st.form_submit_button("Analyze")

if submitted:
    if not resume_text.strip() or not jd_text.strip():
        st.error("Please enter both Resume and Job Description text.")
    else:
        # Clean texts
        resume_clean = clean_text(resume_text)
        jd_clean = clean_text(jd_text)

        # Compute overall similarity
        similarity_score = compute_cosine_similarity(resume_clean, jd_clean)
        overall_match_percent = format_percentage(similarity_score)

        # Extract skills
        resume_hard_skills = extract_skills(resume_clean, HARD_SKILLS)
        jd_hard_skills = extract_skills(jd_clean, HARD_SKILLS)

        resume_soft_skills = extract_skills(resume_clean, SOFT_SKILLS)
        jd_soft_skills = extract_skills(jd_clean, SOFT_SKILLS)

        # Find missing skills
        missing_hard_skills = list(set(jd_hard_skills) - set(resume_hard_skills))
        missing_soft_skills = list(set(jd_soft_skills) - set(resume_soft_skills))

        # Issues count for badges
        hard_skill_issues = len(missing_hard_skills)
        soft_skill_issues = len(missing_soft_skills)

        # Searchability checks (simple presence checks)
        searchability_issues = 0
        searchability_details = []
        for field, label in [(r'\b\d{10}\b', 'Phone Number'),
                             (r'\b[\w\.-]+@[\w\.-]+\.\w{2,4}\b', 'Email'),
                             (r'https?://[^\s]+', 'LinkedIn URL'),
                             (r'\baddress\b', 'Address')]:
            if re.search(field, resume_text.lower()):
                searchability_details.append(f"{label} found")
            else:
                searchability_details.append(f"{label} missing")
                searchability_issues += 1

        # Formatting issues - simple heuristic: check for columns / tables
        formatting_issues = 0
        formatting_details = []
        if re.search(r'\t', resume_text) or re.search(r' {5,}', resume_text):
            formatting_issues = 1
            formatting_details.append("Detected tab or multiple spaces suggesting column/table layout which may confuse ATS.")
        else:
            formatting_details.append("No complex formatting detected.")

        # Recruiter tips
        recruiter_tips = []
        if overall_match_percent < 70:
            recruiter_tips.append("Improve keyword coverage by adding missing hard and soft skills.")
        if formatting_issues:
            recruiter_tips.append("Simplify resume formatting to avoid ATS parsing errors.")
        if not re.search(r'\bsummary\b', resume_text.lower()):
            recruiter_tips.append("Add a concise Summary section to highlight your professional strengths.")
        if missing_hard_skills:
            recruiter_tips.append(f"Add missing technical skills: {', '.join(missing_hard_skills)}.")

        # Display Results

        # Overall Match Score
        st.header("Overall Match Score")
        st.metric(label="Resume vs Job Description Similarity", value=f"{overall_match_percent}%")

        # Searchability
        st.header("Searchability")
        st.success(f"{max(0,4 - searchability_issues)} of 4 key fields found")
        for detail in searchability_details:
            st.write(f"- {detail}")

        # Hard Skills
        st.header("Hard Skills")
        st.warning(f"{hard_skill_issues} issues to fix" if hard_skill_issues > 0 else "No hard skill issues")
        st.write("**Matched Hard Skills:** " + (", ".join(resume_hard_skills) if resume_hard_skills else "None"))
        st.write("**Missing Hard Skills:** " + (", ".join(missing_hard_skills) if missing_hard_skills else "None"))

        # Soft Skills
        st.header("Soft Skills")
        st.warning(f"{soft_skill_issues} issues to fix" if soft_skill_issues > 0 else "No soft skill issues")
        st.write("**Matched Soft Skills:** " + (", ".join(resume_soft_skills) if resume_soft_skills else "None"))
        st.write("**Missing Soft Skills:** " + (", ".join(missing_soft_skills) if missing_soft_skills else "None"))

        # Formatting
        st.header("Formatting Issues")
        if formatting_issues:
            st.error(f"{formatting_issues} formatting issue(s) detected")
        else:
            st.success("No formatting issues detected")
        for detail in formatting_details:
            st.write(f"- {detail}")

        # Recruiter Tips
        st.header("Recruiter Tips")
        if recruiter_tips:
            for tip in recruiter_tips:
                st.info(f"• {tip}")
        else:
            st.success("No specific recruiter tips, your resume looks great!")

        # Skill Match Table
        st.header("Skill Match Table (Resume vs Job Description)")
        all_skills = list(set(resume_hard_skills + jd_hard_skills))
        if not all_skills:
            st.write("No hard skills found in either resume or job description.")
        else:
            # Create table data
            data = []
            for skill in sorted(all_skills):
                data.append({
                    "Skill": skill,
                    "Resume Count": resume_clean.count(skill),
                    "JD Count": jd_clean.count(skill),
                })
            import pandas as pd
            df = pd.DataFrame(data)
            st.dataframe(df.style.format({"Resume Count": "{:.0f}", "JD Count": "{:.0f}"}))

