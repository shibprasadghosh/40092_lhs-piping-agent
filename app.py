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
    st.session_state.ai_query_input = "" 

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
                    Do not include any markdown formatting in your response.
                    """
                    
                    for m_name in model_list:
                        try:
                            model = genai.GenerativeModel(m_name)
                            response = model.generate_content(prompt)
                            
                            # 100% Copy-Paste safe trick using chr(96) for backticks
                            bt = chr(96) * 3
                            code = response.text.replace(bt + "python", "").replace(bt, "").strip()
                            
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
        
        def safe_numeric(val):
            if pd.isna(val) or val == "":
                return val
            str_val = str(val).strip()
            if str_val.startswith('0') and len(str_val) > 1 and str_val[1] != '.':
                return val
            try:
                f_val = float(str_val)
                return int(f_val) if f_val.is_integer() else f_val
            except (ValueError, TypeError):
                return val

        file_time_str = datetime.now(IST).strftime('%Y%m%d_%I%M%S_%p')
        
        csv_df = add_watermark(display_df)
        csv = csv_df.to_csv(index=False).encode('utf-8')
        dl_col1.download_button(
            label="📄 Download as CSV",
            data=csv,
            file_name=f"LHS_Search_Result_{file_time_str}.csv",
            mime="text/csv"
        )
        
        try:
            excel_df = display_df.copy()
            for col in excel_df.columns:
                excel_df[col] = excel_df[col].apply(safe_numeric)
            
            excel_df = add_watermark(excel_df)
            
            excel_buffer = io.BytesIO()
            with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                excel_df.to_excel(writer, index=False, sheet_name='Search_Result')
            excel_data = excel_buffer.getvalue()
            
            dl_col2.download_button(
                label="📊 Download as Excel",
                data=excel_data,
                file_name=f"LHS_Search_Result_{file_time_str}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        except ModuleNotFoundError:
            dl_col2.warning("⚠️ Excel download requires 'openpyxl'. Please use CSV.")

st.markdown("---")

# --- 💡 User Suggestion & Feedback Box ---
with st.expander("💡 Give Feedback / Suggestion for Improvement"):
    st.write("We are constantly improving! Let us know what features you want next.")
    with st.form("feedback_form"):
        feedback_text = st.text_area("Your Suggestion / Feature Request:", placeholder="E.g. Please add a visual chart for weekly progress...")
        submit_feedback = st.form_submit_button("Submit Suggestion")
        
        if submit_feedback:
            if feedback_text.strip():
                log_time = datetime.now(IST).strftime("%Y-%m-%d %I:%M:%S %p")
                uname = user_name.strip() if user_name.strip() else "Anonymous User"
                with open("suggestions_log.txt", "a", encoding="utf-8") as sf:
                    sf.write(f"[{log_time}] {uname}: {feedback_text.strip()}\n")
                st.success("Thank you! Your suggestion has been successfully recorded. 🙏")
            else:
                st.warning("Please write something before submitting.")

st.markdown("---")

# --- 📋 Admin Panel (Logs & Suggestions Download) ---
if st.checkbox("⚙️ View Admin Panel (Logs & Suggestions)"):
    tab1, tab2 = st.tabs(["📊 User Search Logs", "📝 Suggestions Received"])
    
    with tab1:
        if os.path.exists("visitor_log.csv"):
            log_df = pd.read_csv("visitor_log.csv")
            st.dataframe(log_df, use_container_width=True)
            
            try:
                log_buffer = io.BytesIO()
                with pd.ExcelWriter(log_buffer, engine='openpyxl') as writer:
                    log_df.to_excel(writer, index=False, sheet_name='Search_Logs')
                st.download_button(
                    label="📥 Download Search Logs as Excel",
                    data=log_buffer.getvalue(),
                    file_name=f"LHS_Visitor_Logs_{datetime.now(IST).strftime('%Y%m%d')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            except Exception as e:
                st.error("Error generating Excel log file.")
        else:
            st.info("No search logs available yet.")
            
    with tab2:
        if os.path.exists("suggestions_log.txt"):
            with open("suggestions_log.txt", "r", encoding="utf-8") as sf:
                st.text_area("All Suggestions", sf.read(), height=250)
        else:
            st.info("No suggestions received yet.")

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
