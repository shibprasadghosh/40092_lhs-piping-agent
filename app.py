import streamlit as st
import pandas as pd
import os
from datetime import datetime
import google.generativeai as genai

# পেজ কনফিগারেশন
st.set_page_config(page_title="LHS Project AI Agent", layout="wide")

# টাইটেল ও ওয়েলকাম মেসেজ
st.title("🤖 LHS Project - AI Data Assistant")
st.write("Welcome, Dear Project Team! 🚀 Your smart assistant for all LHS line nos., areas, joints, spools, and welding data. Feel free to ask anything in any language!")

# সাইডবার - প্রজেক্টের হাইলাইটস
st.sidebar.title("🛠️ Project LHS Info")
st.sidebar.write("This chat assistant helps you to:")
st.sidebar.info("- Check welding joint status")
st.sidebar.info("- Track area-wise work progress")
st.sidebar.info("- Find spool numbers & welder details")

# --- ভিজিটর লগ সেভ করার ফাংশন ---
def log_visitor(query_text):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"Time: {timestamp} | Query: {query_text}\n"
    with open("visitor_log.txt", "a", encoding="utf-8") as f:
        f.write(log_entry)

# ডেটাবেস লোড 
@st.cache_resource
def load_data():
    api_key = st.secrets["GOOGLE_API_KEY"]
    genai.configure(api_key=api_key)
    df = pd.read_excel("Merged_Master_Data_EXCEL_14Aug2026_114927_PM.xlsx", sheet_name="Master_Data", dtype=str)
    return df

df = load_data()

# কুইক বাটন
st.subheader("Quick Search:")
col1, col2 = st.columns(2)
if col1.button("Show Area 1P25A1 Progress"):
    st.session_state.query = "What is the total number of joints in Area 1P25A1?"
if col2.button("List all Welder No. 69 works"):
    st.session_state.query = "Find all rows where Welder No. is 69"

# চ্যাটবক্স
user_query = st.text_input("Enter your question here:", key="query")

if st.button("Search Database"):
    if user_query:
        log_visitor(user_query)
        
        with st.spinner("Searching through LHS database... 🕵️‍♂️"):
            try:
                # সরাসরি জেমিনির লেটেস্ট মডেল কনফিগার করা
                model = genai.GenerativeModel('gemini-1.5-flash')
                
                safety_settings = [
                    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                ]
                
                prompt = f"""
                You are an expert data analyst working with a Pandas DataFrame named `df`.
                The columns of the dataframe are: {list(df.columns)}
                
                The user asked this question: "{user_query}"
                
                Write ONLY executable Python code using pandas to get the answer from `df`. 
                Store the final result in a variable named `result`. 
                Do not include any markdown formatting like ```python or ``` in your response, just output the raw python code lines. Ensure `result` is printed or formatted properly.
                """
                
                response = model.generate_content(prompt, safety_settings=safety_settings)
                code = response.text.replace("```python", "").replace("```", "").strip()
                
                # সেফলি পাইথন কোড এক্সিকিউট করা
                local_vars = {"df": df, "pd": pd}
                exec(code, {}, local_vars)
                
                final_res = local_vars.get("result", "No result variable found.")
                
                st.success("Result found from database:")
                st.write(final_res)
                
            except Exception as e:
                st.error(f"Error executing query: {e}")
    else:
        st.warning("Please enter a question first!")

# --- অ্যাডভান্সড ফিচার: অ্যাক্টিভিটি লগ ---
st.markdown("---")
if st.checkbox("📋 View Team Activity Log (Admin Only)"):
    if os.path.exists("visitor_log.txt"):
        st.write("Here is the history of queries searched by the team:")
        with open("visitor_log.txt", "r", encoding="utf-8") as f:
            log_contents = f.read()
        st.text_area("Activity Logs", log_contents, height=150)
    else:
        st.info("No activity logs found yet. Start searching to record logs!")
