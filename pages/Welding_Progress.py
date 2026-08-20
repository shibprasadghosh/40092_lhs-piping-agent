import streamlit as st
import pandas as pd
import glob
import os

st.set_page_config(page_title="Welding Progress", layout="wide")

st.title("📊 Welding Progress Dashboard")

# মেইন অ্যাপের ফাইলটাই এখানে লোড হচ্ছে
excel_files = glob.glob("*.xlsx")
if excel_files:
    file_name = max(excel_files, key=os.path.getmtime)
    df = pd.read_excel(file_name, sheet_name="Master_Data", dtype=str)
    df = df.apply(lambda x: x.str.strip().str.upper() if x.dtype == "object" else x)

    # ওয়েল্ডিং প্রোগ্রেস লজিক
    def check_welding(row):
        val = str(row.get('F&W REPORT', '')).strip().upper()
        return val != '' and val != 'NAN' and val != 'NONE' and val != 'N/A'

    df['Welding_Done'] = df.apply(check_welding, axis=1)
    
    summary = df.groupby(['AREA', 'LINE NO.']).agg(
        Welding_Scope=('JOINT NO.', 'count'),
        Welding_Done=('Welding_Done', 'sum')
    ).reset_index()
    
    summary['Welding_%'] = ((summary['Welding_Done'] / summary['Welding_Scope']) * 100).round(1)
    
    st.dataframe(summary, use_container_width=True)
else:
    st.warning("Data file not found!")
