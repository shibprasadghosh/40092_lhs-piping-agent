import streamlit as st
import pandas as pd
import os
from datetime import datetime
import google.generativeai as genai

st.set_page_config(page_title="LHS Project AI Agent", layout="wide")

st.title("🤖 LHS Project - AI Data Assistant")
st.write("Welcome, Dear Project Team! 🚀 Your smart assistant for all LHS line nos., areas, joints, spools, and welding data.")

st.sidebar.title("🛠️ Project LHS Info")
st.sidebar.info("- Check welding joint status\n- Track area-wise work progress\n- Find spool numbers & welder details")

def log_visitor(query_text):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open("visitor_log.txt", "a", encoding="utf-8") as f:
        f.write(f"Time: {timestamp} | Query: {query_text}\n")

@st.cache_resource
def load_data_and_model():
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
    df = pd.read_excel("Merged_Master_Data_EXCEL_14Aug2026_114927_PM.xlsx", sheet_name="Master_Data", dtype=str)
    
    # ম্যাজিক ট্রিক: আমরা কোনো নাম ফিক্স করছি না! 
    # তোমার API Key যে মডেল সাপোর্ট করে, কোড নিজে থেকে সেটাই খুঁজে নেবে।
    valid_model = None
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            valid_model = m.name
            break
            
    return df, valid_model

df, auto_model_name = load_data_and_model()

st.subheader("Quick Search:")
col1, col2 = st.columns(2)
if col1.button("Show Area 1P25A1 Progress"):
    st.session_state.query = "What is the total number of joints in Area 1P25A1?"
if col2.button("List all Welder No. 69 works"):
    st.session_state.query = "Find all rows where Welder No. is 69"

user_query = st.text_input("Enter your question here:", key="query")

if st.button("Search Database"):
    if user_query:
        if not auto_model_name:
            st.error("Error: Your API Key does not have access to any text generation models.")
        else:
            log_visitor(user_query)
            with st.spinner(f"Searching using auto-detected model ({auto_model_name})... 🕵️‍♂️"):
                try:
                    model = genai.GenerativeModel(auto_model_name)
                    prompt = f"""
                    You are an expert data analyst working with a Pandas DataFrame named `df`.
                    The columns of the dataframe are: {list(df.columns)}
                    
                    The user asked this question: "{user_query}"
                    
                    Write ONLY executable Python code using pandas to get the answer from `df`. 
                    Store the final result in a variable named `result`. 
                    Do not include markdown like ```python in your response.
                    """
                    response = model.generate_content(prompt)
                    code = response.text.replace("```python", "").replace("```", "").strip()
                    
                    local_vars = {"df": df, "pd": pd}
                    exec(code, {}, local_vars)
                    
                    final_res = local_vars.get("result", "No result variable found.")
                    st.success("Result found from database:")
                    st.write(final_res)
                except Exception as e:
                    st.error(f"Error executing query: {e}")
    else:
        st.warning("Please enter a question first!")

st.markdown("---")
if st.checkbox("📋 View Team Activity Log (Admin Only)"):
    if os.path.exists("visitor_log.txt"):
        with open("visitor_log.txt", "r", encoding="utf-8") as f:
            st.text_area("Activity Logs", f.read(), height=150)
    else:
        st.info("No logs yet.")
