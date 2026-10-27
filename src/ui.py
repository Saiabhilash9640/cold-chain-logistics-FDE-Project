import os
import sys
import uuid
import json
import urllib
from pathlib import Path
from dotenv import load_dotenv
import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text
from langchain_core.messages import HumanMessage, ToolMessage, SystemMessage

# ==========================================
# 1. IMMEDIATE PATH & ENVIRONMENT RESOLUTION
# ==========================================
script_dir = Path(__file__).resolve().parent  # points to src/
project_root = script_dir.parent              # climbs to project root

if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

load_dotenv(project_root / ".env")

prompt_path = project_root / "src" / "prompts" / "system_prompt.txt"

with open(prompt_path, "r", encoding="utf-8") as f:
    system_instructions = f.read()

system_prompt = SystemMessage(content=system_instructions)

# Import the compiled graph and tools list dynamically
from src.orchestrator import fde_agent

# ==========================================
# 2. SQL CREDENTIALS MAPPING FROM .ENV
# ==========================================
db_host = os.getenv("SQL_SERVER_HOST", "localhost")
db_port = os.getenv("SQL_SERVER_PORT", "1433")
db_user = os.getenv("SQL_AGENT_USER", "USR_FDE_RO")
db_password = os.getenv("SQL_AGENT_PASSWORD")

# Engine for the Agent to write logs using its standard credentials
connection_string = (
    f"DRIVER={{ODBC Driver 18 for SQL Server}};"
    f"SERVER={db_host},{db_port};"
    f"DATABASE=master;"
    f"UID={db_user};"
    f"PWD={db_password};"
    f"Encrypt=no;"
    f"TrustServerCertificate=yes;"
)

log_params = urllib.parse.quote_plus(connection_string)

log_engine = create_engine(f"mssql+pyodbc:///?odbc_connect={log_params}")

def write_audit_log(session_id, node_name, tool_name, content):
    """Silently writes agent execution traces to the SQL audit table using agent permissions."""
    try:
        with log_engine.connect() as conn:
            conn.execute(text("""
                INSERT INTO FDE_VIEWS.AgentAuditLog (SessionID, NodeExecuted, ToolName, Content)
                VALUES (:session_id, :node_name, :tool_name, :content)
            """), {
                "session_id": session_id,
                "node_name": node_name,
                "tool_name": tool_name,
                "content": content
            })
            conn.commit()
    except Exception as e:
        print(f"Audit Log Failed (Silent): {e}")

# ==========================================
# 3. PAGE CONFIGURATION & ENTERPRISE THEME
# ==========================================
st.set_page_config(
    page_title="FDE Supply Chain Dispatch Console",
    page_icon="🧊",
    layout="wide",
    initial_sidebar_state="expanded"
)



