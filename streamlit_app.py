import json
import hashlib
import os
import secrets
import sqlite3
from urllib import request

import dotenv
import streamlit as st

dotenv.load_dotenv(override=True)

st.set_page_config(
    page_title="Support OS | Ticket Intelligence",
    page_icon="S",
    layout="wide",
    initial_sidebar_state="expanded",
)

DB_PATH = os.path.join(os.path.dirname(__file__), "support_tickets.db")


def hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 120_000)
    return f"{salt.hex()}${digest.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        salt_hex, digest_hex = stored_hash.split("$", 1)
        expected = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), 120_000)
        return secrets.compare_digest(expected.hex(), digest_hex)
    except (ValueError, TypeError):
        return False


def database_connection():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_auth_database():
    with database_connection() as connection:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS tickets (id INTEGER PRIMARY KEY AUTOINCREMENT, ticket_id TEXT UNIQUE NOT NULL, customer_name TEXT NOT NULL, customer_email TEXT NOT NULL, subject TEXT NOT NULL, description TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'Open', priority TEXT NOT NULL DEFAULT 'Medium', category TEXT NOT NULL DEFAULT 'General', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, owner_username TEXT NOT NULL DEFAULT 'admin')"
        )
        connection.execute(
            "CREATE TABLE IF NOT EXISTS notes (id INTEGER PRIMARY KEY AUTOINCREMENT, ticket_id TEXT NOT NULL, note_text TEXT NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
        )
        connection.execute(
            "CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, email TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'user')"
        )
        connection.execute(
            "CREATE TABLE IF NOT EXISTS replies (id INTEGER PRIMARY KEY AUTOINCREMENT, ticket_id TEXT NOT NULL, reply_text TEXT NOT NULL, sent_to_email INTEGER NOT NULL DEFAULT 0, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
        )
        ticket_columns = {row[1] for row in connection.execute("PRAGMA table_info(tickets)")}
        if "owner_username" not in ticket_columns:
            connection.execute("ALTER TABLE tickets ADD COLUMN owner_username TEXT NOT NULL DEFAULT 'admin'")
        admin = connection.execute("SELECT username FROM users WHERE username = 'admin'").fetchone()
        if admin is None:
            connection.execute(
                "INSERT INTO users (username, email, password_hash, role) VALUES (?, ?, ?, ?)",
                ("admin", "admin@support.local", hash_password("password123"), "admin"),
            )
        connection.execute("UPDATE tickets SET owner_username = 'admin' WHERE owner_username IS NULL OR owner_username = ''")
        if connection.execute("SELECT COUNT(*) FROM tickets").fetchone()[0] == 0:
            connection.executemany(
                "INSERT INTO tickets (ticket_id, customer_name, customer_email, subject, description, status, priority, category, owner_username) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    ("TKT-9557", "Alex Morgan", "alex@example.com", "Critical payment outage", "The billing API is down and broken. Unable to update billing details.", "Closed", "Urgent", "Billing", "admin"),
                    ("TKT-7965", "Alex Morgan", "alex@example.com", "Critical payment outage", "The billing API is down and broken", "Open", "Urgent", "Billing", "admin"),
                    ("TKT-7948", "Tejas Kamble", "tejas@example.com", "unable to bill", "Getting payment process errors during checkout.", "Open", "Medium", "General", "admin"),
                ],
            )


def authenticate_user(username: str, password: str):
    with database_connection() as connection:
        user = connection.execute("SELECT * FROM users WHERE username = ?", (username.strip().lower(),)).fetchone()
    if user and verify_password(password, user["password_hash"]):
        return dict(user)
    return None


def register_user(username: str, email: str, password: str):
    username = username.strip().lower()
    email = email.strip().lower()
    if len(username) < 3 or len(password) < 8:
        return "Username must have 3+ characters and password must have 8+ characters."
    try:
        with database_connection() as connection:
            connection.execute(
                "INSERT INTO users (username, email, password_hash, role) VALUES (?, ?, ?, 'user')",
                (username, email, hash_password(password)),
            )
        return None
    except sqlite3.IntegrityError:
        return "That username or email is already registered."


