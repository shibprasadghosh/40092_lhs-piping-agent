import streamlit as st
import pandas as pd
import os
from datetime import datetime
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_experimental.agents import create_pandas_dataframe_agent

# পেজ কনফিগারেশন
st.set_page_config(page_title="LHS Project AI Agent", layout="wide")

# টাইটেল ও ওয়েলকাম মেসেজ
st.title("🤖 LHS Project - AI Data Assistant")
st.write("Welcome, Dear Project Team! 🚀 Your smart assistant for all LHS line nos., areas, joints, spools, and welding data. Feel free to ask anything in any language!")

# সাইডবার - প্রজেক্টের হাইলাইটস (ইংলিশে আপডেট করা)
st.sidebar.title("🛠️ Project LHS Info")
st.sidebar.write("This chat assistant helps you to:")
st.sidebar.info("- Check welding joint status")
st.sidebar.info("- Track area-wise work progress")
st.sidebar.info("- Find spool numbers & welder details")

# --- ভিজিটর লগ সেভ করার ফাংশন ---
def log_visitor(query_text):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"Time: {timestamp} | Query: {query_text}\n"
    with open("visitor_log.txt", "a", encoding="utf-8") as f:
        f.write(log_entry)

# ডেটাবেস ও এজেন্ট লোড 
@st.cache_resource
def load_agent():
    os.environ["GOOGLE_API_KEY"] = st.secrets["GOOGLE_API_KEY"]
    df = pd.read_excel("Merged_Master_Data_EXCEL_14Aug2026_114927_PM.xlsx", dtype=str)
    llm = ChatGoogleGenerativeAI(model="gemini-3.5-flash", temperature=0)
    
    prefix = "You are a helpful assistant for LHS piping projects. Always provide concise and accurate data from the dataframe."
    agent = create_pandas_dataframe_agent(llm, df, verbose=True, allow_dangerous_code=True, handle_parsing_errors=True, prefix=prefix)
    return agent

agent = load_agent()

# কুইক বাটন
st.subheader("Quick Search:")
col1, col2 = st.columns(2)
if col1.button("Show Area 1P25A1 Progress"):
    st.session_state.query = "Show me the status of joints in Area 1P25A1"
if col2.button("List all Welder No. 69 works"):
    st.session_state.query = "Find all rows where Welder No. is 69"

# চ্যাটবক্স
user_query = st.text_input("Enter your question here:", key="query")

if st.button("Search Database"):
    if user_query:
        # ভিজিটর লগ রেকর্ড করা হলো
        log_visitor(user_query)
        
        with st.spinner("Searching through LHS database... 🕵️‍♂️"):
            try:
                response = agent.invoke({"input": user_query + " You MUST start your final output exactly with the words 'Final Answer: '"})
                st.success("Result found!")
                # আউটপুট হ্যান্ডেলিং আরও স্মুথ করা হলো
                if isinstance(response, dict) and 'output' in response:
                    st.write(response['output'])
                else:
                    st.write(str(response))
            except Exception as e:
                # যদি কোনো টেকনিক্যাল এরর আসে, সেটার থেকেও ডেটা বের করে দেখানোর ব্যবস্থা
                st.success("Result found from database:")
                st.write(str(e).split("Final Answer:")[-1] if "Final Answer:" in str(e) else str(e))
    else:
        st.warning("Please enter a question first!")

# --- অ্যাডভান্সড ফিচার: কে কে ভিজিট করল বা সার্চ করল তার লগ দেখার অপশন ---
st.markdown("---")
if st.checkbox("📋 View Team Activity Log (Admin Only)"):
    if os.path.exists("visitor_log.txt"):
        st.write("Here is the history of queries searched by the team:")
        with open("visitor_log.txt", "r", encoding="utf-8") as f:
            log_contents = f.read()
        st.text_area("Activity Logs", log_contents, height=150)
    else:
        st.info("No activity logs found yet. Start searching to record logs!")
