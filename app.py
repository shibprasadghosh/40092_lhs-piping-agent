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

st.set_page_config(page_title="LHS Project AI Agent", layout="wide")

# --- Set Indian Standard Time (IST) ---
IST = timezone(timedelta(hours=5, minutes=30))

# --- Google Sheets Connection ---
def get_gspread_client():
    try:
        creds_dict = st.secrets["gcp_service_account"]
        creds = Credentials.from_service_account_info(creds_dict, scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ])
        return gspread.authorize(creds)
    except:
        return None

# --- Auto-detect File ---
excel_files = glob.glob("*.xlsx")
file_name = max(excel_files, key=os.path.getmtime) if excel_files else None
last_updated = datetime.fromtimestamp(os.path.getmtime(file_name), IST).strftime("%d-%b-%Y at %I:%M %p") if file_name else "No File Found"

st.title("🤖 LHS Project - AI Data Assistant")
st.info(f"📅 **Database Last Updated On:** {last_updated}")

# --- Sidebar ---
st.sidebar.title("👤 User Authentication")
user_name = st.sidebar.text_input("Enter Your Name / Emp ID:")
st.sidebar.markdown("---")

if st.sidebar.button("📊 View Welding Progress"):
    st.session_state.show_progress = True

if 'show_progress' not in st.session_state:
    st.session_state.show_progress = False

# --- Data Loading ---
@st.cache_resource
def load_data(current_file):
    if not current_file: return pd.DataFrame()
    df = pd.read_excel(current_file, sheet_name="Master_Data", dtype=str)
    return df.apply(lambda x: x.str.strip().str.upper() if x.dtype == "object" else x)

df = load_data(file_name)

# --- Progress Dashboard Section ---
if st.session_state.show_progress:
    st.subheader("📈 Welding Progress Tracking")
    if not df.empty:
        # তোমার এক্সেল হেডার অনুযায়ী কলাম চেক
        def check_welding(row):
            # 'F&W REPORT' কলামটি চেক করছে
            val = str(row.get('F&W REPORT', '')).strip().upper()
            return val != '' and val != 'NAN' and val != 'NONE' and val != 'N/A'

        df['Welding_Done'] = df.apply(check_welding, axis=1)
        
        summary = df.groupby(['AREA', 'LINE NO.']).agg(
            Welding_Scope=('JOINT NO.', 'count'),
            Welding_Done=('Welding_Done', 'sum')
        ).reset_index()
        
        summary['Welding_%'] = ((summary['Welding_Done'] / summary['Welding_Scope']) * 100).round(1)
        st.dataframe(summary, use_container_width=True)
        
        if st.button("Close Progress Dashboard"):
            st.session_state.show_progress = False
            st.rerun()
    else:
        st.warning("No data found!")
else:
    # --- Main Search Logic ---
    st.subheader("🎯 Smart Dynamic Filters & AI Search")
    user_query = st.text_input("Ask about joint status, progress, or welder details:")
    
    if st.button("Search Database"):
        if not user_name.strip():
            st.error("⚠️ Please enter your Name / Emp ID!")
        else:
            # সার্চ ও লগিং লজিক (আগের মতোই)
            try:
                genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
                model = genai.GenerativeModel('gemini-1.5-flash')
                prompt = f"Analyze this dataframe: {df.head().to_string()}. Answer: {user_query}"
                response = model.generate_content(prompt)
                st.write(response.text)
                
                # Google Sheets Logging
                client = get_gspread_client()
                if client:
                    client.open("LHS_App_Logs").worksheet("Search_Logs").append_row([str(datetime.now(IST)), user_name, user_query])
            except Exception as e:
                st.error(f"Error: {e}")

st.markdown("<br><br><div style='text-align: right;'><i>© Created by Shib Prasad Ghosh</i></div>", unsafe_allow_html=True)