st.markdown("""
<style>

/* =========================================
   1. GLOBAL THEME
   ========================================= */
.stApp {
    background: linear-gradient(135deg, #0B1120 0%, #101827 55%, #0C1422 100%);
    color: #E5EDF7;
}

[data-testid="stHeader"] {
    background: rgba(11, 17, 32, 0.85);
}

.block-container {
    padding-top: 2rem;
    padding-bottom: 3rem;
    max-width: 1500px;
}

h1, h2, h3 {
    color: #F1F5F9 !important;
    letter-spacing: -0.4px;
}

h1 {
    font-weight: 750 !important;
}

p, label, .stMarkdown {
    color: #CBD5E1;
}

/* =========================================
   2. SIDEBAR
   ========================================= */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #111C30 0%, #0B1220 100%);
    border-right: 1px solid #26354D;
}

section[data-testid="stSidebar"] > div {
    padding-top: 1.5rem;
}

section[data-testid="stSidebar"] h1,
section[data-testid="stSidebar"] h2,
section[data-testid="stSidebar"] h3 {
    color: #F8FAFC !important;
}

section[data-testid="stSidebar"] [data-testid="stCaptionContainer"] {
    color: #94A3B8;
}

section[data-testid="stSidebar"] [role="radiogroup"] {
    gap: 0.45rem;
}

section[data-testid="stSidebar"] [role="radiogroup"] label {
    background: #172338;
    border: 1px solid #293950;
    border-radius: 10px;
    padding: 0.7rem 0.8rem;
    transition: all 0.2s ease;
}

section[data-testid="stSidebar"] [role="radiogroup"] label:hover {
    border-color: #2DD4BF;
    background: #1B3044;
}

/* =========================================
   3. BUTTONS
   ========================================= */
.stButton > button,
.stFormSubmitButton > button {
    background: linear-gradient(135deg, #0D9488, #0F766E);
    color: #FFFFFF !important;
    border: 1px solid #2DD4BF;
    border-radius: 10px;
    font-weight: 650;
    padding: 0.55rem 1rem;
    transition: all 0.2s ease;
}

.stButton > button:hover,
.stFormSubmitButton > button:hover {
    background: linear-gradient(135deg, #14B8A6, #0D9488);
    border-color: #5EEAD4;
    color: #FFFFFF !important;
    box-shadow: 0 4px 18px rgba(20, 184, 166, 0.18);
}

/* =========================================
   4. CHAT MESSAGES
   ========================================= */
[data-testid="stChatMessage"] {
    background: rgba(21, 32, 51, 0.92);
    border: 1px solid #293950;
    border-radius: 16px;
    padding: 1rem 1.1rem;
    margin-bottom: 0.9rem;
    box-shadow: 0 5px 18px rgba(0, 0, 0, 0.12);
}

[data-testid="stChatMessage"]:has(
    [data-testid="chatAvatarIcon-user"]
) {
    border-left: 3px solid #38BDF8;
}

[data-testid="stChatMessage"]:has(
    [data-testid="chatAvatarIcon-assistant"]
) {
    border-left: 3px solid #2DD4BF;
}

/* =========================================
   5. CHAT INPUT — LIGHT BACKGROUND
   ========================================= */

/* Outer chat input container */
[data-testid="stChatInput"] {
    background: #F8FAFC !important;
    border: 2px solid #14B8A6 !important;
    border-radius: 14px !important;
    box-shadow: 0 4px 18px rgba(0, 0, 0, 0.18);
    transition: border-color 0.2s ease, box-shadow 0.2s ease;
}

/* Focused chat input */
[data-testid="stChatInput"]:focus-within {
    background: #FFFFFF !important;
    border-color: #0D9488 !important;
    box-shadow: 0 0 0 3px rgba(20, 184, 166, 0.20);
}

/* Actual text area */
[data-testid="stChatInput"] textarea,
[data-testid="stChatInput"] textarea:focus {
    background: #F8FAFC !important;
    color: #172033 !important;
    -webkit-text-fill-color: #172033 !important;
    caret-color: #0D9488 !important;
    font-size: 16px !important;
    font-weight: 500 !important;
    opacity: 1 !important;
}

/* Placeholder text */
[data-testid="stChatInput"] textarea::placeholder {
    color: #64748B !important;
    -webkit-text-fill-color: #64748B !important;
    opacity: 1 !important;
}

/* Send button / icon */
[data-testid="stChatInput"] button {
    color: #0D9488 !important;
    background: transparent !important;
    border-radius: 9px !important;
}

[data-testid="stChatInput"] button:hover {
    color: #0F766E !important;
    background: #CCFBF1 !important;
}

/* =========================================
   6. CODE, JSON AND TOOL TRACES
   ========================================= */
.stMarkdown code {
    background: #1D2B40 !important;
    color: #67E8F9 !important;
    border: 1px solid #30445D;
    border-radius: 5px;
    padding: 0.15rem 0.35rem;
}

pre, code {
    font-variant-ligatures: none;
}

[data-testid="stCode"],
[data-testid="stJson"] {
    background: #0B1220;
    border: 1px solid #263850;
    border-radius: 10px;
}

[data-testid="stExpander"] {
    background: rgba(17, 28, 48, 0.7);
    border: 1px solid #30415A;
    border-radius: 12px;
    margin: 0.45rem 0;
}

[data-testid="stExpander"] summary {
    color: #DCE7F5;
    font-weight: 600;
}

[data-testid="stExpander"] summary:hover {
    color: #5EEAD4;
}

/* =========================================
   7. STATUS / PROGRESS PANEL
   ========================================= */
[data-testid="stStatusWidget"] {
    background: #111C30;
    border: 1px solid #2D425C;
    border-radius: 14px;
    padding: 0.35rem;
}

[data-testid="stStatusWidget"] summary {
    color: #A5F3FC;
    font-weight: 650;
}

/* =========================================
   8. TEXT INPUTS AND FORMS
   ========================================= */
.stTextInput input,
.stTextArea textarea,
.stSelectbox div[data-baseweb="select"] > div {
    background: #111C30;
    color: #F1F5F9;
    border-color: #33465F;
    border-radius: 9px;
}

.stTextInput input:focus,
.stTextArea textarea:focus {
    border-color: #2DD4BF;
    box-shadow: 0 0 0 1px #2DD4BF;
}

[data-testid="stForm"] {
    background: rgba(17, 28, 48, 0.75);
    border: 1px solid #293950;
    border-radius: 15px;
    padding: 1.25rem;
}

/* =========================================
   9. TABLES AND DATAFRAMES
   ========================================= */
[data-testid="stDataFrame"] {
    border: 1px solid #30415A;
    border-radius: 12px;
    overflow: hidden;
}

[data-testid="stTable"] {
    border: 1px solid #30415A;
    border-radius: 10px;
}

/* =========================================
   10. ALERTS AND DIVIDERS
   ========================================= */
[data-testid="stAlert"] {
    border-radius: 11px;
    border: 1px solid #33465F;
}

hr {
    border-color: #293950;
}

/* =========================================
   11. SCROLLBARS
   ========================================= */
::-webkit-scrollbar {
    width: 8px;
    height: 8px;
}

::-webkit-scrollbar-track {
    background: #0B1120;
}

::-webkit-scrollbar-thumb {
    background: #33465F;
    border-radius: 8px;
}

::-webkit-scrollbar-thumb:hover {
    background: #0D9488;
}

/* =========================================
   12. RESPONSIVE LAYOUT
   ========================================= */
@media (max-width: 768px) {
    .block-container {
        padding-top: 1rem;
        padding-left: 1rem;
        padding-right: 1rem;
    }

    [data-testid="stChatMessage"] {
        padding: 0.8rem;
        border-radius: 12px;
    }

    [data-testid="stChatInput"] textarea {
        font-size: 16px !important;
    }
}

</style>
""", unsafe_allow_html=True)



