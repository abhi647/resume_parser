import streamlit as st
import openai
import sqlite3
import fitz  # PyMuPDF
import re  # Regular expression module for parsing
import pandas as pd
from concurrent.futures import ThreadPoolExecutor
from config import OPENAI_API_KEY

# Initialize OpenAI API
openai.api_key = OPENAI_API_KEY

# Create SQLite connection
conn = sqlite3.connect('candidates.db',check_same_thread=False)
c = conn.cursor()

# Create table if it doesn't exist
c.execute('''CREATE TABLE IF NOT EXISTS candidates
             (name TEXT, email TEXT, score REAL)''')

# Function to call OpenAI API for job description and CV parsing
def call_openai_api(messages):
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=messages
    )
    return response.choices[0].message['content'].strip()

# Function to match CV with JD and extract suitability score
def match_cv_with_jd(jd_text, cv_text):
    messages = [
        {"role": "system", "content": "You are a helpful assistant that matches CVs with job descriptions and assigns suitability scores."},
        {"role": "user", "content": f"Job Description: {jd_text}\n\nCV: {cv_text}\n\nIdentify the relevant skills, qualifications, experience, and educational background. Provide an overall suitability score out of 100. The score should reflect how well the CV matches the job description. Consider factors such as matching skills, years of experience, and educational background. Ensure that the scores are precise and not the same for all CVs."}
    ]
    result = call_openai_api(messages)
    st.write("API Response:", result)  # Add this line for debugging
    # Extract the suitability score using regular expression
    score_match = re.search(r'Overall Suitability Score for the Job: (\d+)', result)
    if not score_match:
        score_match = re.search(r'Overall Suitability Score: (\d+)', result)
    score = float(score_match.group(1)) if score_match else 0
    
    return score

# Function to extract text from PDF
def extract_text_from_pdf(pdf_file):
    document = fitz.open(stream=pdf_file.read(), filetype="pdf")
    text = ""
    for page in document:
        text += page.get_text()
    return text

# Function to extract email from text
def extract_email(text):
    email_match = re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', text)
    return email_match.group(0) if email_match else None

# Process each CV and insert results into the database
def process_cv(jd_text, uploaded_file):
    cv_text = extract_text_from_pdf(uploaded_file)
    score = match_cv_with_jd(jd_text, cv_text)
    name = uploaded_file.name.split('.')[0]  # Assuming the file name is the candidate's name
    email = extract_email(cv_text) or "no-email@example.com"  # Extract email from CV text or use a default value
    
    # Save to database
    c.execute("INSERT INTO candidates (name, email, score) VALUES (?, ?, ?)", (name, email, score))
    conn.commit()
    
    return (name, email, score)

# Load custom CSS
def load_css(file_name):
    with open(file_name) as f:
        st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)

# Streamlit UI

# Load custom CSS
load_css("style.css")

# Input JD
st.markdown("""
    <style>
        /* CSS to change text color */
        .fileinput-upload-display-name {
            color: red; /* Change the color to your desired color */
        }
    </style>
""", unsafe_allow_html=True)


new_title = '<p style="font-family:sans-serif; color:#FFFFFF; font-size: 24px;">Enter the Job Description here</p>'
st.markdown(new_title, unsafe_allow_html=True)
jd_text = st.text_area("", placeholder="Enter the Job Description here")


# Upload CVs
new_title = '<p style="font-family:sans-serif; color:#FFFFFF; font-size: 24px;">Upload Multiple CVs</p>'
st.markdown(new_title, unsafe_allow_html=True)
new_title = '<p style="font-family:sans-serif; color:#FFFFFF; font-size: 18px;">Choose CV files</p>'
st.markdown(new_title, unsafe_allow_html=True)
uploaded_files = st.file_uploader("", accept_multiple_files=True, type=["pdf"])

if st.button("Process"):
    if jd_text and uploaded_files:
        with st.spinner('Processing CVs...'):
            # Use ThreadPoolExecutor for concurrent processing
            with ThreadPoolExecutor() as executor:
                futures = [executor.submit(process_cv, jd_text, uploaded_file) for uploaded_file in uploaded_files]
                results = [future.result() for future in futures]
        
        # Display results in a table format
        new_title = '<p style="font-family:sans-serif; color:#FFFFFF; font-size: 18px;">Matching Results</p>'
        st.markdown(new_title, unsafe_allow_html=True)
        df = pd.DataFrame(results, columns=["Name", "Email", "Suitability Score"])
        st.write(df)
    else:
        st.error("Please enter a Job Description and upload CVs.")

# Close SQLite connection
conn.close()