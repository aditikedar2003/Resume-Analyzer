import streamlit as st
from typing import List, Dict
import math

# --- Helper UI Components --- #
def progress_ring(label: str, value: float, color: str):
    # Draw a simple circular progress ring with SVG & CSS
    percent = int(value)
    st.markdown(f"""
    <style>
    .progress-ring {{
      position: relative;
      width: 120px;
      height: 120px;
      margin: auto;
    }}
    .progress-ring circle {{
      fill: transparent;
      stroke-width: 12;
      stroke-linecap: round;
      transform: rotate(-90deg);
      transform-origin: 50% 50%;
    }}
    .progress-ring__background {{
      stroke: #eee;
    }}
    .progress-ring__progress {{
      stroke: {color};
      stroke-dasharray: 339.292;
      stroke-dashoffset: {339.292 - 339.292 * (percent / 100)};
      transition: stroke-dashoffset 0.7s ease;
    }}
    .progress-ring__text {{
      position: absolute;
      top: 50%;
      left: 50%;
      transform: translate(-50%, -50%);
      font-size: 24px;
      font-weight: 700;
      color: {color};
    }}
    </style>
    <div class="progress-ring">
      <svg width="120" height="120">
        <circle class="progress-ring__background" r="54" cx="60" cy="60" />
        <circle class="progress-ring__progress" r="54" cx="60" cy="60" />
      </svg>
      <div class="progress-ring__text">{percent}%</div>
    </div>
    <div style="text-align:center; margin-top: -15px; font-weight:600;">{label}</div>
    """, unsafe_allow_html=True)

def badge(text: str, status: str = "info"):
    colors = {"info": "#2196F3", "success": "#4CAF50", "warning": "#FFC107", "danger": "#F44336"}
    color = colors.get(status, "#2196F3")
    st.markdown(f"""
    <span style="
        background-color: {color};
        color: white;
        padding: 3px 10px;
        border-radius: 12px;
        font-size: 0.85rem;
        font-weight: 600;
        margin-right: 6px;
        display: inline-block;">
        {text}
    </span>
    """, unsafe_allow_html=True)

def section_card(title: str):
    st.markdown(f"""
    <div style="
        background: #fff;
        padding: 20px 25px;
        margin-bottom: 25px;
        border-radius: 10px;
        box-shadow: 0 2px 10px rgb(0 0 0 / 0.07);">
        <h3 style="margin-bottom: 15px; color:#333;">{title}</h3>
    """, unsafe_allow_html=True)

def section_card_end():
    st.markdown("</div>", unsafe_allow_html=True)

# --- Sample backend results for demonstration ---
# Replace this with your actual backend keyword/NLP logic output
results = {
    "overall_match": 55.84,
    "searchability": {
        "issues": 0,
        "details": ["Address found", "Email found", "Phone number found", "LinkedIn link found — good job!"]
    },
    "hard_skills": {
        "issues": 1,
        "matched": {"core java": 6, "java": 6, "mysql": 3, "postgre": 3, "postgresql": 3, "rest": 1, "rest api": 1, "sql": 6},
        "missing": ["hibernate"]
    },
    "soft_skills": {
        "issues": 1,
        "matched": [],
        "missing": ["constructive feedback"],
        "suggestions": ["collaboration", "leadership", "communication"]
    },
    "recruiter_tips": [
        "Focus on incorporating key measurable achievements tied to the job’s core technical requirements for a stronger impact.",
        "Add a concise 2–3 line Summary at the top describing your role and measurable impact.",
        "Include the exact job title (e.g. 'Java Developer') in your Summary or Experience sections for better ATS matches.",
        "Simplify formatting: avoid columns or table-like layouts; use a clear vertical flow.",
        "Add missing critical skills: hibernate."
    ],
    "formatting": {
        "issues": 1,
        "details": ["Simplify columns or table-like formatting to a vertical layout for better ATS compatibility."]
    },
    "skill_match_table": [
        {"skill": "java", "resume_count": 5, "jd_count": 4},
        {"skill": "developer", "resume_count": 0, "jd_count": 2},
        {"skill": "design", "resume_count": 5, "jd_count": 2},
        {"skill": "develop", "resume_count": 2, "jd_count": 2},
        {"skill": "maintain", "resume_count": 0, "jd_count": 2},
        {"skill": "application", "resume_count": 1, "jd_count": 2},
        {"skill": "requirement", "resume_count": 0, "jd_count": 2},
        {"skill": "code", "resume_count": 1, "jd_count": 2},
        {"skill": "experience", "resume_count": 2, "jd_count": 2},
        {"skill": "location", "resume_count": 0, "jd_count": 1},
        {"skill": "remote", "resume_count": 1, "jd_count": 1},
        {"skill": "on-site", "resume_count": 0, "jd_count": 1},
        {"skill": "job", "resume_count": 0, "jd_count": 1},
        {"skill": "type", "resume_count": 0, "jd_count": 1},
        {"skill": "full-time", "resume_count": 0, "jd_count": 1},
        {"skill": "role", "resume_count": 0, "jd_count": 1},
        {"skill": "seek", "resume_count": 0, "jd_count": 1},
        {"skill": "skill", "resume_count": 1, "jd_count": 1},
        {"skill": "enterprise-level", "resume_count": 0, "jd_count": 1},
        {"skill": "will", "resume_count": 0, "jd_count": 1}
    ]
}

