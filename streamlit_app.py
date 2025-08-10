import streamlit as st

# ====== NAVIGATION STATE AND FUNCTION ======
if "page" not in st.session_state:
    st.session_state.page = "Home"

def navigate_to(page_name):
    st.session_state.page = page_name

# ====== HEADER WITH BUTTON NAVIGATION ======
col1, col2, col3, col4, col5, col6, col7, col8, col9 = st.columns([2,1,1,1,1,1,1,1,1])

with col1:
    st.image("logo (2).png", width=50)
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
    # Your existing home page content here
    # Removed the "This version runs without a database" info message as requested

def page_scanner():
    st.title("Resume Scanner")
    # Your existing scanner page code here
    # On some event (e.g. after scan completed), replace st.experimental_rerun() with:
    # navigate_to("Results")
    # Example placeholder:
    if st.button("Scan Resume"):
        # your scanning logic here
        navigate_to("Results")

def page_results():
    st.title("Results")
    # Your existing results page content here

def page_dashboard():
    st.title("Dashboard")
    # Your existing dashboard content here

def page_cover_letter():
    st.title("Cover Letter")
    # Your existing cover letter page content here

def page_linkedin():
    st.title("LinkedIn Optimizer")
    # Your existing LinkedIn page content here

def page_job_tracker():
    st.title("Job Tracker")
    # Your existing job tracker page content here

def page_account():
    st.title("Account")
    # Your existing account page content here
    # On some event (e.g. after update), replace st.experimental_rerun() with:
    # navigate_to("Home")
    # Example placeholder:
    if st.button("Update Account"):
        # your update logic here
        navigate_to("Home")

# Route to the right page function
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

