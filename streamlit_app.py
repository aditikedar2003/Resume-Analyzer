import streamlit as st
import psycopg2
import base64
from io import BytesIO
import pdfplumber
import re
import openai

# ================= DATABASE CONNECTION =================
DB_HOST = "dpg-d1p4gdjuibrs73dc70ig-a.oregon-postgres.render.com"
DB_NAME = "resume_analyzer_xv7a"
DB_USER = "resume_user"
DB_PASS = "Ujx0Y38UiFyhlJwobetKPBIgvc2FhyYz"

def get_db_connection():
    return psycopg2.connect(
        host=DB_HOST,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASS
    )

# ================= OPENAI CONFIG =================
openai.api_key = st.secrets.get("OPENAI_API_KEY", "")

# ================= SESSION STATE INIT =================
if "page" not in st.session_state:
    st.session_state.page = "HOME"
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "user_id" not in st.session_state:
    st.session_state.user_id = None

# ================= NAVIGATION BAR =================
def navbar():
    st.markdown("""
        <style>
        .navbar {
            display: flex;
            justify-content: center;
            gap: 40px;
            font-weight: bold;
            font-size: 18px;
            background-color: #f8f9fa;
            padding: 10px 0;
            border-bottom: 2px solid #ddd;
        }
        .navbar a {
            text-decoration: none;
            color: #333;
        }
        .navbar a:hover {
            color: #007bff;
        }
        </style>
        <div class="navbar">
            <a href="?page=HOME">HOME</a>
            <a href="?page=DASHBOARD">DASHBOARD</a>
            <a href="?page=RESUME_SCANNER">RESUME SCANNER</a>
            <a href="?page=COVER_LETTER">COVER LETTER</a>
            <a href="?page=LINKEDIN">LINKEDIN</a>
            <a href="?page=ACCOUNT">ACCOUNT</a>
        </div>
    """, unsafe_allow_html=True)

    query_params = st.query_params
    if "page" in query_params:
        st.session_state.page = query_params["page"]

# ================= PAGE FUNCTIONS =================
def page_home():
    st.title("Welcome to Resume Analyzer")
    st.write("Optimize your resume like a pro with AI-powered insights.")

def page_dashboard():
    st.title("Dashboard")
    st.write("Here’s an overview of your activity.")

def page_scanner():
    st.title("Resume Scanner")
    resume_file = st.file_uploader("Upload your Resume (PDF only)", type=["pdf"])
    jd_text = st.text_area("Paste Job Description")
    if st.button("Analyze"):
        if not resume_file or not jd_text.strip():
            st.error("Please upload a resume and paste a job description.")
            return
        
        with pdfplumber.open(resume_file) as pdf:
            resume_text = ""
            for page in pdf.pages:
                resume_text += page.extract_text() + "\n"

        # Simulated AI analysis
        st.success("Analysis complete!")
        st.write("Match Rate: 85%")
        st.write("Suggested Keywords: Python, SQL, Machine Learning")

def page_cover_letter():
    st.title("Cover Letter Scanner")
    st.write("Upload your cover letter for analysis.")

def page_linkedin():
    st.title("LinkedIn Optimizer")
    st.write("Optimize your LinkedIn profile.")

def page_account():
    st.title("Account Settings")
    if not st.session_state.logged_in:
        st.subheader("Sign Up")
        full_name = st.text_input("Full name")
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        if st.button("Register"):
            if not full_name or not email or not password:
                st.error("All fields are required.")
            else:
                conn = get_db_connection()
                cur = conn.cursor()
                cur.execute("INSERT INTO users (full_name, email, password) VALUES (%s, %s, %s) RETURNING id",
                            (full_name, email, password))
                st.session_state.user_id = cur.fetchone()[0]
                conn.commit()
                cur.close()
                conn.close()
                st.session_state.logged_in = True
                st.success("Account created successfully!")
                st.session_state.page = "DASHBOARD"  # Redirect without experimental_rerun
    else:
        st.write("You are logged in.")
        if st.button("Log Out"):
            st.session_state.logged_in = False
            st.session_state.page = "HOME"

# ================= ROUTER =================
navbar()
if st.session_state.page == "HOME":
    page_home()
elif st.session_state.page == "DASHBOARD":
    page_dashboard()
elif st.session_state.page == "RESUME_SCANNER":
    page_scanner()
elif st.session_state.page == "COVER_LETTER":
    page_cover_letter()
elif st.session_state.page == "LINKEDIN":
    page_linkedin()
elif st.session_state.page == "ACCOUNT":
    page_account()
