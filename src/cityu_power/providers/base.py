"""数据来源抽象层。"""

from __future__ import annotations

from typing import Any, Protocol

from ..models import Reading


class ProviderError(RuntimeError):
    """抓取失败（网络错误、状态码非 2xx、字段解析不到等）。"""

    def __init__(self, message: str, detail: Any = None):
        super().__init__(message)
        self.detail = detail


class Provider(Protocol):
    """数据来源接口。"""
    name: str

    def fetch(self, previous: Reading | None = None) -> Reading:
        """抓一次当前余额。previous 只给 mock 之类需要连续性的实现用。"""
        ...
