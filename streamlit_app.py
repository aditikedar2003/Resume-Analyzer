import streamlit as st
from pathlib import Path
import psycopg2
import os

# =========================
#  DATABASE CONNECTION
# =========================
def get_db_connection():
    return psycopg2.connect(
        host="dpg-d1p4gdjuibrs73dc70ig-a.oregon-postgres.render.com",
        dbname="resume_analyzer_xv7a",
        user="resume_user",
        password="Ujx0Y38UiFyhlJwobetKPBIgvc2FhyYz",
        port=5432
    )

# =========================
#  PAGE CONFIG
# =========================
st.set_page_config(
    page_title="Resume Analyzer",
    page_icon="📄",
    layout="wide"
)

# =========================
#  CUSTOM CSS
# =========================
st.markdown("""
    <style>
    /* Purple theme for buttons */
    div.stButton > button {
        background-color: #800080;
        color: white;
        border-radius: 8px;
        padding: 0.4em 1.2em;
        font-size: 16px;
        font-weight: 500;
        border: none;
        cursor: pointer;
    }
    div.stButton > button:hover {
        background-color: #9932CC;
        color: white;
    }
    /* Header alignment */
    .header-container {
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    .nav-buttons {
        display: flex;
        gap: 10px;
    }
    </style>
""", unsafe_allow_html=True)

# =========================
#  NAVIGATION STATE
# =========================
if "current_page" not in st.session_state:
    st.session_state.current_page = "Home"

def navigate_to(page_name):
    st.session_state.current_page = page_name

# =========================
#  HEADER WITH LOGO + NAV
# =========================
logo_path = Path("assets/logo.png")
if logo_path.exists():
    logo_img = f"<img src='data:image/png;base64,{logo_path.read_bytes().hex()}'/>"

col1, col2 = st.columns([1, 3])
with col1:
    st.image(str(logo_path), width=150)
with col2:
    nav_col1, nav_col2 = st.columns([5, 1])
    with nav_col1:
        nav1, nav2, nav3, nav4, nav5, nav6, nav7 = st.columns([1.2, 1.8, 2, 2, 1.6, 1.4, 1.6])
        with nav1:
            if st.button("Home"):
                navigate_to("Home")
        with nav2:
            if st.button("Resume Scanner"):
                navigate_to("Resume Scanner")
        with nav3:
            if st.button("Cover Letter"):
                navigate_to("Cover Letter")
        with nav4:
            if st.button("LinkedIn Optimizer"):
                navigate_to("LinkedIn Optimizer")
        with nav5:
            if st.button("Job Tracker"):
                navigate_to("Job Tracker")
        with nav6:
            if st.button("Pricing"):
                navigate_to("Pricing")
        with nav7:
            if st.button("Resources"):
                navigate_to("Resources")
    with nav_col2:
        if st.button("Sign Up / Login"):
            navigate_to("Auth")

st.markdown("---")

# =========================
#  PAGE CONTENT
# =========================
if st.session_state.current_page == "Home":
    st.title("Welcome to Resume Analyzer")
    st.write("Your AI-powered ATS Resume Optimization Tool.")

elif st.session_state.current_page == "Resume Scanner":
    st.title("Resume Scanner")
    st.write("Upload your resume and job description to check match rate.")
    # Your resume scanner code here

elif st.session_state.current_page == "Cover Letter":
    st.title("Cover Letter Scanner")
    st.write("Upload and analyze your cover letter.")
    # Your cover letter scanner code here

elif st.session_state.current_page == "LinkedIn Optimizer":
    st.title("LinkedIn Optimizer")
    st.write("Optimize your LinkedIn profile with AI suggestions.")
    # Your LinkedIn optimizer code here

elif st.session_state.current_page == "Job Tracker":
    st.title("Job Tracker")
    st.write("Track your job applications here.")
    # Your job tracker code here

elif st.session_state.current_page == "Pricing":
    st.title("Pricing Plans")
    st.write("Choose the plan that fits your needs.")

elif st.session_state.current_page == "Resources":
    st.title("Resources")
    st.write("Resume tips, cover letter guides, and more.")

elif st.session_state.current_page == "Auth":
    st.title("Sign Up / Login")
    st.write("Authentication page content here.")
