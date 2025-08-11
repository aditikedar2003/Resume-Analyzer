import streamlit as st
from io import StringIO
import re

# ---------- PAGE CONFIG ----------
st.set_page_config(page_title="Resume & JD Scanner", layout="wide")

# ---------- CUSTOM CSS ----------
st.markdown("""
    <style>
    /* Global font & color */
    body {
        font-family: Arial, sans-serif;
    }
    /* Headings */
    h1, h2, h3 {
        color: #6A0DAD;
    }
    /* Purple buttons */
    div.stButton > button {
        background-color: #6A0DAD;
        color: white;
        font-weight: bold;
        font-size: 16px;
        border-radius: 8px;
        height: 45px;
        width: 100%;
    }
    div.stButton > button:hover {
        background-color: #5a0bb3;
        color: white;
    }
    /* Upload box */
    section[data-testid="stFileUploadDropzone"] {
        border: 2px dashed #6A0DAD;
        border-radius: 10px;
    }
    /* Score circle */
    .score-badge {
        width: 120px;
        height: 120px;
        border-radius: 50%;
        background-color: #6A0DAD;
        display: flex;
        align-items: center;
        justify-content: center;
        color: white;
        font-size: 32px;
        font-weight: bold;
        margin: auto;
    }
    </style>
""", unsafe_allow_html=True)

# ---------- FAKE IN-MEMORY USERS ----------
users = {}
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "username" not in st.session_state:
    st.session_state.username = None

# ---------- LOGIN / SIGNUP ----------
if not st.session_state.logged_in:
    st.title("🔐 Login or Register")

    option = st.radio("Select option", ["Login", "Register"], horizontal=True)

    if option == "Register":
        new_user = st.text_input("Username")
        new_pass = st.text_input("Password", type="password")
        if st.button("Register"):
            if new_user in users:
                st.error("❌ Username already exists")
            elif new_user and new_pass:
                users[new_user] = new_pass
                st.success("✅ Registration successful! Please login.")
            else:
                st.error("❌ Please fill all fields.")

    elif option == "Login":
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        if st.button("Login"):
            if username in users and users[username] == password:
                st.session_state.logged_in = True
                st.session_state.username = username
                st.success(f"✅ Welcome {username}!")
            else:
                st.error("❌ Invalid username or password.")

else:
    st.title("📄 Resume & JD Analyzer")
    st.write(f"Welcome, **{st.session_state.username}** 👋")

    col1, col2 = st.columns(2)

    with col1:
        resume_file = st.file_uploader("Upload Resume (PDF/TXT)", type=["pdf", "txt"])
        resume_text_input = st.text_area("Or paste your resume text here", height=200)

    with col2:
        jd_file = st.file_uploader("Upload Job Description (TXT)", type=["txt"])
        jd_text_input = st.text_area("Or paste JD text here", height=200)

    if st.button("📊 Scan / Analyze"):
        resume_text = ""
        jd_text = ""

        # Read resume
        if resume_file:
            if resume_file.type == "text/plain":
                resume_text = StringIO(resume_file.getvalue().decode("utf-8")).read()
            else:
                st.error("Only TXT resumes are supported in this demo.")
        elif resume_text_input.strip():
            resume_text = resume_text_input.strip()

        # Read JD
        if jd_file:
            jd_text = StringIO(jd_file.getvalue().decode("utf-8")).read()
        elif jd_text_input.strip():
            jd_text = jd_text_input.strip()

        if not resume_text or not jd_text:
            st.error("Please provide both Resume and Job Description text.")
        else:
            # --- Simple matching analysis ---
            resume_words = set(re.findall(r"\w+", resume_text.lower()))
            jd_words = set(re.findall(r"\w+", jd_text.lower()))
            common_words = resume_words.intersection(jd_words)
            missing_words = jd_words - resume_words

            score = int((len(common_words) / len(jd_words)) * 100)

            st.markdown(f"<div class='score-badge'>{score}%</div>", unsafe_allow_html=True)

            st.subheader("✅ Strengths")
            st.write(", ".join(sorted(common_words)) if common_words else "No significant matches.")

            st.subheader("⚠ Missing Keywords")
            st.write(", ".join(sorted(missing_words)) if missing_words else "None — Great match!")

            st.subheader("💡 Suggestions")
            if score < 50:
                st.write("Add more keywords from the job description to your resume.")
            elif score < 80:
                st.write("Good match — consider fine-tuning phrasing to match JD keywords.")
            else:
                st.write("Excellent! Your resume is highly aligned with the JD.")

    if st.button("🚪 Logout"):
        st.session_state.logged_in = False
        st.session_state.username = None
