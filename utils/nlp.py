import openai
import os
from dotenv import load_dotenv

load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

def analyze_resume(resume_text, job_desc):
    prompt = f"Compare the following resume to the job description and give a match score out of 100, plus matched keywords:\n\nResume:\n{resume_text}\n\nJob Description:\n{job_desc}"
    response = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content
