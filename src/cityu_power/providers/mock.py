"""假数据源。

用途：用假数据把「抓取 → 存储 → 分析 → 推送」整条链路跑通。
它会参考上一次读数往下扣，所以多次运行能得到一条看起来正常的用量曲线。
"""

from __future__ import annotations

import random
from datetime import datetime
from typing import Any

from ..models import Reading
from .base import Provider


class MockProvider:
    """生成假读数。"""
    name = "mock"

    def __init__(self, conf: dict[str, Any] | None = None):
        conf = conf or {}
        self.room: str = conf.get("room", "12A-508")
        self.start_kwh: float = float(conf.get("start_kwh", 180.0))
        self.daily_usage: float = float(conf.get("daily_usage", 6.5))
        self.jitter: float = float(conf.get("jitter", 1.2))
        self.price_per_kwh: float = float(conf.get("price_per_kwh", 0.65))

    def fetch(self, previous: Reading | None = None) -> Reading:
        now = datetime.now().astimezone()

        if previous is not None and previous.balance_kwh is not None:
            elapsed_days = max(
                (now - previous.ts).total_seconds() / 86400.0, 0.0
            )
            used = self.daily_usage * elapsed_days
            used += random.uniform(-self.jitter, self.jitter) * min(elapsed_days, 1.0)
            kwh = previous.balance_kwh - used
        else:
            kwh = self.start_kwh - random.uniform(0, self.daily_usage)

        kwh = max(round(kwh, 2), 0.0)
        return Reading(
            ts=now,
            room=self.room,
            balance_kwh=kwh,
            balance_cny=round(kwh * self.price_per_kwh, 2),
            source=self.name,
            meta={"mock": True, "note": "演示数据，非真实读数"},
        )