# ==========================================
# 4. MULTI-USER STATE & THREAD MANAGEMENT
# ==========================================
if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())

if "ui_messages" not in st.session_state:
    st.session_state.ui_messages = []

if "thread_initialized" not in st.session_state:
    st.session_state.thread_initialized = False

thread_config = {"configurable": {"thread_id": st.session_state.thread_id}}

# ==========================================
# 5. SIDEBAR NAVIGATION & METADATA
# ==========================================
with st.sidebar:
    st.image(str(script_dir / "image_L25X5q.png") if (script_dir / "image_L25X5q.png").exists() else "https://cdn-icons-png.flaticon.com/512/2830/2830305.png", width=65)
    st.title("FDE Command Center")
    
    app_mode = st.radio("System Mode", ["🧊 Dispatch Console", "🛡️ Security & Audit Logs"])
    
    st.markdown("---")
    st.caption(f"Session Token: `{st.session_state.thread_id[:8]}...`")
    st.markdown(f"**Reasoning Architecture:** `{os.getenv('Agent_llm', 'GROQ')}`")
    
    st.markdown("---")
    if st.button("🗑️ Purge Dispatch Workspace Session", use_container_width=True):
        st.session_state.ui_messages = []
        st.session_state.thread_id = str(uuid.uuid4())
        st.session_state.thread_initialized = False
        st.rerun()

