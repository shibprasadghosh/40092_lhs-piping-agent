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
def load_data_and_models():
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
    # এক্সেল থেকে ডেটা লোড
    df = pd.read_excel("Merged_Master_Data_EXCEL_14Aug2026_114927_PM.xlsx", sheet_name="Master_Data", dtype=str)
    
    available_models = []
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            available_models.append(m.name)
            
    return df, available_models

df, model_list = load_data_and_models()

# ডেটাবেস থেকে ইউনিক (Unique) ভ্যালু খুঁজে ড্রপডাউন বানানোর ফাংশন
def get_dropdown_options(col_name):
    for col in df.columns:
        if str(col).strip().lower() == col_name.strip().lower():
            options = df[col].dropna().astype(str).unique().tolist()
            return [""] + sorted(options)
    return [""]

# --- Quick Filter Section (Dropdowns) ---
st.subheader("🎯 Quick Filters (Select to filter):")
col1, col2, col3, col4, col5 = st.columns(5)
f_line = col1.selectbox("Line No.", get_dropdown_options("Line No."))
f_area = col2.selectbox("Area", get_dropdown_options("Area"))
f_loop = col3.selectbox("Loop No.", get_dropdown_options("Loop No."))
f_xr = col4.selectbox("XR No.", get_dropdown_options("XR No."))
f_group = col5.selectbox("Group No.", get_dropdown_options("Group No."))

st.markdown("---")

# --- Custom Column Filter (Dynamic) ---
st.subheader("🔍 Custom Column Filter:")
st.write("Select any column from the database to filter by its exact value:")
ccol1, ccol2 = st.columns(2)
custom_col = ccol1.selectbox("Select Database Column", [""] + list(df.columns))

custom_val = ""
if custom_col:
    # কলাম সিলেক্ট করলে তবেই তার ভেতরের ভ্যালুর ড্রপডাউনটা আসবে
    custom_val = ccol2.selectbox(f"Select value for {custom_col}", [""] + sorted(df[custom_col].dropna().astype(str).unique().tolist()))

st.markdown("---")

# --- AI Natural Language Search ---
st.subheader("💬 Or Ask AI (Custom Question):")
user_query = st.text_input("Enter your question here (Leave blank if using filters above):")

if st.button("Search Database"):
    # ড্রপডাউন থেকে ফিল্টার কন্ডিশন বানানো
    conditions = []
    if f_line: conditions.append(f"`Line No.` == '{f_line}'")
    if f_area: conditions.append(f"`Area` == '{f_area}'")
    if f_loop: conditions.append(f"`Loop No.` == '{f_loop}'")
    if f_xr: conditions.append(f"`XR No.` == '{f_xr}'")
    if f_group: conditions.append(f"`Group No.` == '{f_group}'")
    if custom_col and custom_val: conditions.append(f"`{custom_col}` == '{custom_val}'")

    active_query = user_query.strip()
    if conditions:
        active_query = "Find all rows where " + " and ".join(conditions) + ". Show all columns."

    if active_query:
        if not model_list:
            st.error("Error: No valid text models found for this API Key.")
        else:
            log_visitor(active_query)
            with st.spinner("Bypassing restrictions & searching database... 🕵️‍♂️"):
                success = False
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
                        code = response.text.replace("```python", "").replace("```", "").strip()
                        
                        local_vars = {"df": df, "pd": pd}
                        exec(code, {}, local_vars)
                        
                        final_res = local_vars.get("result", "No result variable found.")
                        
                        st.success(f"✅ Success! (Powered by {m_name})")
                        
                        if isinstance(final_res, pd.DataFrame):
                            st.dataframe(final_res, hide_index=True, use_container_width=False)
                        else:
                            st.write(final_res)
                            
                        success = True
                        break 
                    except Exception as e:
                        error_logs.append(f"Failed with {m_name}: {str(e)}")
                        continue 
                
                if not success:
                    st.error("❌ Google API is blocking all available models. Error details:")
                    for err in error_logs:
                        st.write(err)
    else:
        st.warning("Please enter a question or select at least one filter first!")

st.markdown("---")
if st.checkbox("📋 View Team Activity Log (Admin Only)"):
    if os.path.exists("visitor_log.txt"):
        with open("visitor_log.txt", "r", encoding="utf-8") as f:
            st.text_area("Activity Logs", f.read(), height=150)
    else:
        st.info("No logs yet.")

# --- Footer: Created by Shib Prasad Ghosh (Now fully visible!) ---
st.markdown(
    """
    <br><br>
    <div style='text-align: right; color: #a0a0a0; font-size: 18px; font-weight: bold;'>
        🚀 Created by <span style='color: #ffffff;'>Shib Prasad Ghosh</span>
    </div>
    """, 
    unsafe_allow_html=True
)
