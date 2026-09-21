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
    page_title="Helios | Support Command Center",
    page_icon="⚡",
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
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=Space+Grotesk:wght@400;500;600;700&display=swap');

    :root {
        --indigo:#6366f1; --violet:#8b5cf6; --purple:#a855f7;
        --cyan:#06b6d4; --emerald:#10b981; --amber:#f59e0b; --rose:#f43f5e;
        --ink:#0b1020; --ink2:#1e293b; --muted:#64748b;
        --bg:#f6f7fb;
    }

    * { -webkit-font-smoothing:antialiased; box-sizing:border-box; }

    html, body, [data-testid="stAppViewContainer"], #root {
        height: 100%;
        min-height: 100vh;
    }
    [data-testid="stApp"] { min-height: 100vh; }

    /* ============ ANIMATED AMBIENT BACKGROUND ============ */
    .stApp {
        background: var(--bg);
        color: var(--ink);
        font-family: 'Inter', sans-serif;
        position: relative;
        overflow-x: hidden;
        min-height: 100vh;
    }
    .stApp::before {
        content: '';
        position: fixed; inset:0; z-index:0;
        background:
            radial-gradient(60% 50% at 12% 8%, rgba(99,102,241,.14), transparent 60%),
            radial-gradient(50% 45% at 88% 12%, rgba(168,85,247,.12), transparent 60%),
            radial-gradient(70% 50% at 50% 100%, rgba(6,182,212,.10), transparent 60%),
            radial-gradient(40% 40% at 95% 90%, rgba(16,185,129,.08), transparent 60%);
        animation: bgDrift 22s ease-in-out infinite;
    }
    @keyframes bgDrift {
        0%,100% { transform: scale(1) rotate(0deg); opacity:.9; }
        33% { transform: scale(1.06) rotate(1.2deg); opacity:1; }
        66% { transform: scale(0.97) rotate(-1deg); opacity:.85; }
    }

    /* drifting gradient blobs */
    .blob { position:fixed; border-radius:50%; filter:blur(70px); opacity:.5; z-index:0; pointer-events:none; }
    .blob-b1 { width:420px; height:420px; left:-120px; top:-80px;
        background:radial-gradient(circle,#818cf8,transparent 70%);
        animation: blobFloat 16s ease-in-out infinite; }
    .blob-b2 { width:380px; height:380px; right:-100px; top:22%;
        background:radial-gradient(circle,#a78bfa,transparent 70%);
        animation: blobFloat 20s ease-in-out infinite reverse; }
    .blob-b3 { width:360px; height:360px; left:30%; bottom:-140px;
        background:radial-gradient(circle,#22d3ee,transparent 70%);
        animation: blobFloat 24s ease-in-out infinite; }
    .blob-b4 { width:200px; height:200px; right:22%; bottom:18%;
        background:radial-gradient(circle,#34d399,transparent 70%);
        animation: blobFloat 18s ease-in-out infinite 2s; }
    @keyframes blobFloat {
        0%,100% { transform: translate(0,0) scale(1); }
        33% { transform: translate(40px,-50px) scale(1.12); }
        66% { transform: translate(-30px,30px) scale(.92); }
    }

    /* floating particles */
    .particles { position:fixed; inset:0; z-index:0; pointer-events:none; overflow:hidden; }
    .particle { position:absolute; bottom:-20px; border-radius:50%;
        background:linear-gradient(135deg,#818cf8,#22d3ee); opacity:.25;
        animation: rise linear infinite; }
    @keyframes rise {
        0% { transform: translateY(0) translateX(0); opacity:0; }
        12% { opacity:.35; }
        100% { transform: translateY(-110vh) translateX(30px); opacity:0; }
    }

    .main-content-wrapper { position:relative; z-index:10; }

    /* ============ LAYOUT ============ */
    [data-testid='stHeader'] { background:transparent !important; }
    [data-testid='stDecoration'] { display:none !important; }
    [data-testid='stToolbar'] { right:1rem; }
    [data-testid='stStatusWidget'] { background:transparent; }

    [data-testid='stSidebar'] {
        background: linear-gradient(180deg, rgba(255,255,255,.9), rgba(248,249,252,.82));
        backdrop-filter: blur(28px) saturate(180%);
        -webkit-backdrop-filter: blur(28px) saturate(180%);
        border-right: 1px solid rgba(255,255,255,.85);
        box-shadow: 8px 0 40px rgba(11,16,32,.06);
        z-index: 20;
    }
    [data-testid='stSidebar']::before {
        content:''; position:absolute; top:0; left:0; right:0; height:4px; z-index:2;
        background: linear-gradient(90deg,#6366f1,#a855f7,#ec4899,#06b6d4,#6366f1);
        background-size:300% 100%;
        animation: gradientSlide 8s ease-in-out infinite;
    }
    [data-testid='stSidebar']::after {
        content:''; position:absolute; inset:0; z-index:1; pointer-events:none;
        background:
            radial-gradient(120% 40% at 100% 0%, rgba(99,102,241,.08), transparent 60%),
            radial-gradient(120% 40% at 0% 100%, rgba(16,185,129,.06), transparent 60%);
    }
    @keyframes gradientSlide { 0%,100% {background-position:0% 50%;} 50% {background-position:100% 50%;} }

    /* ============ TYPOGRAPHY ============ */
    h1,h2,h3,h4 { font-family:'Space Grotesk',sans-serif; color:var(--ink); letter-spacing:-.02em; }
    h1 { font-size:clamp(2.1rem,4.4vw,3.9rem) !important; font-weight:700 !important; line-height:1.04; letter-spacing:-.03em; }
    h2 { font-weight:650 !important; }
    p,label,[data-testid='stMetricLabel'] { color:var(--muted) !important; }
    .brand-title { font-family:'Space Grotesk',sans-serif; }

    .gradient-text {
        background: linear-gradient(120deg,#4f46e5 0%,#7c3aed 35%,#db2777 70%,#0891b2 100%);
        background-size:250% 250%;
        -webkit-background-clip:text; background-clip:text;
        -webkit-text-fill-color:transparent;
        animation: gradientText 7s ease-in-out infinite;
    }
    @keyframes gradientText { 0%,100% {background-position:0% 50%;} 50% {background-position:100% 50%;} }

    /* ============ LOGIN COPY ============ */
    .login-copy {
        color: var(--muted);
        line-height: 1.7;
        margin: 10px 0 22px;
        font-size: 1rem;
        animation: fadeSlideIn .8s ease-in-out both;
        animation-delay: .15s;
    }

    /* ============ CARDS (Bento / Glass) ============ */
    .glass-card,[data-testid='stMetric'],[data-testid='stForm'],[data-testid='stExpander'] {
        background: linear-gradient(160deg, rgba(255,255,255,.92), rgba(255,255,255,.66));
        backdrop-filter: blur(22px) saturate(180%);
        -webkit-backdrop-filter: blur(22px) saturate(180%);
        border: 1px solid rgba(255,255,255,.85);
        border-radius: 22px;
        box-shadow: 0 1px 2px rgba(11,16,32,.03), 0 12px 40px rgba(11,16,32,.07);
        position: relative;
        transition: transform .35s cubic-bezier(.4,0,.2,1), box-shadow .35s cubic-bezier(.4,0,.2,1);
    }
    .glass-card:hover { transform: translateY(-4px); box-shadow:0 2px 4px rgba(11,16,32,.04), 0 24px 60px rgba(11,16,32,.12); }

    /* animated gradient border on hover */
    .glass-card::before {
        content:''; position:absolute; inset:-1px; border-radius:22px; z-index:-1;
        background:linear-gradient(135deg,#6366f1,#a855f7,#ec4899,#06b6d4,#6366f1);
        background-size:400% 400%;
        opacity:0; transition:opacity .4s ease;
        animation: gradientSlide 5s ease infinite;
    }
    .glass-card:hover::before { opacity:.35; }

    [data-testid='stMetric'] {
        padding: 22px 76px 22px 24px;
        border-radius: 20px;
        overflow:hidden;
    }
    [data-testid='stMetric']::after {
        content:''; position:absolute; top:0; left:0; right:0; height:3px;
        border-radius:20px 20px 0 0;
    }
    [data-testid='stMetricLabel'] { font-size:.7rem !important; font-weight:700 !important; letter-spacing:.16em; text-transform:uppercase; }
    [data-testid='stMetricValue'] { font-family:'Space Grotesk',sans-serif; font-weight:700 !important; color:var(--ink); font-size:2rem !important; }
    [data-testid='stMetricDelta'] { font-weight:600 !important; }

    .metric-icon-ring {
        position:absolute; top:16px; right:16px; width:46px; height:46px;
        border-radius:14px; display:flex; align-items:center; justify-content:center;
        font-family:'Space Grotesk',sans-serif; font-weight:700; font-size:1rem;
        color:#fff; box-shadow:0 8px 20px rgba(11,16,32,.16);
        animation: popIn .5s cubic-bezier(.24,1.4,.4,1) both;
    }
    @keyframes popIn { from { transform:scale(.4); opacity:0; } to { transform:scale(1); opacity:1; } }

    /* ============ PILLS ============ */
    .status-pill,.priority-pill,.category-pill {
        display:inline-flex; align-items:center; gap:6px;
        border-radius:999px; padding:6px 13px; margin:2px 6px 2px 0;
        font-size:.74rem; font-weight:650; letter-spacing:.01em; font-family:'Inter',sans-serif;
        border:1px solid transparent; white-space:nowrap;
    }
    .pill-dot { width:7px; height:7px; border-radius:50%; display:inline-block; }
    .status-Open { background:linear-gradient(135deg,#e0edff,#dbeafe); color:#1d4ed8; border-color:rgba(59,130,246,.25); }
    .status-Open .pill-dot { background:#3b82f6; box-shadow:0 0 0 3px rgba(59,130,246,.18); animation:dotPulse 2s infinite; }
    .status-In { background:linear-gradient(135deg,#fdf0d7,#fde68a); color:#b45309; border-color:rgba(245,158,11,.3); }
    .status-In .pill-dot { background:#f59e0b; box-shadow:0 0 0 3px rgba(245,158,11,.16); animation:dotPulse 2s infinite; }
    .status-Closed { background:linear-gradient(135deg,#d8f5ea,#c6f6e3); color:#047857; border-color:rgba(16,185,129,.3); }
    .status-Closed .pill-dot { background:#10b981; box-shadow:0 0 0 3px rgba(16,185,129,.16); }
    @keyframes dotPulse { 0%,100%{box-shadow:0 0 0 3px rgba(59,130,246,.18);} 50%{box-shadow:0 0 0 6px rgba(59,130,246,.06);} }

    .priority-Low { background:linear-gradient(135deg,#e7f9f3,#d1f5e8); color:#059669; border-color:rgba(16,185,129,.25); }
    .priority-Low .pill-dot { background:#10b981; }
    .priority-Medium { background:linear-gradient(135deg,#fff8e6,#fef0c7); color:#b45309; border-color:rgba(245,158,11,.28); }
    .priority-Medium .pill-dot { background:#f59e0b; }
    .priority-Urgent { background:linear-gradient(135deg,#ffe3e7,#fecdd3); color:#be123c; border-color:rgba(244,63,94,.28); }
    .priority-Urgent .pill-dot { background:#e11d48; box-shadow:0 0 0 3px rgba(225,29,72,.18); animation:dotPulse 1.2s infinite; }

    .category-Billing { background:linear-gradient(135deg,#f0ecff,#e5e0ff); color:#6d28d9; border-color:rgba(139,92,246,.24); }
    .category-General { background:linear-gradient(135deg,#e2f7fb,#cff6fc); color:#0e7490; border-color:rgba(6,182,212,.24); }
    .category-Technical { background:linear-gradient(135deg,#ffeaf5,#ffd6ea); color:#be185d; border-color:rgba(236,72,153,.24); }

    /* ============ TICKET CARDS ============ */
    .ticket-card {
        background:linear-gradient(160deg,rgba(255,255,255,.92),rgba(255,255,255,.66));
        backdrop-filter:blur(18px) saturate(180%);
        -webkit-backdrop-filter:blur(18px) saturate(180%);
        border:1px solid rgba(255,255,255,.8);
        border-radius:18px; box-shadow:0 1px 2px rgba(11,16,32,.03),0 8px 28px rgba(11,16,32,.05);
        padding:18px; margin:10px 0; position:relative; overflow:hidden;
        transition:transform .3s cubic-bezier(.4,0,.2,1), box-shadow .3s cubic-bezier(.4,0,.2,1), border-color .3s;
    }
    .ticket-card::before {
        content:''; position:absolute; left:0; top:0; bottom:0; width:4px;
        opacity:0; transition:opacity .3s;
    }
    .ticket-card[data-priority='Urgent']::before { background:linear-gradient(180deg,#f43f5e,#f97316); }
    .ticket-card[data-priority='Medium']::before { background:linear-gradient(180deg,#f59e0b,#fde047); }
    .ticket-card[data-priority='Low']::before { background:linear-gradient(180deg,#10b981,#38bdf8); }
    .ticket-card:hover {
        transform:translateY(-3px);
        box-shadow:0 2px 4px rgba(11,16,32,.05),0 18px 44px rgba(11,16,32,.10);
        border-color:rgba(99,102,241,.3);
    }
    .ticket-card:hover::before { opacity:1; }

    .ticket-mono { display:flex; align-items:center; justify-content:space-between; margin-bottom:8px; }
    .ticket-id { font-family:'Space Grotesk',sans-serif; font-weight:700; font-size:.8rem; letter-spacing:.02em;
        background:linear-gradient(90deg,#4f46e5,#7c3aed); -webkit-background-clip:text; -webkit-text-fill-color:transparent; }
    .ticket-subject { font-weight:650; color:var(--ink); font-size:.98rem; margin:6px 0; line-height:1.35; font-family:'Space Grotesk',sans-serif; }
    .ticket-meta { display:flex; align-items:center; gap:8px; color:var(--muted); font-size:.82rem; margin:6px 0 10px; }
    .muted { color:var(--muted); }

    .monogram {
        width:34px; height:34px; border-radius:50%; flex-shrink:0;
        display:flex; align-items:center; justify-content:center;
        color:#fff; font-weight:700; font-size:.82rem; font-family:'Space Grotesk',sans-serif;
        box-shadow:0 6px 14px rgba(99,102,241,.28);
        transition:transform .25s ease;
    }
    .ticket-card:hover .monogram { transform:scale(1.08); }

    .note-card {
        background:linear-gradient(160deg,rgba(255,255,255,.9),rgba(255,255,255,.6));
        backdrop-filter:blur(16px) saturate(180%);
        -webkit-backdrop-filter:blur(16px) saturate(180%);
        border:1px solid rgba(255,255,255,.75); border-radius:16px;
        padding:16px; margin:10px 0; position:relative;
        box-shadow:0 4px 18px rgba(11,16,32,.05);
        animation:fadeSlideIn .5s cubic-bezier(.4,0,.2,1) both;
    }
    .note-card-note { border-left:3px solid #a855f7; }
    .note-card-reply { border-left:3px solid #06b6d4; }
    @keyframes fadeSlideIn { from{opacity:0;transform:translateY(10px);} to{opacity:1;transform:translateY(0);} }

    /* ============ BUTTONS ============ */
    .stButton>button,.stFormSubmitButton>button {
        border:none !important; border-radius:13px !important; color:#fff !important;
        font-weight:650 !important; font-family:'Inter',sans-serif; font-size:.93rem !important;
        padding:.68rem 1.4rem !important; letter-spacing:.01em;
        background:linear-gradient(135deg,#4f46e5 0%,#7c3aed 55%,#a855f7 100%);
        background-size:200% 200%;
        box-shadow:0 4px 0 rgba(67,56,202,.25),0 12px 28px rgba(99,102,241,.28);
        transition:all .25s cubic-bezier(.4,0,.2,1) !important;
        position:relative; overflow:hidden;
    }
    .stButton>button::after,.stFormSubmitButton>button::after {
        content:''; position:absolute; top:0; left:-80%; width:50%; height:100%;
        background:linear-gradient(120deg,transparent,rgba(255,255,255,.45),transparent);
        transform:skewX(-20deg); animation:shimmer 3s ease-in-out infinite;
    }
    @keyframes shimmer { 0%,60%{left:-80%;} 100%{left:120%;} }
    .stButton>button:hover,.stFormSubmitButton>button:hover {
        color:#fff !important; transform:translateY(-2px); box-shadow:0 6px 0 rgba(67,56,202,.25),0 18px 40px rgba(99,102,241,.38);
    }
    .stButton>button:active,.stFormSubmitButton>button:active { transform:translateY(0); box-shadow:0 2px 0 rgba(67,56,202,.25),0 6px 18px rgba(99,102,241,.3); }

    .stButton>button[kind='secondary'] {
        background:rgba(255,255,255,.6) !important; color:var(--ink) !important;
        border:1px solid rgba(148,163,184,.25) !important; box-shadow:0 4px 12px rgba(11,16,32,.05);
    }
    .stButton>button[kind='secondary']:hover { background:rgba(255,255,255,.9) !important; box-shadow:0 8px 20px rgba(11,16,32,.1); }

    /* ============ INPUTS ============ */
    input,textarea,select,[data-baseweb='select']>div,[data-baseweb='base-input']>div>div {
        border-radius:13px !important; font-family:'Inter',sans-serif;
        border:1.5px solid rgba(99,102,241,.16) !important;
        background:rgba(255,255,255,.72) !important;
        transition:all .2s ease !important; color:var(--ink) !important;
    }
    input:focus,textarea:focus,[data-baseweb='select']:focus-within>div {
        border-color:rgba(99,102,241,.5) !important; background:rgba(255,255,255,.95) !important;
        box-shadow:0 0 0 4px rgba(99,102,241,.1) !important;
    }
    input::placeholder,textarea::placeholder { color:#a0aec0 !important; }
    textarea { line-height:1.6 !important; }
    label { font-weight:600 !important; font-family:'Inter',sans-serif; font-size:.85rem !important; }

    [data-testid='stAlert'] {
        border-radius:15px !important; border:1px solid transparent !important;
        backdrop-filter:blur(12px); font-family:'Inter',sans-serif; font-weight:500;
        box-shadow:0 6px 22px rgba(11,16,32,.06);
    }

    /* ============ EYEBROW / SUBTITLE ============ */
    .eyebrow {
        display:inline-flex; align-items:center; gap:8px;
        font-size:.72rem; font-weight:700; letter-spacing:.18em; text-transform:uppercase;
        color:#6d28d9; padding:7px 16px; border-radius:999px;
        background:linear-gradient(135deg,rgba(99,102,241,.12),rgba(168,85,247,.12));
        border:1px solid rgba(99,102,241,.18); font-family:'Inter',sans-serif;
        animation:popIn .6s cubic-bezier(.24,1.4,.4,1) both;
    }
    .subtitle { color:var(--muted); font-size:1.12rem; line-height:1.7; max-width:680px; }

    /* ============ HERO ============ */
    .hero-card {
        position:relative; padding:56px 48px; border-radius:30px; overflow:hidden;
        background:linear-gradient(160deg,rgba(255,255,255,.94),rgba(255,255,255,.7));
        backdrop-filter:blur(24px) saturate(180%);
        -webkit-backdrop-filter:blur(24px) saturate(180%);
        border:1px solid rgba(255,255,255,.85);
        box-shadow:0 1px 2px rgba(11,16,32,.03),0 28px 70px rgba(11,16,32,.09);
        animation:fadeSlideIn .7s cubic-bezier(.4,0,.2,1) both;
    }
    .hero-card::before {
        content:''; position:absolute; inset:0; z-index:0;
        background:
            radial-gradient(120% 60% at 90% 0%, rgba(168,85,247,.14), transparent 55%),
            radial-gradient(120% 60% at 8% 100%, rgba(6,182,212,.12), transparent 55%);
    }
    .hero-grid-lines {
        position:absolute; inset:0; z-index:0; opacity:.4; pointer-events:none;
        background-image:
            linear-gradient(rgba(99,102,241,.05) 1px, transparent 1px),
            linear-gradient(90deg, rgba(99,102,241,.05) 1px, transparent 1px);
        background-size:44px 44px;
        -webkit-mask-image:radial-gradient(circle at 50% 40%, black, transparent 80%);
        mask-image:radial-gradient(circle at 50% 40%, black, transparent 80%);
    }
    .hero-ring {
        position:absolute; border-radius:50%; border:1px solid rgba(99,102,241,.15); z-index:0;
        animation:ringPulse 6s ease-in-out infinite; pointer-events:none;
    }
    .hero-ring-r1 { width:300px; height:300px; right:-60px; top:-60px; }
    .hero-ring-r2 { width:420px; height:420px; right:-120px; top:-120px; animation-delay:2s; }
    .hero-ring-r3 { width:180px; height:180px; left:-40px; bottom:-40px; animation-delay:4s; }
    @keyframes ringPulse { 0%,100%{transform:scale(1);opacity:.5;} 50%{transform:scale(1.12);opacity:.15;} }

    .hero-stat-chip {
        display:inline-flex; align-items:center; gap:8px;
        padding:8px 16px; border-radius:999px; font-size:.82rem; font-weight:600;
        background:rgba(255,255,255,.6); border:1px solid rgba(148,163,184,.2);
        color:var(--ink2); box-shadow:0 2px 8px rgba(11,16,32,.04);
        animation:popIn .6s cubic-bezier(.24,1.4,.4,1) both;
    }
    .hero-dot { width:8px; height:8px; border-radius:50%; background:#10b981; box-shadow:0 0 0 3px rgba(16,185,129,.2); }

    /* ============ FEATURE CARDS ============ */
    .feature-card {
        position:relative; padding:32px 28px; border-radius:22px; overflow:hidden; cursor:default;
        transition:transform .35s cubic-bezier(.4,0,.2,1), box-shadow .35s;
    }
    .feature-card:hover { transform:translateY(-7px); box-shadow:0 24px 56px rgba(11,16,32,.12); }
    .feature-card::before { content:''; position:absolute; top:0; left:0; right:0; height:4px; border-radius:22px 22px 0 0; }
    .feature-icon {
        width:54px; height:54px; border-radius:15px; display:flex; align-items:center; justify-content:center;
        color:#fff; font-family:'Space Grotesk',sans-serif; font-weight:700; font-size:1.15rem;
        margin-bottom:18px; box-shadow:0 8px 20px rgba(11,16,32,.12); animation:popIn .6s cubic-bezier(.24,1.4,.4,1) both;
    }
    .feature-title { font-family:'Space Grotesk',sans-serif; font-weight:700; font-size:1.16rem; color:var(--ink); margin:0 0 8px; }
    .feature-desc { color:var(--muted); font-size:.95rem; line-height:1.65; margin:0; }

    /* ============ LOGIN (SPLIT) ============ */
    .split-login { display:grid; grid-template-columns:1.1fr 1fr; gap:48px; align-items:center; max-width:1180px; margin:0 auto; padding:30px 20px; }
    .login-visual { position:relative; animation:fadeSlideIn .7s cubic-bezier(.4,0,.2,1) .1s both; }
    .login-form-side { animation:fadeSlideIn .7s cubic-bezier(.4,0,.2,1); }

    .big-visual {
        position:relative; background:
            radial-gradient(120% 80% at 0% 0%, rgba(129,140,248,.55), transparent 60%),
            radial-gradient(120% 80% at 100% 100%, rgba(217,70,239,.5), transparent 60%),
            linear-gradient(135deg,#4f46e5,#7c3aed);
        border-radius:30px; padding:60px 46px; overflow:hidden; color:#fff;
        box-shadow:0 1px 0 rgba(255,255,255,.2) inset,0 36px 90px rgba(79,70,229,.4);
    }
    .big-visual::before { content:''; position:absolute; top:-70px; right:-70px; width:260px; height:260px;
        border-radius:50%; background:radial-gradient(circle,rgba(255,255,255,.22),transparent 70%); }
    .big-visual::after { content:''; position:absolute; bottom:-60px; left:-40px; width:200px; height:200px;
        border-radius:50%; background:radial-gradient(circle,rgba(253,224,71,.25),transparent 70%); }
    .visual-logo-line { display:flex; align-items:center; gap:10px; color:rgba(255,255,255,.9); font-weight:700;
        letter-spacing:.18em; font-size:.75rem; text-transform:uppercase; font-family:'Inter',sans-serif; }
    .visual-headed { font-family:'Space Grotesk',sans-serif; font-weight:700; font-size:2.3rem; line-height:1.08; letter-spacing:-.025em; color:#fff; position:relative; z-index:2; margin:26px 0 16px; }
    .visual-sub { color:rgba(255,255,255,.85); font-size:1rem; line-height:1.7; position:relative; z-index:2; }
    .visual-orbs { display:flex; gap:12px; margin:26px 0 34px; position:relative; z-index:2; position:relative; }
    .visual-orb { width:52px; height:52px; border-radius:16px; background:rgba(255,255,255,.16);
        backdrop-filter:blur(8px); border:1px solid rgba(255,255,255,.25); display:flex; align-items:center; justify-content:center;
        font-family:'Space Grotesk',sans-serif; font-weight:700; font-size:1.1rem; color:#fff;
        animation:orbBob 3.5s ease-in-out infinite; }
    .visual-orb:nth-child(2){animation-delay:.3s;} .visual-orb:nth-child(3){animation-delay:.6s;}
    .visual-orb:nth-child(4){animation-delay:.9s;} .visual-orb:nth-child(5){animation-delay:1.2s;}
    @keyframes orbBob { 0%,100%{transform:translateY(0);} 50%{transform:translateY(-10px);} }
    .visual-stats { display:flex; gap:26px; margin-top:34px; padding-top:28px; border-top:1px solid rgba(255,255,255,.2); position:relative; z-index:2; }
    .visual-stat-num { font-family:'Space Grotesk',sans-serif; font-weight:700; font-size:1.9rem; line-height:1; margin-bottom:4px; color:#fff; }
    .visual-stat-label { font-size:.72rem; opacity:.8; text-transform:uppercase; letter-spacing:.12em; font-weight:600; }

    .login-shell { max-width:440px; margin:0 auto; }
    .login-mark { display:inline-flex; align-items:center; gap:10px; font-size:.78rem; font-weight:800; letter-spacing:.2em;
        text-transform:uppercase; font-family:'Space Grotesk',sans-serif; }
    .login-logo-dot { width:38px; height:38px; border-radius:12px; background:linear-gradient(135deg,#4f46e5,#7c3aed);
        display:flex; align-items:center; justify-content:center; font-size:1.05rem; color:#fff;
        box-shadow:0 8px 20px rgba(99,102,241,.3); animation:gradientSlide 4s ease infinite; background-size:200% 200%; }

    .demo-note { display:flex; align-items:center; gap:10px; padding:11px 16px; border-radius:14px;
        background:rgba(255,255,255,.55); border:1px solid rgba(148,163,184,.18); font-size:.82rem;
        color:var(--muted); font-weight:500; }
    .demo-note b { color:var(--ink2); }
    .kbd { padding:1px 7px; border-radius:6px; background:rgba(99,102,241,.1); color:#4f46e5; font-weight:650; font-size:.78rem; }

    /* ============ SECTION HEADERS / DETAIL ============ */
    .section-header { display:flex; align-items:center; gap:10px; margin:20px 0 12px; }
    .section-header-icon { width:32px; height:32px; border-radius:10px; display:flex; align-items:center; justify-content:center;
        background:linear-gradient(135deg,rgba(99,102,241,.12),rgba(168,85,247,.12)); font-family:'Space Grotesk',sans-serif; font-weight:700; font-size:.8rem; color:#6d28d9; }
    .section-header h3 { margin:0 !important; font-size:1.1rem !important; letter-spacing:-.01em; }

    .detail-grid { display:grid; grid-template-columns:1fr 1fr; gap:12px 18px; padding:14px 0; border-top:1px solid rgba(148,163,184,.14); border-bottom:1px solid rgba(148,163,184,.14); margin:14px 0; }
    .detail-label { font-size:.68rem; font-weight:700; color:var(--muted); text-transform:uppercase; letter-spacing:.12em; margin-bottom:4px; }
    .detail-value { color:var(--ink); font-weight:600; font-size:.95rem; }
    .description-box { background:linear-gradient(150deg,rgba(248,250,252,.9),rgba(255,255,255,.6));
        border:1px solid rgba(148,163,184,.14); border-radius:14px; padding:16px 18px; margin:14px 0 0; line-height:1.65; color:var(--ink2); }
    .ticket-details-avatar { width:52px; height:52px; border-radius:16px; background:linear-gradient(135deg,#4f46e5,#7c3aed);
        color:#fff; display:flex; align-items:center; justify-content:center; font-weight:700; font-size:1.25rem;
        font-family:'Space Grotesk',sans-serif; box-shadow:0 8px 18px rgba(99,102,241,.3); flex-shrink:0; }
    .reply-note-meta { display:flex; align-items:center; justify-content:space-between; margin-bottom:10px; padding-bottom:8px; border-bottom:1px solid rgba(148,163,184,.1); }
    .reply-note-author { display:flex; align-items:center; gap:8px; font-weight:700; color:var(--ink2); font-size:.88rem; }
    .reply-note-time { font-size:.76rem; color:var(--muted); }
    .email-badge { display:inline-flex; align-items:center; gap:5px; font-size:.68rem; padding:3px 11px; border-radius:999px;
        background:linear-gradient(135deg,#d1f5e8,#a7f3d0); color:#065f46; font-weight:700; border:1px solid rgba(16,185,129,.25); }
    .no-email-badge { display:inline-flex; align-items:center; gap:5px; font-size:.68rem; padding:3px 11px; border-radius:999px;
        background:linear-gradient(135deg,#fef3c7,#fde68a); color:#92400e; font-weight:700; border:1px solid rgba(245,158,11,.25); }
    .badge-check { width:12px; height:7px; border-left:2px solid currentColor; border-bottom:2px solid currentColor; transform:rotate(-45deg); margin-top:-2px; }

    .empty-state { padding:26px; text-align:center; background:linear-gradient(150deg,rgba(255,255,255,.6),rgba(255,255,255,.4));
        border:1.5px dashed rgba(148,163,184,.28); border-radius:16px; }
    .empty-symbol { width:54px; height:54px; margin:0 auto 12px; border-radius:17px; background:linear-gradient(135deg,rgba(99,102,241,.12),rgba(16,185,129,.1));
        display:flex; align-items:center; justify-content:center; font-family:'Space Grotesk',sans-serif; font-weight:700; font-size:1.2rem; color:#6366f1; border:1px solid rgba(99,102,241,.15); }
    .empty-title { font-weight:650; color:var(--ink2); font-size:.94rem; margin-bottom:4px; }
    .empty-sub { font-size:.82rem; color:var(--muted); }

    .gradient-divider { height:1px; margin:22px 0; border:none;
        background:linear-gradient(90deg,transparent,rgba(99,102,241,.18),rgba(168,85,247,.26),rgba(236,72,153,.16),transparent); }

    .hr-fancy { border:none; height:1px; margin:20px 0; background:linear-gradient(90deg,transparent,rgba(148,163,184,.22),transparent); }

    /* sidebar user badge */
    .sidebar-user-badge { display:flex; align-items:center; gap:12px; padding:13px 15px; margin:6px 0 12px;
        background:linear-gradient(135deg,rgba(16,185,129,.09),rgba(6,182,212,.06)); border:1px solid rgba(16,185,129,.18);
        border-radius:14px; animation:popIn .5s ease both; }
    .sidebar-user-avatar { width:38px; height:38px; border-radius:50%; background:linear-gradient(135deg,#6366f1,#ec4899);
        display:flex; align-items:center; justify-content:center; color:#fff; font-weight:700; font-size:.95rem;
        font-family:'Space Grotesk',sans-serif; box-shadow:0 6px 14px rgba(99,102,241,.3); flex-shrink:0; }
    .sidebar-user-name { font-weight:700; font-size:.9rem; color:var(--ink); white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
    .sidebar-user-role { font-size:.7rem; color:var(--muted); text-transform:uppercase; letter-spacing:.12em; font-weight:600; }
    .sidebar-status-dot { width:8px; height:8px; border-radius:50%; background:#10b981; box-shadow:0 0 0 3px rgba(16,185,129,.2); }

    .brand-logo { display:inline-flex; align-items:center; gap:11px; }
    .brand-logo-mark { width:38px; height:38px; border-radius:12px; background:linear-gradient(135deg,#4f46e5,#7c3aed,#db2777);
        display:flex; align-items:center; justify-content:center; font-size:1.05rem; color:#fff;
        box-shadow:0 6px 18px rgba(99,102,241,.32); animation:gradientSlide 5s ease infinite; background-size:250% 250%; }
    .brand-title-text { font-family:'Space Grotesk',sans-serif; font-weight:700; font-size:1.25rem; color:var(--ink); letter-spacing:-.02em; line-height:1; }
    .brand-subtitle { font-size:.72rem; color:var(--muted); font-weight:600; letter-spacing:.1em; text-transform:uppercase; }

    .quick-chip { display:inline-flex; align-items:center; gap:6px; padding:7px 14px; border-radius:999px; font-size:.8rem; font-weight:600;
        background:rgba(255,255,255,.62); border:1px solid rgba(148,163,184,.18); color:var(--ink2);
        box-shadow:0 2px 8px rgba(11,16,32,.04); animation:popIn .6s cubic-bezier(.24,1.4,.4,1) both; }

    [data-baseweb='tab-list'] { background:rgba(255,255,255,.45) !important; backdrop-filter:blur(10px); border-radius:13px !important;
        padding:5px !important; border:1px solid rgba(148,163,184,.15) !important; }
    [data-baseweb='tab'] { font-weight:600 !important; font-size:.9rem !important; }
    [data-baseweb='tab'][aria-selected='true'] { background:#fff !important; border-radius:9px !important; color:var(--ink) !important;
        box-shadow:0 2px 10px rgba(11,16,32,.07) !important; }

    @media (max-width:900px) {
        .split-login { grid-template-columns:1fr; gap:14px; padding:20px; }
        .login-visual { padding:12px; }
        .big-visual { padding:40px 28px; }
        .detail-grid { grid-template-columns:1fr; }
    }
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


st.markdown("""
<div class="blob blob-b1"></div>
<div class="blob blob-b2"></div>
<div class="blob blob-b3"></div>
<div class="blob blob-b4"></div>
<script>
    (function(){
        var host = document.querySelector('.stApp') || document.body;
        var wrap = document.createElement('div');
        wrap.className = 'particles';
        for (var i = 0; i < 18; i++) {
            var p = document.createElement('span');
            p.className = 'particle';
            var s = 3 + Math.random() * 6;
            p.style.width = s + 'px';
            p.style.height = s + 'px';
            p.style.left = (Math.random() * 100) + 'vw';
            p.style.animationDuration = (9 + Math.random() * 9) + 's';
            p.style.animationDelay = (Math.random() * 8) + 's';
            wrap.appendChild(p);
        }
        document.body.appendChild(wrap);
    })();
</script>
<div class="main-content-wrapper">
""", unsafe_allow_html=True)


if not st.session_state.authenticated:
    st.markdown("""
    <div class="split-login">
        <div class="login-visual">
            <div class="big-visual">
                <div class="visual-logo-line">
                    <span style="width:8px;height:8px;border-radius:50%;background:#fde68a;box-shadow:0 0 12px #fde68a;"></span>
                    HELIOS &middot; SUPPORT ENGINE
                </div>
                <div class="visual-headed">
                    Every ticket.<br>
                    <span style="background:linear-gradient(90deg,#fde68a,#f9a8d4); -webkit-background-clip:text; background-clip:text; -webkit-text-fill-color:transparent;">Perfectly orchestrated.</span>
                </div>
                <div class="visual-sub">
                    A precise, elegant command center for every customer conversation — triage faster, preserve context, and deliver thoughtful responses from a single workspace.
                </div>
                <div class="visual-orbs">
                    <div class="visual-orb">01</div>
                    <div class="visual-orb">02</div>
                    <div class="visual-orb">03</div>
                    <div class="visual-orb">04</div>
                    <div class="visual-orb">05</div>
                </div>
                <div class="visual-stats">
                    <div class="visual-stat">
                        <div class="visual-stat-num">99.8%</div>
                        <div class="visual-stat-label">Uptime</div>
                    </div>
                    <div class="visual-stat">
                        <div class="visual-stat-num">2.4h</div>
                        <div class="visual-stat-label">Avg Response</div>
                    </div>
                    <div class="visual-stat">
                        <div class="visual-stat-num">10k+</div>
                        <div class="visual-stat-label">Tickets</div>
                    </div>
                </div>
            </div>
        </div>
        <div class="login-form-side">
            <div class="login-shell">
                <div class="brand-logo">
                    <div class="login-logo-dot">H</div>
                    <div>
                        <div class="brand-title-text">Helios</div>
                        <div class="brand-subtitle">Ticket Intelligence</div>
                    </div>
                </div>
                <h1 style="margin-top:24px; font-size:clamp(1.8rem,3.4vw,2.5rem);">
                    Welcome <span class="gradient-text">back.</span>
                </h1>
                <p class="login-copy" style="color:var(--muted);line-height:1.7;margin:10px 0 22px;">
                    Sign in to manage your support queue, draft replies, and keep customers satisfied.
                </p>
    """, unsafe_allow_html=True)

    login_tab, signup_tab = st.tabs(["  Sign in", "  Create account"])
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

    st.markdown("""
                <div class="hr-fancy"></div>
                <div class="demo-note">
                    <span style="width:10px;height:10px;border-radius:50%;background:#10b981;box-shadow:0 0 0 3px rgba(16,185,129,.18);margin-right:2px;"></span>
                    <span>Admin demo: <b>admin</b> / <span class="kbd">password123</span> &middot; New accounts are customer accounts</span>
                </div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    st.stop()


current_user = st.session_state["current_user"]
user_role = current_user["role"]
st.session_state.tickets = load_tickets(current_user["username"], user_role)

if "page" not in st.session_state:
    st.session_state.page = "Home"

page = st.session_state.page

st.markdown("""
<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:20px;gap:12px;flex-wrap:wrap;">
    <div class="brand-logo">
        <div class="brand-logo-mark">H</div>
        <div>
            <div class="brand-title-text">Helios</div>
            <div class="brand-subtitle">Ticket Intelligence Platform</div>
        </div>
    </div>
    <div style="display:flex;gap:10px;flex:1;max-width:520px;min-width:280px;">
""", unsafe_allow_html=True)

nav1, nav2, nav3 = st.columns(3)
if nav1.button("Home", use_container_width=True, type="primary" if page == "Home" else "secondary"):
    st.session_state.page = "Home"
    st.rerun()
if nav2.button("App / CRM", use_container_width=True, type="primary" if page == "CRM" else "secondary"):
    st.session_state.page = "CRM"
    st.rerun()
if nav3.button("About", use_container_width=True, type="primary" if page == "About" else "secondary"):
    st.session_state.page = "About"
    st.rerun()

st.markdown("</div></div>", unsafe_allow_html=True)

if st.session_state.page == "Home":
    st.markdown("""
    <div class="hero-card" style="margin-bottom:28px;">
        <div class="hero-grid-lines"></div>
        <div class="hero-ring hero-ring-r1"></div>
        <div class="hero-ring hero-ring-r2"></div>
        <div class="hero-ring hero-ring-r3"></div>
        <div style="position:relative;z-index:2;">
            <div class="eyebrow">HELIOS &middot; COMMAND CENTER</div>
            <h1 style="margin-top:18px;margin-bottom:14px;font-size:clamp(2.4rem,5vw,4.1rem);">
                Orchestrate every<br>
                <span class="gradient-text">customer conversation.</span>
            </h1>
            <p class="subtitle" style="font-size:1.14rem;">
                A refined workspace for triage, context, and resolution. Keep the queue clear, preserve team knowledge, and craft thoughtful replies — all in one seamless flow.
            </p>
            <div style="display:flex;gap:10px;flex-wrap:wrap;margin-top:28px;">
                <span class="hero-stat-chip"><span class="hero-dot"></span> Real-time queue</span>
                <span class="hero-stat-chip"><span style="width:7px;height:7px;border-radius:50%;background:#7c3aed;box-shadow:0 0 0 3px rgba(124,58,237,.15);"></span> AI-powered drafts</span>
                <span class="hero-stat-chip"><span style="width:7px;height:7px;border-radius:50%;background:#06b6d4;box-shadow:0 0 0 3px rgba(6,182,212,.15);"></span> Internal notes</span>
                <span class="hero-stat-chip"><span style="width:7px;height:7px;border-radius:50%;background:#10b981;box-shadow:0 0 0 3px rgba(16,185,129,.15);"></span> Email replies</span>
                <span class="hero-stat-chip"><span style="width:7px;height:7px;border-radius:50%;background:#f59e0b;box-shadow:0 0 0 3px rgba(245,158,11,.15);"></span> Role-based access</span>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    home_left, home_right = st.columns([1.2, 1], gap="large")
    with home_left:
        st.markdown("""
        <div class="glass-card" style="padding:40px;border-radius:26px;">
            <div class="eyebrow" style="margin-bottom:14px;">WHY HELIOS</div>
            <h2 style="font-size:1.7rem;letter-spacing:-0.02em;margin:0 0 10px;">Every ticket has a next step.</h2>
            <p style="font-size:1.05rem;line-height:1.7;color:var(--muted);margin:0 0 24px;">
                Keep the queue clear, preserve team context, and draft thoughtful replies without leaving the workflow. Your team's new calm command center.
            </p>
            <div class="hr-fancy"></div>
            <div style="display:flex;gap:16px;flex-wrap:wrap;">
                <div style="display:flex;align-items:center;gap:11px;flex:1;min-width:150px;">
                    <div style="width:42px;height:42px;border-radius:12px;background:linear-gradient(135deg,#d1f5e8,#a7f3d0);display:flex;align-items:center;justify-content:center;font-family:'Space Grotesk',sans-serif;font-weight:700;color:#059669;">T</div>
                    <div>
                        <div style="font-weight:700;color:var(--ink);font-size:.95rem;">Clear Triage</div>
                        <div style="font-size:.76rem;color:var(--muted);">Priority &amp; status at a glance</div>
                    </div>
                </div>
                <div style="display:flex;align-items:center;gap:11px;flex:1;min-width:150px;">
                    <div style="width:42px;height:42px;border-radius:12px;background:linear-gradient(135deg,#f0ecff,#ddd6fe);display:flex;align-items:center;justify-content:center;font-family:'Space Grotesk',sans-serif;font-weight:700;color:#7c3aed;">C</div>
                    <div>
                        <div style="font-weight:700;color:var(--ink);font-size:.95rem;">Context Preserved</div>
                        <div style="font-size:.76rem;color:var(--muted);">Notes stay with each ticket</div>
                    </div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    with home_right:
        total_count = len(st.session_state.tickets)
        open_count = sum(ticket["status"] == "Open" for ticket in st.session_state.tickets)
        progress_count = sum(ticket["status"] == "In Progress" for ticket in st.session_state.tickets)
        closed_count = sum(ticket["status"] == "Closed" for ticket in st.session_state.tickets)
        urgent_count = sum(ticket["priority"] == "Urgent" for ticket in st.session_state.tickets)

        st.markdown(f"""
        <div class="glass-card" style="padding:32px;border-radius:26px;">
            <div style="display:flex;align-items:center;gap:11px;margin-bottom:20px;">
                <div style="width:40px;height:40px;border-radius:12px;background:linear-gradient(135deg,#6366f1,#7c3aed);display:flex;align-items:center;justify-content:center;font-family:'Space Grotesk',sans-serif;font-weight:700;color:#fff;font-size:1rem;box-shadow:0 6px 16px rgba(99,102,241,0.3);">S</div>
                <div>
                    <h3 style="margin:0;font-size:1.15rem;">Today at a glance</h3>
                    <div style="font-size:0.8rem;color:var(--muted);">Your session workspace is ready</div>
                </div>
            </div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;">
                <div style="background:linear-gradient(135deg,rgba(99,102,241,0.1),rgba(139,92,246,0.08));border:1px solid rgba(99,102,241,0.18);border-radius:16px;padding:16px;">
                    <div style="font-size:0.7rem;font-weight:700;color:#6366f1;text-transform:uppercase;letter-spacing:0.12em;margin-bottom:4px;">Total</div>
                    <div style="font-family:'Space Grotesk',sans-serif;font-weight:700;font-size:1.9rem;color:var(--ink);line-height:1;">{total_count}</div>
                </div>
                <div style="background:linear-gradient(135deg,rgba(59,130,246,0.1),rgba(96,165,250,0.08));border:1px solid rgba(59,130,246,0.18);border-radius:16px;padding:16px;">
                    <div style="font-size:0.7rem;font-weight:700;color:#2563eb;text-transform:uppercase;letter-spacing:0.12em;margin-bottom:4px;">Open</div>
                    <div style="font-family:'Space Grotesk',sans-serif;font-weight:700;font-size:1.9rem;color:var(--ink);line-height:1;">{open_count}</div>
                </div>
                <div style="background:linear-gradient(135deg,rgba(245,158,11,0.1),rgba(251,191,36,0.08));border:1px solid rgba(245,158,11,0.18);border-radius:16px;padding:16px;">
                    <div style="font-size:0.7rem;font-weight:700;color:#d97706;text-transform:uppercase;letter-spacing:0.12em;margin-bottom:4px;">In Progress</div>
                    <div style="font-family:'Space Grotesk',sans-serif;font-weight:700;font-size:1.9rem;color:var(--ink);line-height:1;">{progress_count}</div>
                </div>
                <div style="background:linear-gradient(135deg,rgba(16,185,129,0.1),rgba(52,211,153,0.08));border:1px solid rgba(16,185,129,0.18);border-radius:16px;padding:16px;">
                    <div style="font-size:0.7rem;font-weight:700;color:#059669;text-transform:uppercase;letter-spacing:0.12em;margin-bottom:4px;">Closed</div>
                    <div style="font-family:'Space Grotesk',sans-serif;font-weight:700;font-size:1.9rem;color:var(--ink);line-height:1;">{closed_count}</div>
                </div>
            </div>
            <div class="hr-fancy"></div>
            <div style="display:flex;align-items:center;justify-content:space-between;padding:10px 14px;background:linear-gradient(135deg,rgba(244,63,94,0.08),rgba(249,115,22,0.06));border:1px solid rgba(244,63,94,0.18);border-radius:12px;">
                <div style="display:flex;align-items:center;gap:9px;">
                    <span style="width:9px;height:9px;border-radius:50%;background:#e11d48;box-shadow:0 0 0 3px rgba(225,29,72,.16);animation:dotPulse 1.2s infinite;"></span>
                    <span style="font-weight:700;color:#be123c;font-size:.9rem;">Urgent tickets</span>
                </div>
                <span style="font-family:'Space Grotesk',sans-serif;font-weight:700;color:#be123c;font-size:1.4rem;">{urgent_count}</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("""
    <div style="display:flex;align-items:center;gap:12px;margin:40px 0 18px;">
        <div style="width:4px;height:32px;background:linear-gradient(180deg,#6366f1,#ec4899);border-radius:2px;"></div>
        <h2 style="margin:0;font-size:1.7rem;">Built for the work between the messages</h2>
    </div>
    """, unsafe_allow_html=True)

    feature_one, feature_two, feature_three = st.columns(3)
    feature_one.markdown("""
    <div class="glass-card feature-card">
        <div style="position:absolute;top:0;left:0;right:0;height:4px;border-radius:22px 22px 0 0;background:linear-gradient(90deg,#6366f1,#8b5cf6);"></div>
        <div class="feature-icon" style="background:linear-gradient(135deg,#6366f1,#8b5cf6);">P</div>
        <h3 class="feature-title">Prioritize Intelligently</h3>
        <p class="feature-desc">See urgency, status, and category at a glance with visual color coding and pulsing indicators for urgent items. Never miss a critical ticket.</p>
    </div>
    """, unsafe_allow_html=True)
    feature_two.markdown("""
    <div class="glass-card feature-card">
        <div style="position:absolute;top:0;left:0;right:0;height:4px;border-radius:22px 22px 0 0;background:linear-gradient(90deg,#ec4899,#f97316);"></div>
        <div class="feature-icon" style="background:linear-gradient(135deg,#ec4899,#f97316);">C</div>
        <h3 class="feature-title">Collaborate Seamlessly</h3>
        <p class="feature-desc">Keep internal notes close to the customer story. Attach context, decisions, and follow-ups directly to each ticket for perfect handoffs.</p>
    </div>
    """, unsafe_allow_html=True)
    feature_three.markdown("""
    <div class="glass-card feature-card">
        <div style="position:absolute;top:0;left:0;right:0;height:4px;border-radius:22px 22px 0 0;background:linear-gradient(90deg,#06b6d4,#10b981);"></div>
        <div class="feature-icon" style="background:linear-gradient(135deg,#06b6d4,#10b981);">R</div>
        <h3 class="feature-title">Respond Instantly</h3>
        <p class="feature-desc">Leverage OpenRouter AI to create thoughtful first drafts in seconds. Review, edit, and send — keeping your team's authentic voice with zero friction.</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)
    st.stop()

if st.session_state.page == "About":
    st.markdown("""
    <div style="max-width:1000px;margin:0 auto;">
    <div class="eyebrow" style="margin-bottom:14px;">ABOUT HELIOS</div>
    <h1 style="font-size:clamp(2rem,4.5vw,3.4rem);margin-bottom:12px;">
        Clarity for <span class="gradient-text">customer teams.</span>
    </h1>
    <p class="subtitle" style="font-size:1.1rem;">Helios brings triage, context, and customer communication into one refined workspace.</p>
    </div>
    <div class="hr-fancy"></div>
    """, unsafe_allow_html=True)

    about_left, about_right = st.columns(2, gap="large")
    with about_left:
        st.markdown("""
        <div class="glass-card" style="padding:36px;border-radius:24px;">
            <div style="display:flex;align-items:center;gap:12px;margin-bottom:18px;">
                <div style="width:46px;height:46px;border-radius:14px;background:linear-gradient(135deg,#6366f1,#7c3aed);display:flex;align-items:center;justify-content:center;font-family:'Space Grotesk',sans-serif;font-weight:700;color:#fff;font-size:1.1rem;box-shadow:0 6px 16px rgba(99,102,241,0.3);">Q</div>
                <h2 style="margin:0;font-size:1.35rem;">One queue, less noise.</h2>
            </div>
            <p style="line-height:1.75;color:var(--muted);margin:0 0 18px;">
                Tickets stay searchable, status changes stay visible, and notes stay attached to the very conversation they explain. Your team never loses context.
            </p>
            <div class="hr-fancy" style="margin:14px 0;"></div>
            <div style="display:flex;align-items:center;gap:12px;margin-bottom:12px;">
                <div style="width:38px;height:38px;border-radius:11px;background:linear-gradient(135deg,#f59e0b,#f97316);display:flex;align-items:center;justify-content:center;font-family:'Space Grotesk',sans-serif;font-weight:700;color:#fff;font-size:.9rem;">M</div>
                <h3 style="margin:0;font-size:1.1rem;">Designed for momentum</h3>
            </div>
            <p style="line-height:1.7;color:var(--muted);margin:0;">
                Move from a new issue to a clear next action without losing the details that matter. Fewer clicks, clearer context, faster resolution.
            </p>
            <div style="margin-top:24px;padding:14px 18px;background:linear-gradient(135deg,rgba(99,102,241,0.08),rgba(168,85,247,0.06));border:1px solid rgba(99,102,241,0.15);border-radius:14px;">
                <div style="font-weight:700;color:var(--ink);font-size:0.92rem;margin-bottom:4px;">PRO TIP</div>
                <div style="font-size:0.85rem;color:var(--muted);line-height:1.55;">Use the App / CRM page to dive into tickets, manage statuses, and draft AI replies — all from one designed screen.</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    with about_right:
        st.markdown("""
        <div class="glass-card" style="padding:36px;border-radius:24px;">
            <div style="display:flex;align-items:center;gap:12px;margin-bottom:18px;">
                <div style="width:46px;height:46px;border-radius:14px;background:linear-gradient(135deg,#ec4899,#f97316);display:flex;align-items:center;justify-content:center;font-family:'Space Grotesk',sans-serif;font-weight:700;color:#fff;font-size:1.1rem;box-shadow:0 6px 16px rgba(236,72,153,0.3);">AI</div>
                <h2 style="margin:0;font-size:1.35rem;">AI with a human handoff.</h2>
            </div>
            <p style="line-height:1.75;color:var(--muted);margin:0 0 18px;">
                OpenRouter drafts are placed directly in the response editor for review. Your team stays in control — nothing gets saved or sent without explicit approval.
            </p>
            <div class="hr-fancy" style="margin:14px 0;"></div>
            <div style="display:flex;align-items:center;gap:12px;margin-bottom:12px;">
                <div style="width:38px;height:38px;border-radius:11px;background:linear-gradient(135deg,#06b6d4,#10b981);display:flex;align-items:center;justify-content:center;font-family:'Space Grotesk',sans-serif;font-weight:700;color:#fff;font-size:.9rem;">S</div>
                <h3 style="margin:0;font-size:1.1rem;">Simple by design</h3>
            </div>
            <p style="line-height:1.7;color:var(--muted);margin:0;">
                The dashboard uses session storage for this lightweight prototype, making it easy to run, test, and extend as needed.
            </p>
            <div style="margin-top:24px;padding:14px 18px;background:linear-gradient(135deg,rgba(16,185,129,0.08),rgba(6,182,212,0.06));border:1px solid rgba(16,185,129,0.15);border-radius:14px;">
                <div style="font-weight:700;color:var(--ink);font-size:0.92rem;margin-bottom:4px;">ROLE-BASED ACCESS</div>
                <div style="font-size:0.85rem;color:var(--muted);line-height:1.55;">Admins see all tickets, notes, and AI tools. Customer accounts see only their own tickets and replies.</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)
    st.stop()


openrouter_api_key = get_openrouter_api_key()

with st.sidebar:
    user_initial = current_user["username"][0].upper() if current_user.get("username") else "U"
    st.markdown(f"""
    <div style="padding:4px 0 8px;">
        <div class="brand-logo">
            <div class="brand-logo-mark">H</div>
            <div>
                <div class="brand-title-text">Helios</div>
                <div class="brand-subtitle">Ticket Intelligence</div>
            </div>
        </div>
    </div>
    <div class="sidebar-user-badge">
        <div class="sidebar-user-avatar">{user_initial}</div>
        <div class="sidebar-user-info" style="flex:1;">
            <div style="display:flex;align-items:center;gap:6px;">
                <div class="sidebar-user-name">{current_user['username']}</div>
                <div class="sidebar-status-dot"></div>
            </div>
            <div class="sidebar-user-role">{user_role}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    if st.button("Log out", use_container_width=True):
        st.session_state.authenticated = False
        st.rerun()

    st.markdown("<div class='gradient-divider'></div>", unsafe_allow_html=True)

    st.markdown("<h3 style='font-size:1.05rem;margin:0 0 10px;'>Raise a ticket</h3>", unsafe_allow_html=True)
    with st.form("create_ticket_form", clear_on_submit=True):
        cust_name = st.text_input("Customer name", placeholder="Alex Morgan")
        cust_email = st.text_input("Email", placeholder="alex@example.com")
        subject = st.text_input("Subject", placeholder="Unable to update billing details")
        description = st.text_area("Description", placeholder="Tell us what happened...", height=100)
        priority = st.selectbox("Priority", ["Low", "Medium", "Urgent"])
        category = st.selectbox("Category", ["Billing", "General", "Technical"])
        create_submitted = st.form_submit_button("Create ticket", use_container_width=True)

    if user_role == "admin" and openrouter_api_key:
        st.markdown(f"""
        <div style="margin-top:14px;padding:11px 15px;background:linear-gradient(135deg,rgba(16,185,129,0.1),rgba(6,182,212,0.06));border:1px solid rgba(16,185,129,0.2);border-radius:12px;display:flex;align-items:center;gap:10px;">
            <span style="width:9px;height:9px;border-radius:50%;background:#10b981;box-shadow:0 0 0 3px rgba(16,185,129,.18);flex-shrink:0;"></span>
            <div style="font-size:0.8rem;line-height:1.4;">
                <div style="font-weight:700;color:#065f46;">OpenRouter ready</div>
                <div style="color:var(--muted);font-size:0.74rem;">{openrouter_api_key[:8]}... · AI drafts available</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    elif user_role == "admin":
        st.error("OPENROUTER_API_KEY is not configured for AI drafts.")

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


total_count = len(st.session_state.tickets)
open_count = sum(ticket["status"] == "Open" for ticket in st.session_state.tickets)
progress_count = sum(ticket["status"] == "In Progress" for ticket in st.session_state.tickets)
closed_count = sum(ticket["status"] == "Closed" for ticket in st.session_state.tickets)

st.markdown("""
<div class="eyebrow">OPERATIONS CONSOLE</div>
<h1 style="margin-top:12px;margin-bottom:8px;font-size:clamp(1.8rem,3.5vw,2.8rem);">
    Ticket <span class="gradient-text">command center</span>
</h1>
<p class="subtitle" style="margin-bottom:22px;">A focused workspace for triage, customer context, and faster resolution.</p>
""", unsafe_allow_html=True)

m1, m2, m3, m4 = st.columns(4)

with m1:
    st.markdown(f"""
    <div data-testid="stMetric" style="position:relative;overflow:hidden;background:linear-gradient(135deg,rgba(255,255,255,.9),rgba(255,255,255,.6));backdrop-filter:blur(20px);border:1px solid rgba(255,255,255,.8);box-shadow:0 8px 32px rgba(11,16,32,.07);padding:22px 24px;border-radius:20px;">
        <div style="position:absolute;top:0;left:0;right:0;height:4px;background:linear-gradient(90deg,#6366f1,#8b5cf6,#a855f7);"></div>
        <div class="metric-icon-ring" style="background:linear-gradient(135deg,#6366f1,#a855f7);">T</div>
        <div style="font-size:0.7rem;font-weight:700;letter-spacing:0.16em;text-transform:uppercase;color:var(--muted);font-family:'Inter',sans-serif;">TOTAL TICKETS</div>
        <div style="font-family:'Space Grotesk',sans-serif;font-weight:700;font-size:2.2rem;letter-spacing:-0.02em;color:var(--ink);margin-top:4px;">{total_count}</div>
    </div>
    """, unsafe_allow_html=True)
with m2:
    st.markdown(f"""
    <div data-testid="stMetric" style="position:relative;overflow:hidden;background:linear-gradient(135deg,rgba(255,255,255,.9),rgba(255,255,255,.6));backdrop-filter:blur(20px);border:1px solid rgba(255,255,255,.8);box-shadow:0 8px 32px rgba(11,16,32,.07);padding:22px 24px;border-radius:20px;">
        <div style="position:absolute;top:0;left:0;right:0;height:4px;background:linear-gradient(90deg,#3b82f6,#60a5fa);"></div>
        <div class="metric-icon-ring" style="background:linear-gradient(135deg,#3b82f6,#60a5fa);">O</div>
        <div style="font-size:0.7rem;font-weight:700;letter-spacing:0.16em;text-transform:uppercase;color:var(--muted);font-family:'Inter',sans-serif;">OPEN</div>
        <div style="font-family:'Space Grotesk',sans-serif;font-weight:700;font-size:2.2rem;letter-spacing:-0.02em;color:var(--ink);margin-top:4px;">{open_count}</div>
    </div>
    """, unsafe_allow_html=True)
with m3:
    st.markdown(f"""
    <div data-testid="stMetric" style="position:relative;overflow:hidden;background:linear-gradient(135deg,rgba(255,255,255,.9),rgba(255,255,255,.6));backdrop-filter:blur(20px);border:1px solid rgba(255,255,255,.8);box-shadow:0 8px 32px rgba(11,16,32,.07);padding:22px 24px;border-radius:20px;">
        <div style="position:absolute;top:0;left:0;right:0;height:4px;background:linear-gradient(90deg,#f59e0b,#fbbf24);"></div>
        <div class="metric-icon-ring" style="background:linear-gradient(135deg,#f59e0b,#fbbf24);">P</div>
        <div style="font-size:0.7rem;font-weight:700;letter-spacing:0.16em;text-transform:uppercase;color:var(--muted);font-family:'Inter',sans-serif;">IN PROGRESS</div>
        <div style="font-family:'Space Grotesk',sans-serif;font-weight:700;font-size:2.2rem;letter-spacing:-0.02em;color:var(--ink);margin-top:4px;">{progress_count}</div>
    </div>
    """, unsafe_allow_html=True)
with m4:
    st.markdown(f"""
    <div data-testid="stMetric" style="position:relative;overflow:hidden;background:linear-gradient(135deg,rgba(255,255,255,.9),rgba(255,255,255,.6));backdrop-filter:blur(20px);border:1px solid rgba(255,255,255,.8);box-shadow:0 8px 32px rgba(11,16,32,.07);padding:22px 24px;border-radius:20px;">
        <div style="position:absolute;top:0;left:0;right:0;height:4px;background:linear-gradient(90deg,#10b981,#34d399);"></div>
        <div class="metric-icon-ring" style="background:linear-gradient(135deg,#10b981,#34d399);">C</div>
        <div style="font-size:0.7rem;font-weight:700;letter-spacing:0.16em;text-transform:uppercase;color:var(--muted);font-family:'Inter',sans-serif;">CLOSED</div>
        <div style="font-family:'Space Grotesk',sans-serif;font-weight:700;font-size:2.2rem;letter-spacing:-0.02em;color:var(--ink);margin-top:4px;">{closed_count}</div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("<div class='gradient-divider'></div>", unsafe_allow_html=True)

col_queue, col_detail = st.columns([1.1, 1.5], gap="large")

with col_queue:
    st.markdown(f"""
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px;">
        <div style="display:flex;align-items:center;gap:10px;">
            <div style="width:34px;height:34px;border-radius:11px;background:linear-gradient(135deg,#6366f1,#7c3aed);display:flex;align-items:center;justify-content:center;font-family:'Space Grotesk',sans-serif;font-weight:700;color:#fff;font-size:.9rem;box-shadow:0 4px 12px rgba(99,102,241,0.3);">Q</div>
            <h3 style="margin:0;font-size:1.15rem;">Ticket queue</h3>
        </div>
        <div style="font-size:0.8rem;color:var(--muted);font-weight:600;">{total_count} tickets</div>
    </div>
    <div style="font-size:0.82rem;color:var(--muted);margin-bottom:14px;">Select a ticket to open its details, actions, notes, and AI reply tools.</div>
    """, unsafe_allow_html=True)

    for ticket in st.session_state.tickets:
        initials = ''.join([n[0].upper() for n in ticket["customer"].split()[:2]]) if ticket["customer"] else "?"
        st.markdown(f"""
        <div class="ticket-card" data-priority="{ticket['priority']}">
            <div style="padding-left:4px;">
                <div class="ticket-mono">
                    <span class="ticket-id">#{ticket['id']}</span>
                    <div class="monogram" style="background:linear-gradient(135deg,#6366f1,#a855f7);">{initials}</div>
                </div>
                <div class="ticket-subject">{ticket['subject']}</div>
                <div class="ticket-meta">
                    <span style="width:7px;height:7px;border-radius:50%;background:#94a3b8;"></span>
                    <span>{ticket['customer']}</span>
                    <span style="opacity:0.3;">·</span>
                    <span>{ticket['category']}</span>
                </div>
                <div style="display:flex;flex-wrap:wrap;gap:4px;margin-top:8px;">
                    <span class="status-pill status-{ticket['status'].split()[0]}"><span class="pill-dot"></span>{ticket['status']}</span>
                    <span class="priority-pill priority-{ticket['priority']}"><span class="pill-dot"></span>{ticket['priority']}</span>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        if st.button(f"Open {ticket['id']}", key=f"open-{ticket['id']}", use_container_width=True):
            st.session_state.selected_ticket_id = ticket["id"]
            st.session_state.draft_text = ""
            st.rerun()


with col_detail:
    selected_id = st.session_state.get("selected_ticket_id")
    selected_ticket = next((ticket for ticket in st.session_state.tickets if ticket["id"] == selected_id), None)

    if selected_ticket is None:
        st.markdown("""
        <div class="glass-card" style="padding:56px 40px;text-align:center;border-radius:26px;">
            <div class="empty-symbol" style="width:88px;height:88px;border-radius:26px;font-size:1.6rem;margin:0 auto 20px;">D</div>
            <div class="eyebrow" style="margin-bottom:14px;justify-content:center;">TICKET DETAILS</div>
            <h2 style="font-size:1.6rem;margin:0 0 10px;">Select a ticket</h2>
            <p class="muted" style="font-size:1rem;line-height:1.65;margin:0 auto;max-width:400px;">Choose a ticket from the queue on the left to open its details, actions, notes, and AI-powered reply tools.</p>
            <div style="margin-top:28px;display:flex;gap:10px;justify-content:center;flex-wrap:wrap;">
                <div class="quick-chip"><span style="width:7px;height:7px;border-radius:50%;background:#3b82f6;"></span> Status updates</div>
                <div class="quick-chip"><span style="width:7px;height:7px;border-radius:50%;background:#7c3aed;"></span> AI drafts</div>
                <div class="quick-chip"><span style="width:7px;height:7px;border-radius:50%;background:#a855f7;"></span> Notes</div>
                <div class="quick-chip"><span style="width:7px;height:7px;border-radius:50%;background:#06b6d4;"></span> Replies</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    else:
        initials = ''.join([n[0].upper() for n in selected_ticket["customer"].split()[:2]]) if selected_ticket["customer"] else "?"
        st.markdown(f"""
        <div style="display:flex;align-items:center;gap:10px;margin-bottom:12px;">
            <div style="width:34px;height:34px;border-radius:11px;background:linear-gradient(135deg,#06b6d4,#10b981);display:flex;align-items:center;justify-content:center;font-family:'Space Grotesk',sans-serif;font-weight:700;color:#fff;font-size:.9rem;box-shadow:0 4px 12px rgba(6,182,212,0.3);">D</div>
            <h3 style="margin:0;font-size:1.15rem;">Ticket details</h3>
        </div>
        <div class="glass-card" style="padding:24px;border-radius:22px;">
            <div class="ticket-details-header">
                <div class="ticket-details-left">
                    <div class="ticket-details-avatar">{initials}</div>
                    <div>
                        <div style="font-family:'Space Grotesk',sans-serif;font-weight:700;font-size:0.82rem;color:#4f46e5;letter-spacing:0.02em;margin-bottom:4px;">#{selected_ticket['id']}</div>
                        <h2 style="margin:0;font-size:1.35rem;line-height:1.25;">{selected_ticket['subject']}</h2>
                    </div>
                </div>
            </div>
            <div style="display:flex;flex-wrap:wrap;gap:6px;margin:14px 0;">
                <span class="status-pill status-{selected_ticket['status'].split()[0]}"><span class="pill-dot"></span>{selected_ticket['status']}</span>
                <span class="priority-pill priority-{selected_ticket['priority']}"><span class="pill-dot"></span>{selected_ticket['priority']}</span>
                <span class="category-pill category-{selected_ticket['category']}">{selected_ticket['category']}</span>
            </div>
            <div class="detail-grid">
                <div>
                    <div class="detail-label">Customer</div>
                    <div class="detail-value">{selected_ticket['customer']}</div>
                </div>
                <div>
                    <div class="detail-label">Email</div>
                    <div class="detail-value" style="word-break:break-all;">{selected_ticket['email']}</div>
                </div>
            </div>
            <div style="margin-top:6px;">
                <div class="detail-label">Description</div>
                <div class="description-box">{selected_ticket['description']}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        if user_role == "admin":
            status_options = ["Open", "In Progress", "Closed"]
            current_status_index = status_options.index(selected_ticket["status"]) if selected_ticket["status"] in status_options else 0
            new_status = st.selectbox("Ticket status", status_options, index=current_status_index, key=f"status-{selected_ticket['id']}")
            if new_status != selected_ticket["status"]:
                with database_connection() as connection:
                    connection.execute("UPDATE tickets SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE ticket_id = ?", (new_status, selected_ticket["id"]))
                st.rerun()

            st.markdown("""
            <div class="section-header">
                <div class="section-header-icon">R</div>
                <h3>Add a note or reply</h3>
            </div>
            """, unsafe_allow_html=True)

            if st.button("Draft AI response", use_container_width=True):
                with st.spinner("Asking OpenRouter for a thoughtful draft..."):
                    st.session_state.draft_text = generate_ai_draft(selected_ticket["customer"], selected_ticket["subject"], selected_ticket["description"])

            note_input = st.text_area("Response draft", value=st.session_state.get("draft_text", ""), height=180, placeholder="Write a thoughtful reply or note...")
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

            st.markdown("""
            <div class="section-header">
                <div class="section-header-icon" style="background:linear-gradient(135deg,rgba(6,182,212,0.12),rgba(16,185,129,0.12));color:#0e7490;">S</div>
                <h3>Customer replies</h3>
            </div>
            """, unsafe_allow_html=True)
            if selected_ticket.get("replies"):
                for reply in reversed(selected_ticket["replies"]):
                    emailed_badge = f'<span class="email-badge"><span class="badge-check"></span> Emailed</span>' if reply['emailed'] else f'<span class="no-email-badge">Local only</span>'
                    st.markdown(f"""
                    <div class="note-card note-card-reply">
                        <div class="reply-note-meta">
                            <div class="reply-note-author">
                                <span>R</span>
                                <span>Reply to customer</span>
                            </div>
                            <div style="display:flex;align-items:center;gap:8px;">
                                {emailed_badge}
                                <div class="reply-note-time">{reply['time']}</div>
                            </div>
                        </div>
                        <div style="line-height:1.65;color:var(--ink2);white-space:pre-wrap;">{reply['text']}</div>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.markdown("""
                <div class="empty-state">
                    <div class="empty-symbol">S</div>
                    <div class="empty-title">No replies sent yet</div>
                    <div class="empty-sub">Use the form above to craft and send a reply to the customer.</div>
                </div>
                """, unsafe_allow_html=True)

            st.markdown("""
            <div class="section-header">
                <div class="section-header-icon" style="background:linear-gradient(135deg,rgba(168,85,247,0.12),rgba(236,72,153,0.10));color:#7e22ce;">N</div>
                <h3>Internal notes</h3>
            </div>
            """, unsafe_allow_html=True)
            if selected_ticket["notes"]:
                for note in reversed(selected_ticket["notes"]):
                    st.markdown(f"""
                    <div class="note-card note-card-note">
                        <div class="reply-note-meta">
                            <div class="reply-note-author">
                                <span>N</span>
                                <span>Internal note</span>
                            </div>
                            <div class="reply-note-time">Team only</div>
                        </div>
                        <div style="line-height:1.65;color:var(--ink2);white-space:pre-wrap;">{note}</div>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.markdown("""
                <div class="empty-state" style="border-color:rgba(168,85,247,0.25);">
                    <div class="empty-symbol">N</div>
                    <div class="empty-title">No internal notes yet</div>
                    <div class="empty-sub">Save context, decisions, or follow-up items here for your team.</div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div class="glass-card" style="padding:24px;border-radius:22px;margin-top:14px;">
                <div style="display:flex;align-items:center;gap:12px;margin-bottom:14px;">
                    <div style="width:48px;height:48px;border-radius:14px;background:linear-gradient(135deg,#10b981,#06b6d4);display:flex;align-items:center;justify-content:center;font-family:'Space Grotesk',sans-serif;font-weight:700;color:#fff;font-size:1.1rem;box-shadow:0 6px 16px rgba(16,185,129,0.3);">i</div>
                    <div>
                        <div class="eyebrow" style="margin-bottom:4px;">Current status</div>
                        <h2 style="margin:0;font-size:1.5rem;">{selected_ticket['status']}</h2>
                    </div>
                </div>
                <p class="muted" style="font-size:0.98rem;line-height:1.7;margin:0;">Your support team is actively reviewing this ticket. Replies from the team will appear below as they become available.</p>
            </div>
            """, unsafe_allow_html=True)

            st.markdown("""
            <div class="section-header">
                <div class="section-header-icon" style="background:linear-gradient(135deg,rgba(6,182,212,0.12),rgba(16,185,129,0.12));color:#0e7490;">S</div>
                <h3>Support replies</h3>
            </div>
            """, unsafe_allow_html=True)
            if selected_ticket.get("replies"):
                for reply in reversed(selected_ticket["replies"]):
                    st.markdown(f"""
                    <div class="note-card note-card-reply">
                        <div class="reply-note-meta">
                            <div class="reply-note-author">
                                <span>R</span>
                                <span>From support team</span>
                            </div>
                            <div class="reply-note-time">{reply['time']}</div>
                        </div>
                        <div style="line-height:1.65;color:var(--ink2);white-space:pre-wrap;">{reply['text']}</div>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.markdown("""
                <div class="empty-state">
                    <div class="empty-symbol">T</div>
                    <div class="empty-title">No replies yet</div>
                    <div class="empty-sub">The support team is working on your ticket. Check back soon for updates.</div>
                </div>
                """, unsafe_allow_html=True)

st.markdown("</div>", unsafe_allow_html=True)