# ==========================================
# 6. VIEW ROUTING (DISPATCH VS AUDIT)
# ==========================================

if app_mode == "🧊 Dispatch Console":
    # ------------------------------------------
    # TAB 1: CHAT UI & AGENT EXECUTION
    # ------------------------------------------
    st.title("Cold-Chain Incident Control Dashboard")
    st.caption("Production Data Engineering Pipeline • Real-Time Decision Optimization Platform")

    for entry in st.session_state.ui_messages:
        with st.chat_message(entry["role"], avatar="👤" if entry["role"] == "user" else "🤖"):
            if "traces" in entry:
                for trace in entry["traces"]:
                    if trace["type"] == "tool_input":
                        st.markdown(f"**⚡ Intent Recognized:** `{trace['name']}`")
                        with st.expander(f"📥 View Generated Input ({trace['name']})", expanded=False):
                            st.json(trace["args"])
                    elif trace["type"] == "tool_output":
                        with st.expander(f"📤 View Raw Output ({trace['name']})", expanded=False):
                            st.code(trace["content"], language="text")
            st.markdown(entry["content"])

    if user_input := st.chat_input("Query fleet telemetry, corridor updates, or compliance thresholds..."):
        
        st.session_state.ui_messages.append({"role": "user", "content": user_input})
        with st.chat_message("user", avatar="👤"):
            st.markdown(user_input)

        if not st.session_state.thread_initialized:
            st.session_state.thread_initialized = True
            input_messages = [
                system_prompt,
                HumanMessage(content=user_input)
            ]
        else:
            input_messages = [
                HumanMessage(content=user_input)
            ]

        with st.chat_message("assistant", avatar="🤖"):
            final_response = ""
            current_traces = [] 
            
            with st.status("🧠 Initializing Core Reasoner Node...", expanded=True) as status:
                events = fde_agent.stream(
                    {"messages": input_messages}, 
                    config=thread_config,
                    stream_mode="updates"
                )
                
                for event in events:
                    for node_name, node_state in event.items():
                        
                        if node_name == "reasoner":
                            latest_msg = node_state["messages"][-1]
                            
                            # A. Intercept Tool Call Requests (Inputs)
                            if hasattr(latest_msg, "tool_calls") and latest_msg.tool_calls:
                                status.update(label="🧠 Agent generated tool parameters...")
                                for tool_call in latest_msg.tool_calls:
                                    st.markdown(f"**⚡ Intent Recognized:** `{tool_call['name']}`")
                                    with st.expander(f"📥 View Generated Input ({tool_call['name']})", expanded=False):
                                        st.json(tool_call['args'])
                                    
                                    current_traces.append({
                                        "type": "tool_input",
                                        "name": tool_call['name'],
                                        "args": tool_call['args']
                                    })
                                    
                                    write_audit_log(
                                        session_id=st.session_state.thread_id,
                                        node_name="reasoner",
                                        tool_name=tool_call['name'],
                                        content=json.dumps(tool_call['args'])
                                    )
                            
                            # B. Intercept Final Generation
                            if latest_msg.content:
                                final_response = latest_msg.content
                                status.update(label="📝 Generating Operational Resolution Report...")
                                
                                write_audit_log(
                                    session_id=st.session_state.thread_id,
                                    node_name="reasoner_final",
                                    tool_name="LLM Text Synthesis",
                                    content=final_response
                                )
                                
                        elif node_name == "tools":
                            status.update(label="🔧 Executing Enterprise Subsystem Tools...")
                            for msg in node_state.get("messages", []):
                                if isinstance(msg, ToolMessage):
                                    with st.expander(f"📤 View Raw Output ({msg.name})", expanded=False):
                                        st.code(msg.content, language="text")
                                        
                                    current_traces.append({
                                        "type": "tool_output",
                                        "name": msg.name,
                                        "content": msg.content
                                    })
                                    
                                    write_audit_log(
                                        session_id=st.session_state.thread_id,
                                        node_name="tools",
                                        tool_name=msg.name,
                                        content=msg.content
                                    )
                
                status.update(label="Incident Matrix Evaluation Complete", state="complete", expanded=False)
                
            if final_response:
                st.markdown(final_response)
                st.session_state.ui_messages.append({
                    "role": "assistant",
                    "content": final_response,
                    "traces": current_traces
                })
            else:
                error_fallback = "⚠️ Execution Timeout: System engine encountered an unresolved processing edge case."
                st.error(error_fallback)


