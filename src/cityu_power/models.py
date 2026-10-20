"""数据模型。"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any


@dataclass(slots=True)
class Reading:
    """一次余额读数。"""

    ts: datetime                     # 抓取时刻（本地时区）
    room: str = ""
    balance_kwh: float | None = None  # 剩余电量
    balance_cny: float | None = None  # 剩余金额
    source: str = ""                  # provider 名称
    meta: dict[str, Any] = field(default_factory=dict)  # 原始响应等

    @property
    def day(self) -> str:
        return self.ts.strftime("%Y-%m-%d")

    def to_row(self) -> tuple:
        return (
            self.ts.astimezone().isoformat(timespec="seconds"),
            self.day,
            self.room,
            self.balance_kwh,
            self.balance_cny,
            self.source,
            json.dumps(self.meta, ensure_ascii=False),
        )

    @classmethod
    def from_row(cls, row: tuple) -> "Reading":
        ts, _day, room, kwh, cny, source, meta = row
        try:
            meta_obj = json.loads(meta) if meta else {}
        except json.JSONDecodeError:
            meta_obj = {"_raw": meta}
        moment = datetime.fromisoformat(ts)
        if moment.tzinfo is None:
            moment = moment.astimezone()  # 无时区信息时按本地时间处理
        return cls(
            ts=moment,
            room=room or "",
            balance_kwh=kwh,
            balance_cny=cny,
            source=source or "",
            meta=meta_obj,
        )


@dataclass(slots=True)
class DailyUsage:
    """某一天的用电量统计。"""
    day: date
    used_kwh: float      # 该区间的日均用电
    balance_kwh: float
    span_days: int = 1   # 与上一条读数相隔几天（漏抓时 > 1）
