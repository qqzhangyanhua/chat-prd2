from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MessageResult:
    user_message_id: str
    assistant_message_id: str
    action: dict
    reply: str


@dataclass(frozen=True)
class MessageStreamEvent:
    type: str
    data: dict


@dataclass(frozen=True)
class PreparedMessageStream:
    user_message_id: str
    reply_group_id: str
    assistant_version_id: str
    next_version_no: int
    action: dict
    turn_decision: object
    state: dict
    state_patch: dict
    prd_patch: dict
    model_meta: dict[str, str]
    reply_stream: object


@dataclass(frozen=True)
class PreparedRegenerateStream(PreparedMessageStream):
    assistant_message_id: str


class LocalReplyStream:
    def __init__(self, reply: str) -> None:
        self._reply = reply

    def __iter__(self):
        yield self._reply

    def close(self):
        return None