# --- Streamlit App Layout ---

st.set_page_config(page_title="Professional Resume Analyzer", page_icon="📄", layout="centered")

# Header Navigation (simple one-tab)
st.markdown("""
<style>
.navbar {
  background-color: #1976D2;
  padding: 12px 25px;
  color: white;
  font-size: 20px;
  font-weight: 700;
  border-radius: 8px;
  margin-bottom: 25px;
}
</style>
<div class="navbar">📄 Professional Resume Analyzer</div>
""", unsafe_allow_html=True)

st.title("Match Results Summary")

# Overall Match Score & Explanation
section_card("Overall Match Score")
progress_ring("Overall Match", results["overall_match"], "#4CAF50")
st.markdown(f"""
<p style="font-weight:600; color:#333; margin-top: 12px;">
Scored using a combination of keyword coverage and document semantic similarity.
</p>
""", unsafe_allow_html=True)
section_card_end()

# Searchability Section
section_card("Searchability")
badge(f"{results['searchability']['issues']} issues to fix", "success" if results['searchability']['issues'] == 0 else "danger")
for detail in results["searchability"]["details"]:
    st.markdown(f"- {detail}")
section_card_end()

# Hard Skills Section
section_card("Hard Skills")
badge(f"{results['hard_skills']['issues']} issues to fix", "warning" if results['hard_skills']['issues'] > 0 else "success")

st.markdown("**Top matched technical skills:**")
matched_skills_str = ", ".join(
    [f"{skill} ({count})" for skill, count in results["hard_skills"]["matched"].items()]
)
st.write(matched_skills_str)

st.markdown("**Top missing technical skills:**")
if results["hard_skills"]["missing"]:
    for skill in results["hard_skills"]["missing"]:
        badge(skill, "danger")
else:
    st.write("None — great job!")

section_card_end()

# Soft Skills Section
section_card("Soft Skills")
badge(f"{results['soft_skills']['issues']} issues to fix", "warning" if results['soft_skills']['issues'] > 0 else "success")

if results["soft_skills"]["matched"]:
    st.markdown("**Soft skills matched:**")
    st.write(", ".join(results["soft_skills"]["matched"]))
else:
    st.markdown("**No soft skills matched. Consider adding these high-impact soft skills:**")
    st.write(", ".join(results["soft_skills"]["suggestions"]))

st.markdown("**Missing soft skills:**")
if results["soft_skills"]["missing"]:
    for sskill in results["soft_skills"]["missing"]:
        badge(sskill, "danger")
else:
    st.write("None")

section_card_end()

# Recruiter Tips Section
section_card("Recruiter Tips")
for tip in results["recruiter_tips"]:
    st.markdown(f"• {tip}")
section_card_end()

# Formatting Section
section_card("Formatting Issues")
badge(f"{results['formatting']['issues']} issues to fix", "warning" if results['formatting']['issues'] > 0 else "success")
for fmt in results["formatting"]["details"]:
    st.markdown(f"- {fmt}")
section_card_end()

# Skill Match Table
section_card("Skills — Resume vs Job Description")
st.markdown("""
<style>
.skill-table {
  border-collapse: collapse;
  width: 100%;
  font-size: 14px;
}
.skill-table th, .skill-table td {
  border: 1px solid #ddd;
  padding: 8px 12px;
  text-align: center;
}
.skill-table th {
  background-color: #f2f2f2;
  font-weight: 600;
  color: #333;
}
</style>
<table class="skill-table">
  <thead>
    <tr>
      <th>Skill / Term</th>
      <th>Resume Count</th>
      <th>Job Description Count</th>
    </tr>
  </thead>
  <tbody>
""", unsafe_allow_html=True)

for skill_entry in results["skill_match_table"]:
    skill = skill_entry["skill"]
    rcount = skill_entry["resume_count"]
    jdcount = skill_entry["jd_count"]
    st.markdown(f"""
    <tr>
      <td>{skill}</td>
      <td>{rcount}</td>
      <td>{jdcount}</td>
    </tr>
    """, unsafe_allow_html=True)

st.markdown("""
  </tbody>
</table>
""", unsafe_allow_html=True)
section_card_end()

# Footer
st.markdown("""
<hr>
<p style="font-size: 13px; color: #999; text-align: center; margin-top: 40px;">
© 2025 Professional Resume Analyzer — Designed for polished, actionable feedback.
</p>
""", unsafe_allow_html=True)
