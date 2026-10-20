"""数据源工厂。"""

from __future__ import annotations

from ..config import Config
from .base import Provider, ProviderError
from .http import HttpProvider
from .mock import MockProvider

__all__ = ["Provider", "ProviderError", "HttpProvider", "MockProvider", "build"]


def build(cfg: Config) -> Provider:
    kind = str(cfg.get("provider.type", "mock")).lower()
    if kind == "mock":
        return MockProvider(cfg.get("provider.mock", {}))
    if kind == "http":
        return HttpProvider(cfg.get("provider.http", {}))
    raise ProviderError(f"未知的 provider.type：{kind}（可选 mock / http）")
