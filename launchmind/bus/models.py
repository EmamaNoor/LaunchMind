from __future__ import annotations

import json
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field

from launchmind.utils import generate_message_id, now_iso


class MessageType(str, Enum):
    TASK = "task"
    RESULT = "result"
    REVISION_REQUEST = "revision_request"
    CONFIRMATION = "confirmation"


class Message(BaseModel):
    message_id: str = Field(default_factory=generate_message_id)
    from_agent: str
    to_agent: str
    message_type: MessageType
    payload: dict[str, Any]
    timestamp: str = Field(default_factory=now_iso)
    parent_message_id: Optional[str] = None

    def to_json(self) -> str:
        return self.model_dump_json()

    @classmethod
    def from_json(cls, data: str) -> Message:
        return cls.model_validate_json(data)
