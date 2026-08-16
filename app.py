import streamlit as st
import pandas as pd
import os
import io
from datetime import datetime
import google.generativeai as genai

st.set_page_config(page_title="LHS Project AI Agent", layout="wide")

st.title("🤖 LHS Project - AI Data Assistant")
st.write("Welcome, Dear Project Team! 🚀 Experience the next-generation AI Data Portal for advanced filtering, seamless line tracing, and smart piping insights.")

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
    
    # 1. Data Cleaning (Whitespace & Uppercase)
    df = df.apply(lambda x: x.str.strip().str.upper() if x.dtype == "object" else x)
    df = df.replace({'NAN': '', 'NAT': ''})
    
    # 2. SAFE DATE CLEANER (স্ট্রিং ম্যানিপুলেশন দিয়ে 00:00:00 উড়িয়ে দেওয়া)
    for col in df.columns:
        if 'DATE' in col.upper():
            # যদি ডেটের সাথে টাইম থাকে (যেমন '2026-03-31 00:00:00'), তবে শুধু প্রথম অংশটা নেব
            df[col] = df[col].astype(str).apply(lambda x: x.split(' ')[0] if ' ' in x else x)
            df[col] = df[col].replace({'NAN': '', 'NAT': '', 'NATTYPE': ''})
    
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

def add_filter_row():
    st.session_state.filter_ids.append(st.session_state.next_id)
    st.session_state.next_id += 1

def remove_filter_row(fid):
    st.session_state.filter_ids.remove(fid)

def reset_dashboard():
    st.session_state.filter_ids = []
    st.session_state.next_id = 0
    st.session_state.search_result_df = None
    st.session_state.success_msg = ""

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
                        code = response.text.replace("```python", "").replace("```", "").strip()
                        
                        local_vars = {"df": df, "pd": pd}
                        exec(code, {}, local_vars)
                        
                        final_res = local_vars.get("result", "No result variable found.")
                        successful_model = m_name
                        success = True
                        break 
                    except Exception as e:
                        error_logs.append(f"Failed with {m_name}: {str(e)}")
                        continue 
                
                if success and isinstance(final_res, pd.DataFrame):
                    st.session_state.search_result_df = final_res
                    st.session_state.success_msg = f"✅ Success! (Powered by {successful_model})"
                else:
                    st.session_state.search_result_df = None
                    st.session_state.success_msg = ""
                    st.error("❌ No matching data found or API error.")
    else:
        st.warning("Please enter a question or select at least one filter first!")

if st.session_state.search_result_df is not None:
    res_df = st.session_state.search_result_df
    
    if res_df.empty:
        st.warning("⚠️ No matching data found! Please try different filters.")
    else:
        st.success(st.session_state.success_msg)
        
        hide_empty = st.checkbox("👁️ Hide columns with only 'None' or empty values", value=True)
        
        display_df = res_df.copy()
        if hide_empty:
            display_df = display_df.replace(['None', 'none', 'NAN', 'nan', ''], pd.NA)
            display_df = display_df.dropna(axis=1, how='all')
            display_df = display_df.fillna('')
        
        st.dataframe(display_df, hide_index=True, use_container_width=False)
        
        st.markdown("### 📥 Download Results")
        dl_col1, dl_col2, _ = st.columns([1, 1, 2])
        
        def add_watermark(d_frame):
            df_w = d_frame.copy()
            df_w.loc[len(df_w)] = [""] * len(df_w.columns)
            w_row = [""] * len(df_w.columns)
            w_row[0] = "© Generated by LHS AI-Powered Dashboard - Created by Shib Prasad Ghosh"
            df_w.loc[len(df_w)] = w_row
            return df_w
        
        csv_df = add_watermark(display_df)
        csv = csv_df.to_csv(index=False).encode('utf-8')
        dl_col1.download_button(
            label="📄 Download as CSV",
            data=csv,
            file_name=f"LHS_Search_Result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv"
        )
        
        try:
            excel_df = add_watermark(display_df)
            excel_buffer = io.BytesIO()
            with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                excel_df.to_excel(writer, index=False, sheet_name='Search_Result')
            excel_data = excel_buffer.getvalue()
            
            dl_col2.download_button(
                label="📊 Download as Excel",
                data=excel_data,
                file_name=f"LHS_Search_Result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        except ModuleNotFoundError:
            dl_col2.warning("⚠️ Excel download requires 'openpyxl'. Please use CSV.")

st.markdown("---")
if st.checkbox("📋 View Team Activity Log (Admin Only)"):
    if os.path.exists("visitor_log.txt"):
        with open("visitor_log.txt", "r", encoding="utf-8") as f:
            st.text_area("Activity Logs", f.read(), height=150)
    else:
        st.info("No logs yet.")

# --- Footer ---
st.markdown(
    """
    <br><br>
    <div style='text-align: right; user-select: none; pointer-events: none;'>
        <span style='color: #E0E0E0; font-size: 16px; font-weight: bold; letter-spacing: 1px;'>🚀 AI-POWERED SMART DATA DASHBOARD</span><br>
        <span style='color: #E0E0E0; font-size: 16px; font-weight: bold;'><i>© Created by Shib Prasad Ghosh</i></span>
    </div>
    """, 
    unsafe_allow_html=True
)
