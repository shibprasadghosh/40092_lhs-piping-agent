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
    df = pd.read_excel("Merged_Master_Data_EXCEL_14Aug2026_114927_PM.xlsx", sheet_name="Master_Data", dtype=str)
    
    # তোমার API কী যে যে মডেল সাপোর্ট করে তার একটা লিস্ট বানাচ্ছি
    available_models = []
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            available_models.append(m.name)
            
    return df, available_models

df, model_list = load_data_and_models()

st.subheader("Quick Search:")
col1, col2 = st.columns(2)
if col1.button("Show Area 1P25A1 Progress"):
    st.session_state.query = "What is the total number of joints in Area 1P25A1?"
if col2.button("List all Welder No. 69 works"):
    st.session_state.query = "Find all rows where Welder No. is 69"

user_query = st.text_input("Enter your question here:", key="query")

if st.button("Search Database"):
    if user_query:
        if not model_list:
            st.error("Error: No valid text models found for this API Key.")
        else:
            log_visitor(user_query)
            with st.spinner("Bypassing Google restrictions & searching database... 🕵️‍♂️"):
                success = False
                error_logs = []
                
                prompt = f"""
                You are an expert data analyst working with a Pandas DataFrame named `df`.
                The columns of the dataframe are: {list(df.columns)}
                
                When generating the output table, strictly add a new column named 'Sl. No.' with dynamic serial numbers starting from 1. Do NOT include the original Excel row numbers or dataframe index.
                
                The user asked this question: "{user_query}"
                
                Write ONLY executable Python code using pandas to get the answer from `df`. 
                Store the final result in a variable named `result`. 
                Do not include markdown like ```python in your response.
                """
                
                # লুপ চালিয়ে সব মডেল চেক করা হচ্ছে, যেটা কাজ করবে সেটা দিয়েই রেজাল্ট দেখাবে
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
                        break # কাজ হয়ে গেলে লুপ বন্ধ!
                    except Exception as e:
                        error_logs.append(f"Failed with {m_name}: {str(e)}")
                        continue # ফেইল করলে পরের মডেল ট্রাই করবে
                
                if not success:
                    st.error("❌ Google API is blocking all available models. Error details:")
                    for err in error_logs:
                        st.write(err)
    else:
        st.warning("Please enter a question first!")

st.markdown("---")
if st.checkbox("📋 View Team Activity Log (Admin Only)"):
    if os.path.exists("visitor_log.txt"):
        with open("visitor_log.txt", "r", encoding="utf-8") as f:
            st.text_area("Activity Logs", f.read(), height=150)
    else:
        st.info("No logs yet.")
