from dotenv import load_dotenv

load_dotenv(override=True)

import json
import os
import random
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from urllib import error, request

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload
from database import Base, engine, get_db
from models import Note, Ticket
from schemas import (
    ALLOWED_STATUSES,
    ALLOWED_PRIORITIES,
    TicketCreate,
    TicketCreateResponse,
    TicketDetail,
    TicketListItem,
    TicketUpdate,
    TicketUpdateResponse,
    DraftReplyResponse,
)

print(f"OPENROUTER_API_KEY found at startup: {bool(os.getenv('OPENROUTER_API_KEY'))}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    # Add new fields to databases created by older versions without losing tickets.
    with engine.begin() as connection:
        columns = {row[1] for row in connection.exec_driver_sql("PRAGMA table_info(tickets)")}
        if "priority" not in columns:
            connection.exec_driver_sql("ALTER TABLE tickets ADD COLUMN priority VARCHAR(20) NOT NULL DEFAULT 'Medium'")
        if "category" not in columns:
            connection.exec_driver_sql("ALTER TABLE tickets ADD COLUMN category VARCHAR(30) NOT NULL DEFAULT 'General'")
    yield


app = FastAPI(title="Support Ticket CRM", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")


def classify_ticket(subject: str, description: str) -> tuple[str, str]:
    text = f"{subject} {description}".lower()
    if any(keyword in text for keyword in ("down", "outage", "urgent", "critical", "broken", "emergency")):
        priority = "Urgent"
    elif any(keyword in text for keyword in ("billing", "error", "payment", "refund", "failed")):
        priority = "High"
    elif any(keyword in text for keyword in ("question", "info", "feature", "how to")):
        priority = "Low"
    else:
        priority = "Medium"

    if any(keyword in text for keyword in ("invoice", "payment", "refund", "subscription")):
        category = "Billing"
    elif any(keyword in text for keyword in ("bug", "error", "broken", "api", "crash")):
        category = "Technical"
    elif any(keyword in text for keyword in ("password", "email", "profile", "access")):
        category = "Account"
    else:
        category = "General"
    return priority, category


def generate_ticket_id(db: Session) -> str:
    for _ in range(10):
        candidate = f"TKT-{random.randint(1000, 9999)}"
        if db.scalar(select(Ticket.id).where(Ticket.ticket_id == candidate)) is None:
            return candidate
    latest_id = db.scalar(select(Ticket.id).order_by(Ticket.id.desc()).limit(1)) or 0
    return f"TKT-{1000 + latest_id + 1}"


def get_ticket_or_404(db: Session, ticket_id: str) -> Ticket:
    ticket = db.scalar(
        select(Ticket).options(selectinload(Ticket.notes)).where(Ticket.ticket_id == ticket_id)
    )
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket


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
            "HTTP-Referer": "http://localhost:8002",
            "X-Title": "Support Ticket CRM",
        },
        method="POST",
    )
    with request.urlopen(req, timeout=60) as response:
        body = json.loads(response.read().decode("utf-8"))
    message = body["choices"][0]["message"]["content"]
    return str(message).strip()


@app.get("/", include_in_schema=False)
def serve_app():
    return FileResponse(Path(__file__).parent / "static" / "index.html")


@app.post(
    "/api/tickets",
    response_model=TicketCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_ticket(payload: TicketCreate, db: Session = Depends(get_db)):
    subject = payload.subject.strip()
    description = payload.description.strip()
    priority, category = classify_ticket(subject, description)
    ticket = Ticket(
        ticket_id=generate_ticket_id(db),
        customer_name=payload.customer_name.strip(),
        customer_email=str(payload.customer_email).lower(),
        subject=subject,
        description=description,
        status="Open",
        priority=priority,
        category=category,
    )
    if not all((ticket.customer_name, ticket.subject, ticket.description)):
        raise HTTPException(status_code=422, detail="Name, subject, and description cannot be blank")

    db.add(ticket)
    try:
        db.commit()
        db.refresh(ticket)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Could not create a unique ticket") from exc
    return ticket


@app.get("/api/tickets", response_model=list[TicketListItem])
def list_tickets(
    status_filter: str | None = Query(default=None, alias="status"),
    priority_filter: str | None = Query(default=None, alias="priority"),
    search: str | None = Query(default=None, max_length=200),
    db: Session = Depends(get_db),
):
    query = select(Ticket)
    if status_filter:
        if status_filter not in ALLOWED_STATUSES:
            raise HTTPException(status_code=400, detail="Invalid status filter")
        query = query.where(Ticket.status == status_filter)
    if priority_filter:
        if priority_filter not in ALLOWED_PRIORITIES:
            raise HTTPException(status_code=400, detail="Invalid priority filter")
        query = query.where(Ticket.priority == priority_filter)
    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.where(
            or_(
                Ticket.customer_name.ilike(term),
                Ticket.customer_email.ilike(term),
                Ticket.ticket_id.ilike(term),
                Ticket.subject.ilike(term),
                Ticket.description.ilike(term),
            )
        )
    return db.scalars(query.order_by(Ticket.created_at.desc())).all()


@app.get("/api/tickets/{ticket_id}", response_model=TicketDetail)
def get_ticket(ticket_id: str, db: Session = Depends(get_db)):
    return get_ticket_or_404(db, ticket_id)


@app.post("/api/tickets/{ticket_id}/generate-reply", response_model=DraftReplyResponse)
def generate_reply(ticket_id: str, db: Session = Depends(get_db)):
    ticket = get_ticket_or_404(db, ticket_id)

    openrouter_key = "".join((os.getenv("OPENROUTER_API_KEY") or "").split())

    notes_context = "\n".join(f"- {note.note_text}" for note in ticket.notes) or "No previous internal notes."
    prompt = (
        "You are an expert customer support agent. Draft a concise, friendly, and professional response "
        "resolving this customer ticket.\n"
        f"Customer name: {ticket.customer_name}\n"
        f"Subject: {ticket.subject}\n"
        f"Description: {ticket.description}\n"
        f"Category: {ticket.category}\n"
        f"Priority: {ticket.priority}\n"
        f"Past internal notes:\n{notes_context}\n"
        "Address the customer by the provided name. Return only the response, without a subject line, "
        "meta-commentary, placeholders, bracketed text, or signatures such as [Your Name]."
    )

    if not openrouter_key:
        raise HTTPException(status_code=503, detail="OPENROUTER_API_KEY is not configured")

    try:
        draft_reply = call_openrouter(prompt, openrouter_key)
        if draft_reply:
            return {"draft_reply": draft_reply}
        raise RuntimeError("OpenRouter returned an empty response")
    except Exception as exc:
        print(f"OpenRouter request failed for {ticket_id}: {type(exc).__name__}: {str(exc)[:300]}")
        raise HTTPException(status_code=502, detail=f"OpenRouter API error: {str(exc)}") from exc


@app.put("/api/tickets/{ticket_id}", response_model=TicketUpdateResponse)
def update_ticket(ticket_id: str, payload: TicketUpdate, db: Session = Depends(get_db)):
    ticket = get_ticket_or_404(db, ticket_id)
    if payload.status is not None:
        if payload.status not in ALLOWED_STATUSES:
            raise HTTPException(status_code=400, detail="Invalid ticket status")
        ticket.status = payload.status
    if payload.notes is not None:
        note_text = payload.notes.strip()
        if note_text:
            db.add(Note(ticket_id=ticket.ticket_id, note_text=note_text))
    ticket.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(ticket)
    return {
        "success": True,
        "updated_at": ticket.updated_at,
        "priority": ticket.priority,
        "category": ticket.category,
    }
