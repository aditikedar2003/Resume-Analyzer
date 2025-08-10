import streamlit as st
from utils.auth import login, signup, logout, is_authenticated
from utils.db import init_db
from utils.extractor import extract_text_from_pdf, extract_text_from_docx
from utils.nlp import analyze_resume, match_resume_to_job
import os
import tempfile

# Initialize DB
init_db()

# Page config
st.set_page_config(page_title="Resume Analyzer Pro", page_icon="assets/logo.png", layout="wide")

# Show Logo and Title
st.image("assets/logo.png", width=150)
st.markdown(
    "<h1 style='text-align: center; color: black;'>Resume Analyzer Pro</h1>",
    unsafe_allow_html=True
)
st.caption("Optimize your resume for ATS & improve job match rates.")

# Sidebar navigation
menu = st.sidebar.selectbox("Navigation", ["Login", "Sign Up", "Resume Analyzer", "Logout"])

# Session state for login
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "user_id" not in st.session_state:
    st.session_state.user_id = None

if menu == "Sign Up":
    st.subheader("Create a New Account")
    name = st.text_input("Full Name")
    email = st.text_input("Email")
    password = st.text_input("Password", type="password")
    if st.button("Sign Up"):
        if name and email and password:
            success, msg = signup(name, email, password)
            st.success(msg) if success else st.error(msg)
        else:
            st.error("Please fill in all fields.")

elif menu == "Login":
    st.subheader("Login to Your Account")
    email = st.text_input("Email")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        success, msg, user_id = login(email, password)
        if success:
            st.session_state.authenticated = True
            st.session_state.user_id = user_id
            st.success(msg)
        else:
            st.error(msg)

elif menu == "Resume Analyzer":
    if not st.session_state.authenticated:
        st.warning("Please login first.")
    else:
        st.subheader("Upload Your Resume and Job Description")
        resume_file = st.file_uploader("Upload Resume", type=["pdf", "docx"])
        job_file = st.file_uploader("Upload Job Description", type=["pdf", "docx"])

        if resume_file and job_file:
            # Save to temp files
            with tempfile.NamedTemporaryFile(delete=False) as temp_resume:
                temp_resume.write(resume_file.read())
                resume_path = temp_resume.name

            with tempfile.NamedTemporaryFile(delete=False) as temp_job:
                temp_job.write(job_file.read())
                job_path = temp_job.name

            # Extract text
            resume_text = extract_text_from_pdf(resume_path) if resume_file.name.endswith(".pdf") else extract_text_from_docx(resume_path)
            job_text = extract_text_from_pdf(job_path) if job_file.name.endswith(".pdf") else extract_text_from_docx(job_path)

            # Analyze
            score, matched_keywords = match_resume_to_job(resume_text, job_text)

            st.write(f"**Match Score:** {score}%")
            st.write(f"**Matched Keywords:** {', '.join(matched_keywords)}")

elif menu == "Logout":
    logout()
    st.success("Logged out successfully!")
