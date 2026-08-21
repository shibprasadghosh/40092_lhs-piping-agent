import streamlit as st
import pandas as pd
import os
import io
import csv
import glob
from datetime import datetime, timezone, timedelta
import google.generativeai as genai
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="LHS Project AI Agent", layout="wide", initial_sidebar_state="expanded")

# --- Set Indian Standard Time (IST) ---
IST = timezone(timedelta(hours=5, minutes=30))

# --- Session State for Authentication ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'user_name' not in st.session_state:
    st.session_state.user_name = ""

def handle_login():
    if st.session_state.auth_input.strip():
        st.session_state.user_name = st.session_state.auth_input.strip()
        st.session_state.logged_in = True

# --- Google Sheets Connection ---
def get_gspread_client():
    try:
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        creds_dict = st.secrets["gcp_service_account"]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        client = gspread.authorize(creds)
        return client
    except Exception as e:
        return None

# --- ULTRA-FLEXIBLE AUTO-DETECT EXCEL FILE ---
excel_files = glob.glob("*.xlsx")

if excel_files:
    file_name = max(excel_files, key=os.path.getmtime)
    try:
        if "Merged_Master_Data_EXCEL_" in file_name:
            parts = file_name.replace(".xlsx", "").split("_")
            date_part = parts[4] 
            time_part = parts[5] 
            ampm_part = parts[6] 
            formatted_date = f"{date_part[:2]}-{date_part[2:5]}-{date_part[5:]}"
            formatted_time = f"{time_part[:2]}:{time_part[2:4]} {ampm_part}"
            last_updated = f"{formatted_date} at {formatted_time}"
        else:
            mod_time = os.path.getmtime(file_name)
            last_updated = datetime.fromtimestamp(mod_time, IST).strftime("%d-%b-%Y at %I:%M %p")
    except Exception:
        mod_time = os.path.getmtime(file_name)
        last_updated = datetime.fromtimestamp(mod_time, IST).strftime("%d-%b-%Y at %I:%M %p")
else:
    file_name = None
    last_updated = "No Data File Found! Please upload an Excel file."

# ==========================================
# --- HEADER & GLOBAL STYLES ---
# ==========================================

db_update_html = ""
if st.session_state.logged_in:
    db_update_html = f"<div style='background-color: rgba(43, 123, 203, 0.15); padding: 12px 20px; border-radius: 8px; color: #8bbdff; font-family: sans-serif; font-size: 16px; border: 1px solid rgba(43, 123, 203, 0.3); margin-top: 15px;'>📅 <b>Database Last Updated On:</b> {last_updated}</div>"

sticky_header_html = f"""
<div id="my-frozen-header">
    <h1 style="color: white; margin: 0; padding-bottom: 15px; font-size: 36px;">🤖 LHS Project - AI Data Assistant</h1>
    <div style="background: linear-gradient(135deg, #0f2027, #203a43, #2c5364); padding: 22px; border-radius: 12px; border-left: 6px solid #00d2ff; margin: 0; box-shadow: 0 4px 6px rgba(0,0,0,0.3);">
        <h2 style="color: #00d2ff; margin: 0; padding-bottom: 8px; font-size: 26px; font-weight: bold; text-shadow: 1px 1px 2px rgba(0,0,0,0.8);">👋 Welcome, Dear Project Team! 🚀</h2>
        <p style="color: #e0e0e0; font-size: 22px; font-weight: 500; margin: 0; line-height: 1.6;">Experience the next-generation <b>AI Data Portal</b> for advanced filtering, seamless line tracing, and smart piping insights.</p>
    </div>
    {db_update_html}
</div>

<style>
.block-container {{ padding-top: 1rem !important; }}
div.element-container:has(#my-frozen-header) {{
    position: -webkit-sticky;
    position: sticky;
    top: 2.875rem; 
    z-index: 999999;
    background-color: #0e1117; 
    padding-bottom: 15px;
    border-bottom: 2px solid #2c333f;
    margin-bottom: 15px;
}}
/* Custom Styling for Primary Buttons */
button[kind="primary"] {{
    background: linear-gradient(135deg, #1e3c72, #2a5298) !important;
    color: white !important;
    border: 1px solid #58a6ff !important;
    font-size: 18px !important;
    font-weight: bold !important;
    padding: 10px 24px !important;
    border-radius: 8px !important;
}}
button[kind="primary"]:hover {{
    background: linear-gradient(135deg, #2a5298, #1e3c72) !important;
    border: 1px solid #00d2ff !important;
    box-shadow: 0 4px 8px rgba(0, 210, 255, 0.3) !important;
}}
</style>
"""
st.markdown(sticky_header_html, unsafe_allow_html=True)


