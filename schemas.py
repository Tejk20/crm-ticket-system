from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

ALLOWED_STATUSES = ("Open", "In Progress", "Closed")
ALLOWED_PRIORITIES = ("Urgent", "High", "Medium", "Low")


class TicketCreate(BaseModel):
    customer_name: str = Field(min_length=1, max_length=120)
    customer_email: EmailStr
    subject: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1)


class TicketCreateResponse(BaseModel):
    ticket_id: str
    priority: str
    category: str
    created_at: datetime


class TicketListItem(BaseModel):
    ticket_id: str
    customer_name: str
    subject: str
    status: str
    priority: str
    category: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class NoteResponse(BaseModel):
    note_text: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TicketDetail(BaseModel):
    ticket_id: str
    customer_name: str
    customer_email: str
    subject: str
    description: str
    status: str
    priority: str
    category: str
    created_at: datetime
    updated_at: datetime
    notes: list[NoteResponse]

    model_config = ConfigDict(from_attributes=True)


class TicketUpdate(BaseModel):
    status: str | None = None
    notes: str | None = Field(default=None, max_length=5000)


class TicketUpdateResponse(BaseModel):
    success: bool
    updated_at: datetime
    priority: str
    category: str


class DraftReplyResponse(BaseModel):
    draft_reply: str
