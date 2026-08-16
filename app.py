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
    
    available_models = []
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            available_models.append(m.name)
            
    return df, available_models

df, model_list = load_data_and_models()

# --- Dynamic Custom Filter Builder ---
st.subheader("🎯 Dynamic Filters:")
st.write("Select any column from your database to filter. Click '+' to add more filter fields.")

if 'filter_rows' not in st.session_state:
    st.session_state.filter_rows = 1

def add_filter_row():
    st.session_state.filter_rows += 1

active_conditions = []

for i in range(st.session_state.filter_rows):
    col1, col2 = st.columns(2)
    
    chosen_col = col1.selectbox(f"Filter Field {i+1}", ["(Select a Column)"] + list(df.columns), key=f"col_{i}")
    
    if chosen_col != "(Select a Column)":
        unique_vals = ["(Select a Value)"] + sorted(df[chosen_col].dropna().astype(str).unique().tolist())
        chosen_val = col2.selectbox(f"Value for {chosen_col}", unique_vals, key=f"val_{i}")
        
        if chosen_val != "(Select a Value)":
            active_conditions.append(f"`{chosen_col}` == '{chosen_val}'")

st.button("➕ Add Another Filter Field", on_click=add_filter_row)

st.markdown("---")

# --- AI Natural Language Search ---
st.subheader("💬 Or Ask AI (Custom Question):")
user_query = st.text_input("Enter your question here (Leave blank if using filters above):")

if st.button("Search Database"):
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
                        
                        st.success(f"✅ Success! (Powered by AI)")
                        
                        if isinstance(final_res, pd.DataFrame):
                            # টেবিল ডিসপ্লে করা
                            st.dataframe(final_res, hide_index=True, use_container_width=False)
                            
                            # --- ডাউনলোড এর জন্য ওয়াটারমার্ক লজিক ---
                            dl_df = final_res.copy()
                            # একটা ফাঁকা লাইন যোগ করা
                            dl_df.loc[len(dl_df)] = [""] * len(dl_df.columns)
                            # ওয়াটারমার্ক লাইন যোগ করা
                            watermark_row = [""] * len(dl_df.columns)
                            watermark_row[0] = "© Generated by LHS AI Assistant - Created by Shib Prasad Ghosh"
                            dl_df.loc[len(dl_df)] = watermark_row
                            
                            csv = dl_df.to_csv(index=False).encode('utf-8')
                            st.download_button(
                                label="📥 Download Result (CSV)",
                                data=csv,
                                file_name=f"LHS_Search_Result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                                mime="text/csv"
                            )
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

# --- Footer: Subtle Watermark for Webpage ---
st.markdown(
    """
    <br><br>
    <div style='text-align: right; color: rgba(255, 255, 255, 0.15); font-size: 14px; font-weight: normal; user-select: none; pointer-events: none;'>
        <i>© Created by Shib Prasad Ghosh</i>
    </div>
    """, 
    unsafe_allow_html=True
)
