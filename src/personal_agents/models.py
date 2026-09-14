from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class AgentName(StrEnum):
    MAIN = "main"
    EMAIL = "email"
    RESEARCH = "research"
    BUSINESS = "business"


class TaskStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class MessageKind(StrEnum):
    ASSIGNMENT = "assignment"
    RESULT = "result"
    NOTIFICATION = "notification"
    STATUS = "status"


@dataclass(frozen=True)
class Task:
    id: str
    from_agent: str
    to_agent: str
    kind: str
    payload: dict[str, Any]
    status: str
    result: dict[str, Any] | None
    error: str | None
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class AgentMessage:
    id: str
    from_agent: str
    to_agent: str
    kind: str
    body: dict[str, Any]
    task_id: str | None
    created_at: str
    delivered: bool
