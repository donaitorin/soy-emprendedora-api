import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.task import SuggestionType, TaskPriority


class TaskCreate(BaseModel):
    title: str
    notes: str | None = None
    priority: TaskPriority
    suggestion_type: SuggestionType | None = None
    conversation_ref: str | None = None


class TaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    account_id: uuid.UUID
    title: str
    notes: str | None
    priority: TaskPriority
    done: bool
    suggestion_type: SuggestionType | None
    conversation_ref: str | None
    created_at: datetime


class TaskUpdate(BaseModel):
    done: bool