# ==========================================
# --- GATEKEEPER / AUTHENTICATION LOGIC ---
# ==========================================
if not st.session_state.logged_in:
    st.markdown("### 🔒 Dashboard is Locked")
    st.warning("Please enter your Name or Emp ID below and press **'Enter'** to unlock the dashboard.")
    
    col_auth1, col_auth2 = st.columns([1, 2])
    with col_auth1:
        st.text_input("Enter Your Name / Emp ID:", key="auth_input", on_change=handle_login, placeholder="E.g. Shib Prasad Ghosh")
    with col_auth2:
        st.markdown("<div style='margin-top: 35px; color: gray; font-size: 14px;'>⚠️ Your ID is securely logged for tracking database queries.</div>", unsafe_allow_html=True)

else:
    # ==========================================
    # --- MAIN APP (UNLOCKED) ---
    # ==========================================
    
    st.sidebar.title("🗂️ MAIN MENU")
    st.sidebar.success(f"👤 Logged in as: **{st.session_state.user_name}**")
    st.sidebar.markdown("---")
    
    menu_selection = st.sidebar.radio(
        "Choose a Dashboard:",
        ("🎯 Smart Search & Filters", "📊 Welding Progress Tracking")
    )
    st.sidebar.markdown("---")
    st.sidebar.caption("© Created by Shib Prasad Ghosh")

    @st.cache_resource
    def load_data_and_models(current_file):
        if not current_file:
            return pd.DataFrame(), []
        genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
        df = pd.read_excel(current_file, sheet_name="Master_Data", dtype=str)
        df = df.apply(lambda x: x.str.strip().str.upper() if x.dtype == "object" else x)
        df = df.replace({'NAN': '', 'NAT': ''})
        
        def format_date_dd_mm_yyyy(val):
            if pd.isna(val) or str(val).strip().upper() in ['NAN', 'NAT', '', 'NONE']:
                return ''
            try:
                dt_obj = pd.to_datetime(str(val).split(' ')[0])
                return dt_obj.strftime('%d-%m-%Y')
            except:
                return str(val).split(' ')[0]

        for col in df.columns:
            if 'DATE' in col.upper():
                df[col] = df[col].apply(format_date_dd_mm_yyyy)
        
        available_models = []
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods and 'tts' not in m.name and 'audio' not in m.name:
                available_models.append(m.name)
                
        return df, available_models

    df, model_list = load_data_and_models(file_name)

    def log_visitor(name, query_text):
        timestamp = datetime.now(IST).strftime("%Y-%m-%d %I:%M:%S %p")
        file_exists = os.path.isfile("visitor_log.csv")
        with open("visitor_log.csv", "a", newline='', encoding="utf-8") as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(["Date & Time", "User Name", "Search Query"])
            writer.writerow([timestamp, name, query_text])
        try:
            client = get_gspread_client()
            if client:
                sheet = client.open("LHS_App_Logs").worksheet("Search_Logs")
                sheet.append_row([timestamp, name, query_text])
        except Exception:
            pass 

    def prep_display_df(d_frame):
        display_df = d_frame.copy()
        drop_cols = [c for c in display_df.columns if c.strip().upper() in ['SL. NO.', 'SL NO.', 'SL NO', 'SR NO', 'SR. NO.', 'SL.NO', 'SL. NO', 'SL.NO.']]
        display_df = display_df.drop(columns=drop_cols, errors='ignore')
        display_df.insert(0, 'Sl. No.', range(1, len(display_df) + 1))
        return display_df

    # ==========================================
    # --- MENU 1: WELDING PROGRESS TRACKING ---
    # ==========================================
    if menu_selection == "📊 Welding Progress Tracking":
        if 'wp_filter_ids' not in st.session_state:
            st.session_state.wp_filter_ids = []
        if 'wp_next_id' not in st.session_state:
            st.session_state.wp_next_id = 0
        if 'wp_search_result_df' not in st.session_state:
            st.session_state.wp_search_result_df = None
        if 'wp_success_msg' not in st.session_state:
            st.session_state.wp_success_msg = ""

        def wp_add_filter_row():
            st.session_state.wp_filter_ids.append(st.session_state.wp_next_id)
            st.session_state.wp_next_id += 1

        def wp_remove_filter_row(fid):
            st.session_state.wp_filter_ids.remove(fid)

        def wp_reset_dashboard():
            st.session_state.wp_filter_ids = []
            st.session_state.wp_next_id = 0
            st.session_state.wp_search_result_df = None
            st.session_state.wp_success_msg = ""
            if 'wp_ai_query_input' in st.session_state:
                st.session_state.wp_ai_query_input = "" 

        st.subheader("📊 Welding Progress & Analytics")
        # Enalrged Instruction
        st.markdown("<div style='font-size: 18px; color: #e0e0e0; margin-bottom: 15px;'>Use smart filters or Ask AI to generate a precise visual progress chart based on <b>Inch Dia (ID)</b>.</div>", unsafe_allow_html=True)

        col_f_title, col_f_btn = st.columns([4, 1])
        with col_f_title:
            # Enlarged Instruction
            st.markdown("<div style='font-size: 18px; font-weight: bold; color: #58a6ff;'>➕ Click '+' to add filter fields dynamically!</div>", unsafe_allow_html=True)
        with col_f_btn:
            st.button("🔄 Reset / Refresh", on_click=wp_reset_dashboard, key="wp_reset")

        wp_active_conditions = []
        wp_progressive_df = df.copy() if not df.empty else pd.DataFrame()

        if not df.empty:
            for i, fid in enumerate(st.session_state.wp_filter_ids):
                col1, col2, col3 = st.columns([4, 4, 1])
                chosen_col = col1.selectbox(f"Filter Field {i+1}", ["(Select a Column)"] + list(df.columns), key=f"wp_col_{fid}")
                if chosen_col != "(Select a Column)":
                    raw_vals = [str(val).strip() for val in wp_progressive_df[chosen_col].unique() if str(val).strip() != '']
                    unique_vals = ["(Select a Value)"] + sorted(list(set(raw_vals)))
                    chosen_val = col2.selectbox(f"Value for {chosen_col}", unique_vals, key=f"wp_val_{fid}")
                    if chosen_val != "(Select a Value)":
                        wp_active_conditions.append(f"`{chosen_col}` == '{chosen_val}'")
                        wp_progressive_df = wp_progressive_df[wp_progressive_df[chosen_col].astype(str).str.strip() == chosen_val]
                
                with col3:
                    st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
                    st.button("❌", key=f"wp_del_{fid}", on_click=wp_remove_filter_row, args=(fid,), help="Remove this filter")

        st.button("➕ Add Another Filter Field", on_click=wp_add_filter_row, key="wp_add")

        st.markdown("---")
        
        # Enlarged Instruction for AI input
        st.markdown("<h3 style='margin-bottom: 5px; color: #ffffff;'>💬 Or Ask AI (Custom Question):</h3>", unsafe_allow_html=True)
        st.markdown("<div style='font-size: 18px; color: #e0e0e0; margin-bottom: 10px;'>Enter your question here in your preferred language <b>(Leave blank if using filters above)</b>:</div>", unsafe_allow_html=True)
        
        wp_user_query = st.text_input("Hidden Label", key="wp_ai_query_input", label_visibility="collapsed")

        # Colorized Primary Button
        if st.button("🚀 Calculate Progress & Search", type="primary"):
            if df.empty:
                st.error("⚠️ No data file found. Please upload the Excel dataset first.")
            else:
                active_query = wp_user_query.strip()
                log_entry = active_query if active_query else f"[Welding Progress Filters: {', '.join(wp_active_conditions)}]"
                
                if wp_active_conditions:
                    auto_query = "Find all rows where " + " and ".join(wp_active_conditions) + ". Show all columns."
                    active_query = auto_query + " Furthermore, apply this condition: " + active_query if active_query else auto_query

                if active_query:
                    if not wp_user_query.strip() and wp_active_conditions:
                        st.session_state.wp_search_result_df = wp_progressive_df
                        st.session_state.wp_success_msg = "✅ Success! (Filtered from Data)"
                        log_visitor(st.session_state.user_name.strip(), log_entry)
                    else:
                        if not model_list:
                            st.error("Error: No valid text models found for this API Key.")
                        else:
                            log_visitor(st.session_state.user_name.strip(), log_entry)
                            with st.spinner("Analyzing data for progress report... 🕵️‍♂️"):
                                success = False
                                final_res = None
                                successful_model = ""
                                
                                smart_models = [m for m in model_list if 'pro' in m.lower()] + [m for m in model_list if 'flash' in m.lower() and 'lite' not in m.lower()]
                                smart_models = smart_models if smart_models else model_list
                                ordered_models = list(dict.fromkeys(smart_models))
                                
                                prompt = f"""
                                You are an expert data analyst working with a Pandas DataFrame named `df`.
                                The columns of the dataframe are: {list(df.columns)}
                                
                                CRITICAL RULES FOR SEARCHING:
                                1. Output formatting: Add a new column named 'Sl. No.' with dynamic serial numbers starting from 1.
                                2. EXACT vs PARTIAL MATCHING: 
                                   - For IDs/Numbers (like Line No, Joint No, Area), use EXACT matching: `df[df['column_name'].astype(str).str.strip().str.upper() == 'VAL']`
                                   - For Names, Contractors, Agencies, or text substrings (like 'PECO'), you MUST use `.str.contains('VAL', case=False, na=False)` to allow partial text matches!
                                
                                User requested: "{active_query}"
                                
                                Write ONLY executable Python code using pandas. Store the final result in a variable named `result`.
                                """
                                
                                for m_name in ordered_models:
                                    try:
                                        model = genai.GenerativeModel(m_name)
                                        response = model.generate_content(prompt)
                                        bt = chr(96) * 3
                                        code = response.text.replace(bt + "python", "").replace(bt, "").strip()
                                        local_vars = {"df": df, "pd": pd}
                                        exec(code, {}, local_vars)
                                        final_res = local_vars.get("result", None)
                                        successful_model = m_name
                                        success = True
                                        break 
                                    except Exception:
                                        continue 
                                
                                if success and isinstance(final_res, pd.DataFrame):
                                    st.session_state.wp_search_result_df = final_res
                                    st.session_state.wp_success_msg = f"✅ Success! (Powered by {successful_model})"
                                else:
                                    st.session_state.wp_search_result_df = None
                                    st.session_state.wp_success_msg = ""
                                    st.error("❌ No matching data found or API error.")
                else:
                    st.warning("Please enter a question or select at least one filter first to calculate progress!")

        if st.session_state.wp_search_result_df is not None:
            res_df = st.session_state.wp_search_result_df
            if res_df.empty:
                st.warning("⚠️ No matching data found! Please try different filters.")
            else:
                st.success(st.session_state.wp_success_msg)
                
                chart_df = res_df.copy()
                
                fw_col = next((c for c in chart_df.columns if 'F&W REPORT' in c.upper()), None)
                if fw_col:
                    chart_df['W_Flag'] = chart_df[fw_col].apply(lambda val: str(val).strip().upper() not in ['', 'NAN', 'NONE', 'N/A'])
                else:
                    chart_df['W_Flag'] = False
                
                dia_col = next((c for c in chart_df.columns if 'DIA' in c.upper()), None)
                if dia_col:
                    chart_df['Dia_Numeric'] = pd.to_numeric(chart_df[dia_col], errors='coerce').fillna(0)
                else:
                    chart_df['Dia_Numeric'] = 0
                
                # Exact calculation without rounding
                total_joints = len(chart_df)
                total_id = chart_df['Dia_Numeric'].sum()
                
                done_joints = chart_df['W_Flag'].sum()
                done_id = chart_df.loc[chart_df['W_Flag'] == True, 'Dia_Numeric'].sum()
                
                pending_joints = total_joints - done_joints
                pending_id = total_id - done_id
                
                progress_pct = int((done_id / total_id) * 100) if total_id > 0 else 0
                deg = int((progress_pct / 100) * 360)
                
                css_donut_html = f"""
                <div style="display: flex; flex-wrap: wrap; gap: 30px; align-items: center; background-color: #161b22; padding: 25px; border-radius: 12px; border: 1px solid #30363d; margin-top: 20px; margin-bottom: 25px;">
                    <div style="width: 160px; height: 160px; border-radius: 50%; background: conic-gradient(#28a745 {deg}deg, #dc3545 0deg); display: flex; justify-content: center; align-items: center; box-shadow: 0 4px 10px rgba(0,0,0,0.4);">
                        <div style="width: 115px; height: 115px; border-radius: 50%; background-color: #161b22; display: flex; justify-content: center; align-items: center;">
                            <h2 style="color: white; margin: 0; font-size: 28px;">{progress_pct}%</h2>
                        </div>
                    </div>
                    <div>
                        <h3 style="margin-top: 0; color: #58a6ff; font-size: 24px;">Welding Progress (Inch Dia Basis)</h3>
                        <div style="font-size: 18px; color: #c9d1d9; margin-bottom: 8px;">🟢 <span style="display:inline-block; width: 120px;"><b>Completed:</b></span> {done_joints} Joints ({done_id:.3f} ID)</div>
                        <div style="font-size: 18px; color: #c9d1d9; margin-bottom: 8px;">🔴 <span style="display:inline-block; width: 120px;"><b>Pending:</b></span> {pending_joints} Joints ({pending_id:.3f} ID)</div>
                        <div style="font-size: 18px; color: #ffffff; margin-top: 12px; border-top: 1px solid #30363d; padding-top: 12px;">📐 <span style="display:inline-block; width: 120px;"><b>Total Scope:</b></span> <b>{total_joints} Joints ({total_id:.3f} ID)</b></div>
                    </div>
                </div>
                """
                st.markdown(css_donut_html, unsafe_allow_html=True)
                
                st.markdown("### 📋 Filtered Joint List")
                hide_empty = st.checkbox("👁️ Hide empty columns", value=True, key="wp_hide_col")
                
                display_df = prep_display_df(res_df)
                
                if hide_empty:
                    display_df = display_df.replace(['None', 'none', 'NAN', 'nan', ''], pd.NA).dropna(axis=1, how='all').fillna('')
                st.dataframe(display_df, hide_index=True, use_container_width=False)


    # ==========================================
    # --- MENU 2: SMART SEARCH & FILTERS ---
    # ==========================================
    elif menu_selection == "🎯 Smart Search & Filters":
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
            if 'ai_query_input' in st.session_state:
                st.session_state.ai_query_input = "" 

        st.subheader("🎯 Smart Dynamic Filters:")
        
        col_f_title, col_f_btn = st.columns([4, 1])
        with col_f_title:
            # Enlarged Instruction
            st.markdown("<div style='font-size: 18px; font-weight: bold; color: #58a6ff;'>➕ Click '+' to add filter fields. Options will dynamically update based on your selections!</div>", unsafe_allow_html=True)
        with col_f_btn:
            st.button("🔄 Reset / Refresh", on_click=reset_dashboard, help="Clear all filters and search results")

        active_conditions = []
        progressive_df = df.copy() if not df.empty else pd.DataFrame()

        if not df.empty:
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

        # Enlarged Instruction for AI input
        st.markdown("<h3 style='margin-bottom: 5px; color: #ffffff;'>💬 Or Ask AI (Custom Question):</h3>", unsafe_allow_html=True)
        st.markdown("<div style='font-size: 18px; color: #e0e0e0; margin-bottom: 10px;'>Enter your question here in your preferred language <b>(Leave blank if using filters above)</b>:</div>", unsafe_allow_html=True)
        
        user_query = st.text_input("Hidden Label", key="ai_query_input", label_visibility="collapsed")

        # Colorized Primary Button
        if st.button("🔍 Search Database", type="primary"):
            if df.empty:
                st.error("⚠️ No data file found. Please upload the Excel dataset first.")
            else:
                actual_user_typing = user_query.strip()
                log_entry = actual_user_typing if actual_user_typing else f"[Used Filters: {', '.join(active_conditions)}]"
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
                        log_visitor(st.session_state.user_name.strip(), log_entry)
                        with st.spinner("Bypassing restrictions & searching database... 🕵️‍♂️"):
                            success = False
                            final_res = None
                            successful_model = ""
                            
                            smart_models = [m for m in model_list if 'pro' in m.lower()] + [m for m in model_list if 'flash' in m.lower() and 'lite' not in m.lower()]
                            smart_models = smart_models if smart_models else model_list
                            ordered_models = list(dict.fromkeys(smart_models))
                            
                            prompt = f"""
                            You are an expert data analyst working with a Pandas DataFrame named `df`.
                            The columns of the dataframe are: {list(df.columns)}
                            
                            CRITICAL RULES FOR SEARCHING:
                            1. Output formatting: Add a new column named 'Sl. No.' with dynamic serial numbers starting from 1. Do NOT include original dataframe index.
                            2. EXACT vs PARTIAL MATCHING: 
                               - For IDs/Numbers (like Line No, Joint No, Area), use EXACT matching: `df[df['column_name'].astype(str).str.strip().str.upper() == 'VAL']`
                               - For Names, Contractors, Agencies, or text substrings (like 'PECO'), you MUST use `.str.contains('VAL', case=False, na=False)` to allow partial text matches!
                            3. Identify the most logical column name based on context.
                            
                            User requested: "{active_query}"
                            
                            Write ONLY executable Python code using pandas. Store the final result in a variable named `result`. Do not include any markdown formatting like python in your response.
                            """
                            
                            for m_name in ordered_models:
                                try:
                                    model = genai.GenerativeModel(m_name)
                                    response = model.generate_content(prompt)
                                    bt = chr(96) * 3
                                    code = response.text.replace(bt + "python", "").replace(bt, "").strip()
                                    local_vars = {"df": df, "pd": pd}
                                    exec(code, {}, local_vars)
                                    final_res = local_vars.get("result", "No result variable found.")
                                    successful_model = m_name
                                    success = True
                                    break 
                                except Exception as e:
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
                
                display_df = prep_display_df(res_df)
                
                if hide_empty:
                    display_df = display_df.replace(['None', 'none', 'NAN', 'nan', ''], pd.NA).dropna(axis=1, how='all').fillna('')
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

    # --- FOOTER & ADMIN PANEL ---
    st.markdown("---")
    with st.expander("💡 Give Feedback / Suggestion for Improvement"):
        st.write("We are constantly improving! Let us know what features you want next.")
        with st.form("feedback_form"):
            feedback_text = st.text_area("Your Suggestion / Feature Request:", placeholder="E.g. Please add a visual chart for weekly progress...")
            submit_feedback = st.form_submit_button("Submit Suggestion")
            if submit_feedback:
                if feedback_text.strip():
                    log_time = datetime.now(IST).strftime("%Y-%m-%d %I:%M:%S %p")
                    uname = st.session_state.user_name.strip()
                    with open("suggestions_log.txt", "a", encoding="utf-8") as sf:
                        sf.write(f"[{log_time}] {uname}: {feedback_text.strip()}\n")
                    try:
                        client = get_gspread_client()
                        if client:
                            sheet = client.open("LHS_App_Logs").worksheet("Suggestions")
                            sheet.append_row([log_time, uname, feedback_text.strip()])
                    except Exception:
                        pass
                    st.success("Thank you! Your suggestion has been successfully recorded. 🙏")
                else:
                    st.warning("Please write something before submitting.")

    st.markdown("---")
    if st.checkbox("⚙️ View Admin Panel (Logs & Suggestions)"):
        tab1, tab2 = st.tabs(["📊 User Search Logs", "📝 Suggestions Received"])
        with tab1:
            if os.path.exists("visitor_log.csv"):
                log_df = pd.read_csv("visitor_log.csv")
                st.dataframe(log_df, use_container_width=True)
            else:
                st.info("No search logs available yet locally.")
        with tab2:
            if os.path.exists("suggestions_log.txt"):
                with open("suggestions_log.txt", "r", encoding="utf-8") as sf:
                    st.text_area("All Suggestions", sf.read(), height=250)
            else:
                st.info("No suggestions received yet locally.")

# Watermark / Credit
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
