"""MessageBus 介面。

語意（見 docs/adr/0002）：
- 投遞為 at-least-once，消費端必須冪等，以 ``Message.message_id`` 去重。
- handler 正常返回 → ack。
- handler 拋出 ``RetryableError`` → 稍後重送；重試次數與退避由 Postgres 記帳，不依賴 broker。
- handler 拋出 ``PermanentError`` → 直接進入死信佇列（DLQ）。
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Protocol


class RetryableError(Exception):
    """暫時性失敗，可以稍後重試。"""


class PermanentError(Exception):
    """永久性失敗，重試沒有意義，應進入死信佇列。"""


@dataclass(frozen=True, slots=True)
class Message:
    message_id: str
    topic: str
    body: bytes
    headers: dict[str, str] = field(default_factory=dict)  # 含 W3C traceparent
    delivery_attempt: int = 1


Handler = Callable[[Message], Awaitable[None]]


class MessageBus(Protocol):
    async def publish(self, message: Message) -> None: ...

    async def consume(self, topic: str, handler: Handler) -> None:
        """持續消費直到被取消。"""
        ...
