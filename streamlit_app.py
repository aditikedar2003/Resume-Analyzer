import streamlit as st
from utils.db import init_db
from utils.auth import register_user, login_user
from utils.extractor import extract_text_from_pdf
from utils.nlp import analyze_resume

st.set_page_config(page_title="Resume Analyzer Pro", layout="wide")

init_db()

if "page" not in st.session_state:
    st.session_state.page = "login"
if "match_results" not in st.session_state:
    st.session_state.match_results = None

def login_page():
    st.title("Login")
    email = st.text_input("Email")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        user = login_user(email, password)
        if user:
            st.session_state.page = "scanner"
            st.rerun()
        else:
            st.error("Invalid credentials")

def register_page():
    st.title("Sign Up")
    name = st.text_input("Full Name")
    email = st.text_input("Email")
    password = st.text_input("Password", type="password")
    if st.button("Register"):
        register_user(name, email, password)
        st.success("Registration successful! Please log in.")
        st.session_state.page = "login"
        st.rerun()

def scanner_page():
    st.title("Resume Scanner")
    resume_file = st.file_uploader("Upload Resume", type=["pdf"])
    job_desc = st.text_area("Paste Job Description")
    if st.button("Analyze"):
        if resume_file and job_desc:
            resume_text = extract_text_from_pdf(resume_file)
            results = analyze_resume(resume_text, job_desc)
            st.session_state.match_results = results
            st.session_state.page = "results"
            st.rerun()
        else:
            st.error("Please upload a resume and enter job description.")

def results_page():
    st.title("Match Results")
    if st.session_state.match_results:
        st.write(st.session_state.match_results)
    if st.button("Scan Another"):
        st.session_state.page = "scanner"
        st.rerun()

# Navigation
if st.session_state.page == "login":
    login_page()
elif st.session_state.page == "register":
    register_page()
elif st.session_state.page == "scanner":
    scanner_page()
elif st.session_state.page == "results":
    results_page()