def load_tickets(username: str, role: str):
    query = "SELECT * FROM tickets" if role == "admin" else "SELECT * FROM tickets WHERE owner_username = ?"
    params = () if role == "admin" else (username,)
    with database_connection() as connection:
        rows = connection.execute(query, params).fetchall()
        tickets = []
        for row in rows:
            notes = connection.execute("SELECT note_text FROM notes WHERE ticket_id = ? ORDER BY created_at DESC", (row["ticket_id"],)).fetchall()
            replies = connection.execute("SELECT reply_text, sent_to_email, created_at FROM replies WHERE ticket_id = ? ORDER BY created_at DESC", (row["ticket_id"],)).fetchall()
            tickets.append({"id":row["ticket_id"],"customer":row["customer_name"],"email":row["customer_email"],"subject":row["subject"],"description":row["description"],"status":row["status"],"priority":row["priority"],"category":row["category"],"notes":[note["note_text"] for note in notes],"replies":[{"text":reply["reply_text"],"emailed":bool(reply["sent_to_email"]),"time":reply["created_at"]} for reply in replies]})
    return tickets


initialize_auth_database()

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Space+Grotesk:wght@500;600;700&display=swap');
    :root { --ink:#273044; --muted:#697386; --glass:rgba(255,255,255,.68); --line:rgba(255,255,255,.72); --violet:#7767e8; --coral:#ed7e6b; }
    .stApp { background: linear-gradient(135deg, #fdf6f0 0%, #f3e8ff 50%, #fff5e6 100%); color: var(--ink); font-family: 'DM Sans', sans-serif; }
    @keyframes floatUp { 0% { transform: translateY(0) scale(1); opacity: 0.7; } 50% { transform: translateY(-18px) scale(1.08); opacity: 1; } 100% { transform: translateY(0) scale(1); opacity: 0.7; } }
    .float-shape { position: absolute; border-radius: 50%; filter: blur(2px); animation: floatUp 6s ease-in-out infinite; pointer-events: none; z-index: 0; }
    .float-shape:nth-child(2) { animation-delay: 2s; animation-duration: 7s; }
    [data-testid='stHeader'] { background:transparent; }
    [data-testid='stSidebar'] { background:rgba(255,255,255,.48); border-right:1px solid var(--line); backdrop-filter:blur(18px); }
    h1,h2,h3,h4,.brand-title { font-family:'Space Grotesk',sans-serif; color:var(--ink); }
    h1 { font-size:clamp(2rem,4vw,3.5rem)!important; letter-spacing:-.04em; } h2 { letter-spacing:-.03em; }
    p,label,[data-testid='stMetricLabel'] { color:var(--muted)!important; }
    [data-testid='stMetric'],.glass-card,[data-testid='stForm'],[data-testid='stExpander'],.ticket-card,.note-card { background:var(--glass); backdrop-filter:blur(12px); -webkit-backdrop-filter:blur(12px); border:1px solid var(--line); border-radius:20px; box-shadow:0 8px 32px rgba(31,38,135,.07); }
    [data-testid='stMetric'] { padding:18px 20px; } [data-testid='stMetricValue'] { color:var(--ink); font-family:'Space Grotesk',sans-serif; }
    [data-testid='stForm'] { padding:18px; }
    .eyebrow { color:var(--coral); font-size:.76rem; font-weight:700; letter-spacing:.14em; text-transform:uppercase; }
    .subtitle { color:var(--muted); font-size:1.05rem; max-width:660px; }
    .status-pill,.priority-pill,.category-pill { display:inline-block; border-radius:999px; padding:5px 11px; margin:2px 4px 2px 0; font-size:.75rem; font-weight:700; }
    .status-pill { background:#e0e7ff; color:#4f46a5; } .priority-pill { background:#ffddd5; color:#b44f42; } .category-pill { background:#e8defc; color:#7551a6; }
    .ticket-card,.note-card { padding:16px; margin:8px 0; } .ticket-id { color:var(--violet); font-family:monospace; font-weight:700; } .muted { color:var(--muted); }
    .login-shell { max-width:520px; margin:8vh auto 0; } .login-mark { color:var(--coral); font-family:'Space Grotesk',sans-serif; font-size:.8rem; font-weight:700; letter-spacing:.16em; }
    .login-copy { color:var(--muted); line-height:1.7; }
    .stButton>button,.stFormSubmitButton>button { border:0; border-radius:12px; color:white; font-weight:700; background:linear-gradient(135deg,var(--violet),#a26be2); box-shadow:0 8px 18px rgba(119,103,232,.22); transition:transform 160ms ease,box-shadow 160ms ease; }
    .stButton>button:hover,.stFormSubmitButton>button:hover { color:white; transform:translateY(-2px) scale(1.01); box-shadow:0 12px 22px rgba(119,103,232,.3); }
    input,textarea,select,[data-baseweb='select']>div { border-radius:12px!important; border-color:rgba(119,103,232,.16)!important; background:rgba(255,255,255,.66)!important; }
    [data-testid='stAlert'] { border-radius:14px; }
    </style>
    """,
    unsafe_allow_html=True,
)

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False


def get_openrouter_api_key():
    try:
        value = st.secrets.get("OPENROUTER_API_KEY")
        if value:
            return str(value).strip()
    except Exception:
        pass
    value = os.getenv("OPENROUTER_API_KEY")
    return str(value).strip() if value else None


def call_openrouter(prompt: str, api_key: str) -> str:
    payload = {"model":"openai/gpt-4o-mini","messages":[{"role":"user","content":prompt}]}
    req = request.Request("https://openrouter.ai/api/v1/chat/completions", data=json.dumps(payload).encode("utf-8"), headers={"Authorization":f"Bearer {api_key}","Content-Type":"application/json","HTTP-Referer":"http://localhost:8501","X-Title":"Support Ticket CRM"}, method="POST")
    with request.urlopen(req, timeout=60) as response:
        body = json.loads(response.read().decode("utf-8"))
    return str(body["choices"][0]["message"]["content"]).strip()


def send_reply_email(to_email: str, subject: str, body: str) -> bool:
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_password = os.getenv("SMTP_PASSWORD")
    smtp_from = os.getenv("SMTP_FROM", smtp_user or "support@local")
    if not smtp_host or not to_email:
        return False
    import smtplib
    from email.mime.text import MIMEText
    message = MIMEText(body)
    message["Subject"] = subject
    message["From"] = smtp_from
    message["To"] = to_email
    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
            server.starttls()
            if smtp_user and smtp_password:
                server.login(smtp_user, smtp_password)
            server.sendmail(smtp_from, [to_email], message.as_string())
        return True
    except Exception as exc:
        print(f"Email send failed: {exc}")
        return False


def generate_ai_draft(customer_name, subject, description):
    api_key = get_openrouter_api_key()
    if not api_key:
        return "OpenRouter API key is not configured. Add OPENROUTER_API_KEY to your environment."
    prompt = f"""
You are an expert customer support agent. Draft a helpful, empathetic, professional email response.
Customer name: {customer_name}
Subject: {subject}
Issue details: {description}
Address the customer by the provided name. Keep it under 150 words. Return only the response, without a subject line,
meta-commentary, placeholders, bracketed text, or a made-up signature.
"""
    try:
        return call_openrouter(prompt, api_key)
    except Exception as exc:
        error_message = f"OpenRouter API error: {exc}"
        print(error_message)
        return error_message


if not st.session_state.authenticated:
    _, center, _ = st.columns([1, 2, 1])
    with center:
        st.markdown("<div class='login-shell'><div class='login-mark'>SUPPORT / OS</div><h1>Welcome back.</h1><p class='login-copy'>A calmer command center for every customer conversation. Sign in to manage your queue.</p></div>", unsafe_allow_html=True)
        login_tab, signup_tab = st.tabs(["Sign in", "Create account"])
        with login_tab:
            with st.form("login_form"):
                username = st.text_input("Username", placeholder="admin")
                password = st.text_input("Password", type="password", placeholder="Your password")
                login_submitted = st.form_submit_button("Sign in", use_container_width=True)
            if login_submitted:
                user = authenticate_user(username, password)
                if user:
                    st.session_state.authenticated = True
                    st.session_state.current_user = user
                    st.session_state.login_error = ""
                    st.rerun()
                st.session_state.login_error = "Invalid username or password. Please try again."
        with signup_tab:
            with st.form("signup_form"):
                new_username = st.text_input("Username", placeholder="your-name")
                new_email = st.text_input("Email", placeholder="you@example.com")
                new_password = st.text_input("Password", type="password", placeholder="At least 8 characters")
                signup_submitted = st.form_submit_button("Create customer account", use_container_width=True)
            if signup_submitted:
                error_message = register_user(new_username, new_email, new_password)
                if error_message:
                    st.error(error_message)
                else:
                    st.success("Account created. Sign in with your new credentials.")
        if st.session_state.get("login_error"):
            st.error(st.session_state.login_error)
        st.caption("Admin demo: admin / password123 · New accounts are customer accounts")
    st.stop()


current_user = st.session_state["current_user"]
user_role = current_user["role"]
st.session_state.tickets = load_tickets(current_user["username"], user_role)

if "page" not in st.session_state:
    st.session_state.page = "Home"

nav_home, nav_crm, nav_about = st.columns([1, 1, 1])
if nav_home.button("Home", use_container_width=True):
    st.session_state.page = "Home"
    st.rerun()
if nav_crm.button("App / CRM", use_container_width=True):
    st.session_state.page = "CRM"
    st.rerun()
if nav_about.button("About", use_container_width=True):
    st.session_state.page = "About"
    st.rerun()

if st.session_state.page == "Home":
    st.markdown("""
    <div style="position:relative; overflow:hidden; padding-top:10px;">
      <div class="float-shape" style="width:220px;height:220px;background:radial-gradient(circle at 30% 30%,#e8dff5,#cbb8e8);top:-40px;left:-30px;opacity:0.55;"></div>
      <div class="float-shape" style="width:160px;height:160px;background:radial-gradient(circle at 30% 30%,#ffe8cc,#f5cba0);top:60px;right:-20px;opacity:0.55;"></div>
      <div class="float-shape" style="width:120px;height:120px;background:radial-gradient(circle at 30% 30%,#fff0d6,#fce0b0);bottom:20px;left:20%;opacity:0.45;"></div>
    </div>
    """, unsafe_allow_html=True)
    st.markdown("<div class='login-shell'><div class='eyebrow'>SUPPORT / OS</div><h1>Customer support, with room to think.</h1><p class='subtitle'>A focused workspace for triage, customer context, and faster resolution.</p></div>", unsafe_allow_html=True)
    home_left, home_right = st.columns([1.2, 1], gap="large")
    with home_left:
        st.markdown("<div class='glass-card' style='padding:28px; text-align:center'><div class='eyebrow'>COMMAND CENTER</div><h2>Every ticket has a next step.</h2><p>Keep the queue clear, preserve team context, and draft thoughtful replies without leaving the workflow.</p></div>", unsafe_allow_html=True)
    with home_right:
        st.markdown("<div class='glass-card' style='padding:28px; text-align:center'><h3>Today at a glance</h3><p class='muted'>Your session workspace is ready.</p></div>", unsafe_allow_html=True)
    st.markdown("### Built for the work between the messages")
    feature_one, feature_two, feature_three = st.columns(3)
    feature_one.markdown("<div class='ticket-card' style='text-align:center'><h3>Prioritize</h3><p>See urgency and category at a glance.</p></div>", unsafe_allow_html=True)
    feature_two.markdown("<div class='ticket-card' style='text-align:center'><h3>Collaborate</h3><p>Keep internal notes close to the customer story.</p></div>", unsafe_allow_html=True)
    feature_three.markdown("<div class='ticket-card' style='text-align:center'><h3>Respond</h3><p>Use OpenRouter to create a considered first draft.</p></div>", unsafe_allow_html=True)
    st.stop()

if st.session_state.page == "About":
    st.markdown("<div class='login-shell'><div class='eyebrow'>ABOUT SUPPORT / OS</div><h1>Clarity for customer teams.</h1><p class='subtitle'>Support OS brings triage, context, and customer communication into one calm workspace.</p></div>", unsafe_allow_html=True)
    about_left, about_right = st.columns(2, gap="large")
    with about_left:
        st.markdown("<div class='glass-card' style='padding:28px'><h2>One queue, less noise.</h2><p>Tickets stay searchable, status changes stay visible, and notes stay attached to the conversation they explain.</p><h3>Designed for momentum</h3><p>Move from a new issue to a clear next action without losing the details that matter.</p></div>", unsafe_allow_html=True)
    with about_right:
        st.markdown("<div class='glass-card' style='padding:28px'><h2>AI with a human handoff.</h2><p>OpenRouter drafts are placed in the response editor for review. Your team stays in control before anything becomes a saved note.</p><h3>Simple by design</h3><p>The dashboard uses session storage for this lightweight prototype.</p></div>", unsafe_allow_html=True)
    st.stop()


openrouter_api_key = get_openrouter_api_key()
with st.sidebar:
    st.markdown("<div class='eyebrow'>SUPPORT / OS</div><h2 class='brand-title'>Ticket intelligence</h2>", unsafe_allow_html=True)
    st.success(f"● Signed in as {current_user['username']} · {user_role}")
    if st.button("Log out", use_container_width=True):
        st.session_state.authenticated = False
        st.rerun()
    st.divider()
    st.markdown("### Raise a ticket")
    with st.form("create_ticket_form", clear_on_submit=True):
        cust_name = st.text_input("Customer name", placeholder="Alex Morgan")
        cust_email = st.text_input("Email", placeholder="alex@example.com")
        subject = st.text_input("Subject", placeholder="Unable to update billing details")
        description = st.text_area("Description", placeholder="Tell us what happened...")
        priority = st.selectbox("Priority", ["Low", "Medium", "Urgent"])
        category = st.selectbox("Category", ["Billing", "General", "Technical"])
        create_submitted = st.form_submit_button("Create ticket", use_container_width=True)
    if user_role == "admin" and openrouter_api_key:
        st.caption(f"OpenRouter ready · {openrouter_api_key[:8]}...")
    elif user_role == "admin":
        st.error("OPENROUTER_API_KEY is not configured.")

if create_submitted:
    if not cust_name.strip() or not subject.strip() or not description.strip():
        st.sidebar.error("Name, subject, and description are required.")
    else:
        new_id = f"TKT-{secrets.randbelow(9000) + 1000}"
        with database_connection() as connection:
            while connection.execute("SELECT 1 FROM tickets WHERE ticket_id = ?", (new_id,)).fetchone():
                new_id = f"TKT-{secrets.randbelow(9000) + 1000}"
            connection.execute(
                "INSERT INTO tickets (ticket_id, customer_name, customer_email, subject, description, status, priority, category, owner_username, created_at, updated_at) VALUES (?, ?, ?, ?, ?, 'Open', ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)",
                (new_id, cust_name.strip(), cust_email.strip(), subject.strip(), description.strip(), priority, category, current_user["username"]),
            )
        st.sidebar.success(f"Created {new_id}")
        try:
            send_reply_email(cust_email.strip(), f"Ticket Created: {subject.strip()}", f"Dear {cust_name.strip()},\n\nYour ticket {new_id} has been received. Subject: {subject.strip()}. Our team will review it shortly.\n\nBest,\nSupport Team")
        except Exception:
            pass
        st.rerun()


st.markdown("<div class='eyebrow'>OPERATIONS CONSOLE</div>", unsafe_allow_html=True)
st.title("Ticket command center")
st.markdown("<p class='subtitle'>A focused workspace for triage, customer context, and faster resolution.</p>", unsafe_allow_html=True)

total_count = len(st.session_state.tickets)
open_count = sum(ticket["status"] == "Open" for ticket in st.session_state.tickets)
progress_count = sum(ticket["status"] == "In Progress" for ticket in st.session_state.tickets)
closed_count = sum(ticket["status"] == "Closed" for ticket in st.session_state.tickets)

m1, m2, m3, m4 = st.columns(4)
m1.metric("TOTAL TICKETS", total_count)
m2.metric("OPEN", open_count)
m3.metric("IN PROGRESS", progress_count)
m4.metric("CLOSED", closed_count)

st.divider()
col_queue, col_detail = st.columns([1.1, 1.5], gap="large")
with col_queue:
    st.markdown("### Ticket queue")
    st.caption(f"{total_count} tickets · select one to open details")
    for ticket in st.session_state.tickets:
        st.markdown(f"<div class='ticket-card'><span class='ticket-id'>{ticket['id']}</span><br><strong>{ticket['subject']}</strong><br><span class='muted'>{ticket['customer']} · {ticket['category']}</span><br><span class='status-pill'>{ticket['status']}</span><span class='priority-pill'>{ticket['priority']}</span></div>", unsafe_allow_html=True)
        if st.button(f"Open {ticket['id']}", key=f"open-{ticket['id']}", use_container_width=True):
            st.session_state.selected_ticket_id = ticket["id"]
            st.session_state.draft_text = ""
            st.rerun()

with col_detail:
    selected_id = st.session_state.get("selected_ticket_id")
    selected_ticket = next((ticket for ticket in st.session_state.tickets if ticket["id"] == selected_id), None)
    if selected_ticket is None:
        st.markdown("<div class='glass-card' style='padding:32px; text-align:center'><div class='eyebrow'>TICKET DETAILS</div><h2>Select a ticket</h2><p class='muted'>Choose a ticket from the queue to open its details, actions, notes, and AI reply tools.</p></div>", unsafe_allow_html=True)
    else:
        st.markdown("### Ticket details")
        st.markdown(f"<div class='glass-card' style='padding:20px'><span class='ticket-id'>{selected_ticket['id']}</span><h2>{selected_ticket['subject']}</h2><p class='muted'>{selected_ticket['customer']} · {selected_ticket['email']}</p><span class='status-pill'>{selected_ticket['status']}</span><span class='priority-pill'>{selected_ticket['priority']}</span><span class='category-pill'>{selected_ticket['category']}</span><hr><p>{selected_ticket['description']}</p></div>", unsafe_allow_html=True)
        if user_role == "admin":
            status_options = ["Open", "In Progress", "Closed"]
            current_status_index = status_options.index(selected_ticket["status"]) if selected_ticket["status"] in status_options else 0
            new_status = st.selectbox("Ticket status", status_options, index=current_status_index, key=f"status-{selected_ticket['id']}")
            if new_status != selected_ticket["status"]:
                with database_connection() as connection:
                    connection.execute("UPDATE tickets SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE ticket_id = ?", (new_status, selected_ticket["id"]))
                st.rerun()
            st.markdown("### Add a note or reply")
            if st.button("Draft AI response", use_container_width=True):
                with st.spinner("Asking OpenRouter for a draft..."):
                    st.session_state.draft_text = generate_ai_draft(selected_ticket["customer"], selected_ticket["subject"], selected_ticket["description"])
            note_input = st.text_area("Response draft", value=st.session_state.get("draft_text", ""), height=170)
            send_col, save_col = st.columns(2)
            if send_col.button("Send to customer", use_container_width=True):
                if note_input.strip():
                    emailed = send_reply_email(selected_ticket["email"], f"Re: {selected_ticket['subject']}", note_input.strip())
                    with database_connection() as connection:
                        connection.execute("INSERT INTO replies (ticket_id, reply_text, sent_to_email) VALUES (?, ?, ?)", (selected_ticket["id"], note_input.strip(), 1 if emailed else 0))
                    st.session_state.draft_text = ""
                    st.success("Reply sent to customer." + (" Email delivered." if emailed else " Email not sent (SMTP not configured)."))
                    try:
                        send_reply_email(selected_ticket["email"], f"Re: {selected_ticket['subject']}", note_input.strip())
                    except Exception:
                        pass
                    st.rerun()
                else:
                    st.warning("Write a reply before sending.")
            if save_col.button("Save note", use_container_width=True):
                if note_input.strip():
                    with database_connection() as connection:
                        connection.execute("INSERT INTO notes (ticket_id, note_text) VALUES (?, ?)", (selected_ticket["id"], note_input.strip()))
                    st.session_state.draft_text = ""
                    st.success("Internal note saved.")
                    st.rerun()
                else:
                    st.warning("Write a note before saving.")
            st.markdown("### Customer replies")
            if selected_ticket.get("replies"):
                for reply in reversed(selected_ticket["replies"]):
                    st.markdown(f"<div class='note-card' style='border-left:3px solid #7767e8'><strong>Reply to customer</strong><br>{reply['text']}<br><span class='muted'>{reply['time']} · Emailed: {'yes' if reply['emailed'] else 'no'}</span></div>", unsafe_allow_html=True)
            else:
                st.caption("No customer replies sent yet.")
            st.markdown("### Internal notes")
            if selected_ticket["notes"]:
                for note in reversed(selected_ticket["notes"]):
                    st.markdown(f"<div class='note-card'>{note}</div>", unsafe_allow_html=True)
        else:
            st.markdown(f"<div class='glass-card' style='padding:18px 22px'><span class='eyebrow'>CURRENT STATUS</span><h2 style='margin-top:4px'>{selected_ticket['status']}</h2><p class='muted'>Your support team is reviewing this ticket.</p></div>", unsafe_allow_html=True)
            if selected_ticket.get("replies"):
                st.markdown("### Support replies")
                for reply in reversed(selected_ticket["replies"]):
                    st.markdown(f"<div class='note-card' style='border-left:3px solid #7767e8'><strong>From support team</strong><br>{reply['text']}<br><span class='muted'>{reply['time']}</span></div>", unsafe_allow_html=True)
            else:
                st.caption("No replies from the support team yet.")
