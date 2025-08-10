import streamlit as st
from PIL import Image
import os

# ===============================
# PAGE CONFIGURATION
# ===============================
st.set_page_config(
    page_title="Resume Analyzer",
    page_icon="assets/logo.png",
    layout="wide",
)

# ===============================
# CUSTOM CSS
# ===============================
st.markdown("""
    <style>
    /* Main theme color - purple */
    :root {
        --main-color: #800080;
    }
    /* Header logo container */
    .header-container {
        display: flex;
        align-items: center;
        justify-content: flex-start;
        padding: 8px 20px;
        background-color: white;
        border-bottom: 2px solid var(--main-color);
    }
    .header-logo {
        height: 45px;
        margin-right: 15px;
    }
    .header-title {
        font-size: 26px;
        font-weight: bold;
        color: var(--main-color);
        white-space: nowrap;
    }
    /* Buttons */
    div.stButton > button {
        background-color: var(--main-color);
        color: white;
        border-radius: 6px;
        border: none;
        padding: 0.4rem 1rem;
        font-size: 16px;
        cursor: pointer;
    }
    div.stButton > button:hover {
        background-color: #9932CC; /* lighter purple on hover */
    }
    /* Hide default Streamlit menu */
    #MainMenu, header, footer {visibility: hidden;}
    </style>
""", unsafe_allow_html=True)

# ===============================
# HEADER SECTION
# ===============================
with st.container():
    logo_path = os.path.join("assets", "logo.png")
    if os.path.exists(logo_path):
        logo = Image.open(logo_path)
        col1, col2 = st.columns([0.08, 1])  # Slightly wider col1 for better word fit
        with col1:
            st.image(logo, use_container_width=True)
        with col2:
            st.markdown("<div class='header-title'>Resume Analyzer</div>", unsafe_allow_html=True)
    else:
        st.warning("Logo not found. Please check assets/logo.png.")

# ===============================
# SIDEBAR NAVIGATION
# ===============================
st.sidebar.title("📂 Navigation")
page = st.sidebar.radio("Go to", ["🏠 Home", "📄 Resume Scanner", "✉️ Cover Letter Scanner", "💼 LinkedIn Optimizer", "📊 Job Tracker"])

# ===============================
# PAGE CONTENT
# ===============================
if page == "🏠 Home":
    st.header("Welcome to Resume Analyzer")
    st.write("Easily check your resume against job descriptions, optimize for ATS, and get keyword suggestions.")
elif page == "📄 Resume Scanner":
    st.header("Resume Scanner")
    st.write("Upload your resume and job description to get match rate and improvement tips.")
elif page == "✉️ Cover Letter Scanner":
    st.header("Cover Letter Scanner")
    st.write("Upload your cover letter for analysis.")
elif page == "💼 LinkedIn Optimizer":
    st.header("LinkedIn Optimizer")
    st.write("Analyze your LinkedIn profile for better reach.")
elif page == "📊 Job Tracker":
    st.header("Job Tracker")
    st.write("Track your job applications easily.")

# ===============================
# FOOTER
# ===============================
st.markdown("<hr>", unsafe_allow_html=True)
st.markdown(
    "<center style='color: gray;'>© 2025 Resume Analyzer. All rights reserved.</center>",
    unsafe_allow_html=True
)
