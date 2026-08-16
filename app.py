import streamlit as st
import pandas as pd
import os
import io
import csv
from datetime import datetime, timezone, timedelta
import google.generativeai as genai

st.set_page_config(page_title="LHS Project AI Agent", layout="wide")

st.title("🤖 LHS Project - AI Data Assistant")
st.write("Welcome, Dear Project Team! 🚀 Experience the next-generation AI Data Portal for advanced filtering, seamless line tracing, and smart piping insights.")

# --- Sidebar & User Tracking ---
st.sidebar.title("🛠️ Project LHS Info")
st.sidebar.info("- Check welding joint status\n- Track area-wise work progress\n- Find spool numbers & welder details")

st.sidebar.markdown("---")
st.sidebar.subheader("👤 User Authentication")
user_name = st.sidebar.text_input("Enter Your Name / Emp ID:", placeholder="E.g. Shib Prasad Ghosh (EMP-100949)")
st.sidebar.caption("⚠️ Required for tracking database queries.")

# --- Set Indian Standard Time (IST) ---
IST = timezone(timedelta(hours=5, minutes=30))

# --- Log Function (Upgraded to CSV for Excel Download) ---
def log_visitor(name, query_text):
    timestamp = datetime.now(IST).strftime("%Y-%m-%d %I:%M:%S %p")
    file_exists = os.path.isfile("visitor_log.csv")
    
    with open("visitor_log.csv", "a", newline='', encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["Date & Time", "User Name", "Search Query"]) # Header
        writer.writerow([timestamp, name, query_text])

@st.cache_resource
def load_data_and_models():
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
    df = pd.read_excel("Merged_Master_Data_EXCEL_14Aug2026_114927_PM.xlsx", sheet_name="Master_Data", dtype=str)
    
    df = df.apply(lambda x: x.str.strip().str.upper() if x.dtype == "object" else x)
    df = df.replace({'NAN': '', 'NAT': ''})
    
    for col in df.columns:
        if 'DATE' in col.upper():
            df[col] = df[col].apply(lambda x: str(x).split(' ')[0] if pd.notna(x) and str(x).upper() not in ['NAN', 'NAT', '', 'NONE'] else '')
    
    available_models = []
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods and 'tts' not in m.name and 'audio' not in m.name:
            available_models.append(m.name)
            
    return df, available_models

df, model_list = load_data_and_models()

# --- Session State Management ---
if 'filter_ids' not in st.session_state:
    st.session_state.filter_ids = []
if 'next_id' not in st.session_state:
    st.session_state.next_id = 0
if 'search_result_df' not in st.session_state:
    st.session_state.search_result_df = None
if 'success_msg' not in st.session_state:
    st.session_state.success_msg = ""
# নতুন: টেক্সট বক্সের স্টেট ট্র্যাক করার জন্য
if 'ai_query_input' not in st.session_state:
    st.session_state.ai_query_input = ""

def add_filter_row():
    st.session_state.filter_ids.append(st.session_state.next_id)
    st.session_state.next_id += 1

def remove_filter_row(fid):
    st.session_state.filter_ids.remove(fid)

# --- 🔄 Reset / Refresh Function ---
def reset_dashboard():
    st.session_state.filter_ids = []
    st.session_state.next_id = 0
    st.session_state.search_result_df = None
    st.session_state.success_msg = ""
    st.session_state.ai_query_input = "" # টেক্সট বক্স ক্লিয়ার করবে

# --- Smart Cascading Filter Builder ---
st.subheader("🎯 Smart Dynamic Filters:")
col_f_title, col_f_btn = st.columns([4, 1])
with col_f_title:
    st.write("Click '+' to add filter fields. Options will dynamically update based on your selections!")
with col_f_btn:
    st.button("🔄 Reset / Refresh", on_click=reset_dashboard, help="Clear all filters and search results")

active_conditions = []
progressive_df = df.copy() 

for i, fid in enumerate(st.session_state.filter_ids):
    col1, col2, col3 = st.columns([4, 4, 1])
    
    chosen_col = col1.selectbox(f"Filter Field {i+1}", ["(Select a Column)"] + list(df.columns), key=f"col_{fid}")
    
    if chosen_col != "(Select a Column)":
        raw_vals = [str(val).strip() for val in progressive_df[chosen_col].unique() if str(val).strip() != '']
        unique_vals = ["(Select a Value)"] + sorted(list(set(raw_vals)))
        
        chosen_val = col2.selectbox(f"Value for {chosen_col}", unique_vals, key=f"val_{fid}")
        
        if chosen_val != "(Select a Value)":
            active_conditions.append(f"`{chosen_col}` == '{chosen_val}'")
            progressive_df = progressive_df[progressive_df[chosen_col].astype(str).str.strip() == chosen_val]
    
    with col3:
        st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
        st.button("❌", key=f"del_{fid}", on_click=remove_filter_row, args=(fid,), help="Remove this filter")

st.button("➕ Add Another Filter Field", on_click=add_filter_row)

st.markdown("---")

# --- AI Natural Language Search ---
st.subheader("💬 Or Ask AI (Custom Question):")
# Key যোগ করা হয়েছে যাতে রিসেট করা যায়
user_query = st.text_input("Enter your question here in your preferred language (Leave blank if using filters above):", key="ai_query_input")

if st.button("Search Database"):
    if not user_name.strip():
        st.error("⚠️ Please enter your Name / Emp ID in the sidebar before searching!")
    else:
        active_query = user_query.strip()
        
        if active_conditions:
            auto_query = "Find all rows where " + " and ".join(active_conditions) + ". Show all columns."
            if active_query:
                active_query = auto_query + " Furthermore, apply this condition: " + active_query
            else:
                active_query = auto_query

        if active_query:
            if not model_list:
                st.error("Error: No valid text models found for this API Key.")
            else:
                log_visitor(user_name.strip(), active_query)
                with st.spinner("Bypassing restrictions & searching database... 🕵️‍♂️"):
                    success = False
                    final_res = None
                    successful_model = ""
                    error_logs = []
                    
                    prompt = f"""
                    You are an expert data analyst working with a Pandas DataFrame named `df`.
                    The columns of the dataframe are: {list(df.columns)}
                    
                    When generating the output table, strictly add a new column named 'Sl. No.' with dynamic serial numbers starting from 1. Do NOT include the original Excel row numbers or dataframe index.
                    
                    The user asked this question: "{active_query}"
                    
                    Write ONLY executable Python code using pandas to get the answer from `df`. 
                    Store the final result in a variable named `result`. 
                    Do not include markdown like ```python in your response.
                    """
                    
                    for m_name in model_list:
                        try:
                            model = genai.GenerativeModel(m_name)
                            response = model.generate_content(prompt)
                            code = response.text.replace("