elif app_mode == "🛡️ Security & Audit Logs":
    # ------------------------------------------
    # TAB 2: AUDIT LOG VIEWER (REQUIRES ADMIN CREDENTIALS FROM .ENV OR INPUT)
    # ------------------------------------------
    st.title("🛡️ Enterprise Agent Audit Trail")
    st.caption("Secure database inspection of FDE_VIEWS.AgentAuditLog")
    
    st.markdown("### Database Authorization Gate")
    st.markdown("Enter high-privilege administrative credentials (defined in `.env` as `SQL_ADMIN_USER`) to query audit logs.")
    
    with st.form("admin_auth_form"):
        col1, col2 = st.columns(2)
        with col1:
            input_user = st.text_input("Admin Username", value=os.getenv("SQL_ADMIN_USER", ""))
        with col2:
            input_pass = st.text_input("Admin Password", type="password", value="")
            
        submit_admin = st.form_submit_button("Authenticate & Load Logs", use_container_width=True)

    if submit_admin:
        expected_admin_user = os.getenv("SQL_ADMIN_USER")
        expected_admin_pass = os.getenv("SQL_ADMIN_PASSWORD")
        
        if input_user == expected_admin_user and input_pass == expected_admin_pass:
            try:
                # Build an isolated admin connection string for viewing data
                admin_params = urllib.parse.quote_plus(
                    "DRIVER={ODBC Driver 18 for SQL Server};"
                    f"SERVER={db_host},{db_port};"
                    "DATABASE=master;"
                    f"UID={input_user};"
                    f"PWD={input_pass};"
                    "Encrypt=no;"
                    "TrustServerCertificate=yes;"
                )
                admin_engine = create_engine(f"mssql+pyodbc:///?odbc_connect={admin_params}")
                
                with admin_engine.connect() as conn:
                    query = """
                        SELECT LogID, Timestamp, SessionID, NodeExecuted, ToolName, Content 
                        FROM FDE_VIEWS.AgentAuditLog 
                        ORDER BY Timestamp DESC
                    """
                    df = pd.read_sql(query, conn)
                
                st.success("✅ Authenticated successfully as Admin.")
                
                if not df.empty:
                    st.dataframe(
                        df,
                        column_config={
                            "LogID": st.column_config.NumberColumn("ID", format="%d"),
                            "Timestamp": st.column_config.DatetimeColumn("Execution Time", format="DD/MM/YYYY-h:mm a"),
                            "SessionID": "Session Token",
                            "NodeExecuted": "Graph Node",
                            "ToolName": "Tool Triggered",
                            "Content": "Raw Payload Data"
                        },
                        hide_index=True,
                        use_container_width=True,
                        height=600
                    )
                else:
                    st.info("No audit logs found in the database. Run a query in the Dispatch Console first.")
                    
            except Exception as e:
                st.error(f"Database Query Failed: {e}")
        else:
            st.error("❌ Invalid Administrator Credentials.")