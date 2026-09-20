import json
import os
from urllib import request

import dotenv
import streamlit as st

dotenv.load_dotenv()

st.set_page_config(
    page_title="CRM Ticket Intelligence",
    page_icon="🎫",
    layout="wide",
)

if "tickets" not in st.session_state:
    st.session_state.tickets = [
        {
            "id": "TKT-9557",
            "customer": "Alex Morgan",
            "email": "alex@example.com",
            "subject": "Critical payment outage",
            "description": "The billing API is down and broken. Unable to update billing details.",
            "status": "Closed",
            "priority": "Urgent",
            "category": "Billing",
            "notes": ["not working", "knkjlfs"],
        },
        {
            "id": "TKT-7965",
            "customer": "Alex Morgan",
            "email": "alex@example.com",
            "subject": "Critical payment outage",
            "description": "The billing API is down and broken",
            "status": "Open",
            "priority": "Urgent",
            "category": "Billing",
            "notes": [],
        },
        {
            "id": "TKT-7948",
            "customer": "Tejas Kamble",
            "email": "tejas@example.com",
            "subject": "unable to bill",
            "description": "Getting payment process errors during checkout.",
            "status": "Open",
            "priority": "Medium",
            "category": "General",
            "notes": [],
        },
    ]


def get_openrouter_api_key():
    try:
        value = st.secrets.get("OPENROUTER_API_KEY")
        if value:
            return str(value).strip()
    except Exception:
        pass

    value = os.getenv("OPENROUTER_API_KEY")
    if value:
        return str(value).strip()

    return None


def call_openrouter(prompt: str, api_key: str) -> str:
    payload = {
        "model": "openai/gpt-4o-mini",
        "messages": [{"role": "user", "content": prompt}],
    }
    data = json.dumps(payload).encode("utf-8")
    req = request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=data,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost:8501",
            "X-Title": "Support Ticket CRM",
        },
        method="POST",
    )
    with request.urlopen(req, timeout=60) as response:
        body = json.loads(response.read().decode("utf-8"))
    return str(body["choices"][0]["message"]["content"]).strip()


openrouter_api_key = get_openrouter_api_key()

if openrouter_api_key:
    st.sidebar.warning(f"Detected OpenRouter API Key: {openrouter_api_key[:8]}...")
else:
    st.sidebar.error("OPENROUTER_API_KEY is not configured.")


def generate_ai_draft(customer_name, subject, description):
    if not openrouter_api_key:
        return "OpenRouter API key is not configured."

    prompt = f"""
You are an expert customer support agent. Draft a helpful, empathetic, and professional email response to the following customer complaint.

Customer Name: {customer_name}
Subject: {subject}
Issue Details: {description}

Requirements:
1. Address {customer_name} directly.
2. Specifically address the exact issue mentioned ({description}) and detail the resolution steps being taken.
3. Keep it professional, reassuring, and concise (under 150 words). Do not include placeholders like [Your Name].
"""

    try:
        return call_openrouter(prompt, openrouter_api_key)
    except Exception as e:
        error_message = f"OpenRouter API error: {e}"
        print(error_message)
        return error_message


st.sidebar.header("New Ticket")
with st.sidebar.form("create_ticket_form"):
    cust_name = st.text_input("Customer name")
    cust_email = st.text_input("Email")
    subject = st.text_input("Subject")
    description = st.text_area("Description")
    priority = st.selectbox("Priority", ["Low", "Medium", "Urgent"])
    category = st.selectbox("Category", ["Billing", "General", "Technical"])
    submitted = st.form_submit_button("Create ticket")

if submitted and cust_name and subject:
    new_id = f"TKT-{len(st.session_state.tickets) + 7000}"
    st.session_state.tickets.append(
        {
            "id": new_id,
            "customer": cust_name,
            "email": cust_email,
            "subject": subject,
            "description": description,
            "status": "Open",
            "priority": priority,
            "category": category,
            "notes": [],
        }
    )
    st.sidebar.success(f"Created ticket {new_id}!")
    st.rerun()

st.title("Ticket Command Center")

total_count = len(st.session_state.tickets)
open_count = len([t for t in st.session_state.tickets if t["status"] == "Open"])
progress_count = len([t for t in st.session_state.tickets if t["status"] == "In Progress"])
closed_count = len([t for t in st.session_state.tickets if t["status"] == "Closed"])

m1, m2, m3, m4 = st.columns(4)
m1.metric("TOTAL", total_count)
m2.metric("OPEN", open_count)
m3.metric("IN PROGRESS", progress_count)
m4.metric("CLOSED", closed_count)

st.divider()
col_queue, col_detail = st.columns([3, 2])

with col_queue:
    st.subheader("Ticket Queue")
    ticket_ids = [f"{t['id']} - {t['subject']} ({t['customer']})" for t in st.session_state.tickets]
    selected_ticket_str = st.radio("Select a ticket to view details:", ticket_ids)
    selected_id = selected_ticket_str.split(" - ")[0]
    selected_ticket = next(t for t in st.session_state.tickets if t["id"] == selected_id)

with col_detail:
    st.subheader("Ticket Details")
    st.markdown(f"CUSTOMER: {selected_ticket['customer']} ({selected_ticket['email']})")
    st.markdown(f"DESCRIPTION: {selected_ticket['description']}")
    st.markdown(f"CURRENT STATUS: {selected_ticket['status']}")

    c1, c2 = st.columns(2)
    if c1.button("Mark In Progress"):
        selected_ticket["status"] = "In Progress"
        st.rerun()
    if c2.button("Close Ticket"):
        selected_ticket["status"] = "Closed"
        st.rerun()

    st.divider()
    st.markdown("### Add a Note / Reply")

    if st.button("🤖 Draft AI Response"):
        ai_reply = generate_ai_draft(
            selected_ticket["customer"],
            selected_ticket["subject"],
            selected_ticket["description"],
        )
        st.session_state["draft_text"] = ai_reply

    note_input = st.text_area(
        "Response Draft:",
        value=st.session_state.get("draft_text", ""),
        height=150,
    )

    if st.button("Save Note"):
        if note_input.strip():
            selected_ticket["notes"].append(note_input)
            st.session_state["draft_text"] = ""
            st.success("Note saved!")
            st.rerun()

    if selected_ticket["notes"]:
        st.markdown("#### Saved Notes")
        for note in reversed(selected_ticket["notes"]):
            st.info(note)
