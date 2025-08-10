import streamlit as st

# ====== NAVIGATION STATE AND FUNCTION ======
if "page" not in st.session_state:
    st.session_state.page = "Home"

def navigate_to(page_name):
    st.session_state.page = page_name

# ====== HEADER WITH BUTTON NAVIGATION ======
col1, col2, col3, col4, col5, col6, col7, col8, col9 = st.columns([2,1,1,1,1,1,1,1,1])

with col1:
    st.image("assets/logo.png", width=50)  # ✅ Correct path
    st.markdown("**Resume Analyzer Pro**")

with col2:
    if st.button("Home"):
        navigate_to("Home")
with col3:
    if st.button("Scanner"):
        navigate_to("Scanner")
with col4:
    if st.button("Results"):
        navigate_to("Results")
with col5:
    if st.button("Dashboard"):
        navigate_to("Dashboard")
with col6:
    if st.button("Cover Letter"):
        navigate_to("Cover Letter")
with col7:
    if st.button("LinkedIn"):
        navigate_to("LinkedIn")
with col8:
    if st.button("Job Tracker"):
        navigate_to("Job Tracker")
with col9:
    if st.button("Account"):
        navigate_to("Account")

# ====== SIGN UP / LOGIN LINK TOP RIGHT ======
st.markdown(
    """
    <div style='position:absolute; top:10px; right:20px;'>
        <a href='#' style='text-decoration:none; font-weight:bold; color:#4CAF50;'>Sign Up / Login</a>
    </div>
    """,
    unsafe_allow_html=True
)

# ====== PAGE CONTENT ROUTING ======
page = st.session_state.page

def page_home():
    st.title("Welcome to Resume Analyzer Pro")
    st.write("Optimize your resume with AI-powered ATS scoring and suggestions.")

def page_scanner():
    st.title("Resume Scanner")
    uploaded_file = st.file_uploader("Upload your resume", type=["pdf", "docx"])
    if uploaded_file is not None:
        st.success("Resume uploaded successfully.")
    if st.button("Scan Resume"):
        # your scanning logic here
        navigate_to("Results")  # ✅ No experimental_rerun

def page_results():
    st.title("Results")
    st.write("Your resume match rate and keyword suggestions will appear here.")

def page_dashboard():
    st.title("Dashboard")
    st.write("View your saved resumes, scans, and analytics.")

def page_cover_letter():
    st.title("Cover Letter")
    st.write("Upload or generate a tailored cover letter.")

def page_linkedin():
    st.title("LinkedIn Optimizer")
    st.write("Optimize your LinkedIn profile for recruiters.")

def page_job_tracker():
    st.title("Job Tracker")
    st.write("Track and manage your job applications.")

def page_account():
    st.title("Account")
    st.write("Manage your account details here.")
    if st.button("Update Account"):
        # update logic here
        navigate_to("Home")  # ✅ No experimental_rerun

# ====== ROUTER ======
if page == "Home":
    page_home()
elif page == "Scanner":
    page_scanner()
elif page == "Results":
    page_results()
elif page == "Dashboard":
    page_dashboard()
elif page == "Cover Letter":
    page_cover_letter()
elif page == "LinkedIn":
    page_linkedin()
elif page == "Job Tracker":
    page_job_tracker()
elif page == "Account":
    page_account()
else:
    st.error("Page not found.")
