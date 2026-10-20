"""用量分析与告警判定。"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any

from .config import to_float
from .i18n import t
from .models import DailyUsage, Reading


@dataclass
class Analysis:
    """一次分析的结果：读数、趋势、告警。"""
    latest: Reading
    series: list[DailyUsage] = field(default_factory=list)
    avg_daily: float | None = None       # 近 N 天日均用电 kWh
    avg_source: str = "local"            # local = 自己攒的读数；history = 服务端历史
    days_left: float | None = None       # 预计还能用几天
    runout_date: date | None = None       # 预计耗尽日期
    last_used: float | None = None        # 昨日用电
    alerts: list[str] = field(default_factory=list)
    prev_ts: datetime | None = None
    interval_seconds: float | None = None
    delta_kwh: float | None = None        # 正数 = 充值，负数 = 消耗
    price_per_kwh: float | None = None    # 配置了单价才折算金额
    price_source: str = ""                # 单价来源：config / bills
    trend_daily: list[tuple[str, float]] = field(default_factory=list)
    trend_monthly: list[tuple[str, float]] = field(default_factory=list)
    trend_source: str = "local"           # local = 自己攒的读数；history = 服务端
    avg_window: tuple[str, str] | None = None  # 日均覆盖的日期区间

    @property
    def balance_cny(self) -> float | None:
        """剩余金额：接口给了就用，否则按单价折算。"""
        if self.latest.balance_cny is not None:
            return self.latest.balance_cny
        if self.price_per_kwh and self.latest.balance_kwh is not None:
            return round(self.latest.balance_kwh * self.price_per_kwh, 2)
        return None

    def _cny(self, kwh: float | None) -> float | None:
        if kwh is None or not self.price_per_kwh:
            return None
        value = kwh * self.price_per_kwh
        # 变动量很小，两位小数会显示成 0.00，多留一位
        return round(value, 2) if abs(value) >= 0.01 else round(value, 3)

    @property
    def avg_cny(self) -> float | None:
        """日均用电折合的金额。"""
        return self._cny(self.avg_daily)

    @property
    def change_cny(self) -> float | None:
        """距上次查询的用电折合的金额。"""
        return self._cny(self.delta_kwh)


def _parse_usage(items: Any, *, day_labels: bool = False) -> list[tuple[str, float]]:
    """
    把 [{date, usage}] 解析成按时间升序的 [(label, kWh)]。
    date 形如 2026-09-28 或 2026-09，usage 是字符串。
    """
    if not isinstance(items, list):
        return []
    pairs: list[tuple[str, float]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        raw = str(item.get("date") or "")
        if len(raw) < 7:
            continue
        value = to_float(item.get("usage"))
        if value is None:
            continue
        pairs.append((raw, value))
    pairs.sort(key=lambda p: p[0])
    return [(raw[5:] if day_labels else raw, value) for raw, value in pairs]


def avg_from_history(items: Any, days: int = 14) -> float | None:
    """从服务端返回的每日用电列表里算个均值，用来在本地还没攒够数据时兜底。

    入参形如 [{"date": "2026-09-28", "usage": "5.49"}, ...]。
    """
    if not isinstance(items, list) or not items:
        return None
    pairs: list[tuple[str, float]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        value = to_float(item.get("usage") or item.get("kwh"))
        if value is not None and value > 0:
            pairs.append((str(item.get("date") or ""), value))
    if not pairs:
        return None
    pairs.sort(key=lambda p: p[0], reverse=True)
    recent = [value for _, value in pairs[:days]]
    return round(sum(recent) / len(recent), 2)


def _series(readings: list[Reading]) -> list[DailyUsage]:
    """
    把相邻读数换算成日均用电。

    用真实时间间隔，不是日历天数。`daily_latest` 取的是每天最后一条读数，
    定时任务不一定对齐整点——手动补跑一次，两条读数可能只隔几个小时，
    按日历算会把日均压得很低。
    """
    usable = [r for r in readings if r.balance_kwh is not None]
    out: list[DailyUsage] = []
    for prev, cur in zip(usable, usable[1:]):
        span = (cur.ts - prev.ts).total_seconds() / 86400
        if span < 1 / 24:  # 不到一小时，差值多半是噪声
            continue
        total = prev.balance_kwh - cur.balance_kwh
        if total <= 0 or total / span > 200:
            continue
        out.append(
            DailyUsage(
                day=cur.ts.date(),
                used_kwh=round(total / span, 2),
                balance_kwh=cur.balance_kwh,
                span_days=round(span, 4),
            )
        )
    return out


def bill_rates(extra: dict) -> list[tuple[str, float, float, float]]:
    """
    账单隐含单价：[(月份, 用电量, 金额, 单价)]，按月份倒序。
    宿舍电价不一定等于居民目录价，还可能带阶梯/峰谷，
    所以单价要靠账单 ÷ 用电量反推，不能写死。
    """
    usage = dict(_parse_usage(extra.get("usage_monthly")))
    rows: list[tuple[str, float, float, float]] = []
    for bill in extra.get("bill_history") or []:
        if not isinstance(bill, dict):
            continue
        month = str(bill.get("billTime") or "")
        kwh = usage.get(month)
        money = to_float(bill.get("money"))
        if not kwh or money is None:
            continue
        rows.append((month, kwh, money, round(money / kwh, 4)))
    rows.sort(key=lambda r: r[0], reverse=True)
    return rows


def derived_price(extra: dict) -> tuple[float | None, int]:
    """从账单反推单价：总金额 ÷ 总电量。返回 (单价, 期数)。"""
    rows = bill_rates(extra)
    if not rows:
        return None, 0
    total_kwh = sum(r[1] for r in rows)
    total_money = sum(r[2] for r in rows)
    if total_kwh <= 0:
        return None, 0
    return round(total_money / total_kwh, 4), len(rows)


def analyze(
    latest: Reading,
    readings: list[Reading],
    window_days: int = 7,
    alerts_enabled: bool = True,
    low_balance_kwh: float | None = 20.0,
    low_days_left: float | None = 5.0,
    spike_ratio: float | None = 2.0,
    silent_days: float | None = 2.0,
    fallback_avg: float | None = None,
    previous: Reading | None = None,
    price_per_kwh: float | None = None,
    price_source: str = "config",
    # 本地读数至少要覆盖这么多天，才拿来算日均用电。真正的出处是配置项
    # storage.min_local_days，这里只是调用方不传时的默认值，和模板保持一致。
    min_local_days: float = 3.0,
    now: datetime | None = None,
) -> Analysis:
    now = now or datetime.now().astimezone()
    result = Analysis(
        latest=latest, price_per_kwh=price_per_kwh, price_source=price_source
    )

    if (
        previous is not None
        and previous.balance_kwh is not None
        and latest.balance_kwh is not None
    ):
        result.prev_ts = previous.ts
        result.interval_seconds = (latest.ts - previous.ts).total_seconds()
        result.delta_kwh = round(latest.balance_kwh - previous.balance_kwh, 2)

    since = now.date() - timedelta(days=window_days)
    window = [r for r in readings if r.ts.date() >= since]
    result.series = _series(window)

    if result.series:
        result.last_used = result.series[-1].used_kwh
        total_used = sum(d.used_kwh * d.span_days for d in result.series)
        total_span = sum(d.span_days for d in result.series)
        # 本地窗口不满一天，就不拿它算日均。
        # 出门开不开空调、家里电器在不在线，几个小时的用量完全不代表一整天；
        # 这种时候宁可退回服务端那份多天日均，等本地攒够一整天的样本再说。
        if total_span >= min_local_days:
            result.avg_daily = round(total_used / total_span, 2)
            result.avg_window = (
                result.series[0].day.strftime("%m-%d"),
                result.series[-1].day.strftime("%m-%d"),
            )

    extra = (latest.meta or {}).get("extra") or {}
    if result.avg_daily is None and fallback_avg:
        result.avg_daily = round(fallback_avg, 2)
        result.avg_source = "history"
        used = [p for p in _parse_usage(extra.get("usage_history"), day_labels=True) if p[1] > 0]
        if used:
            result.avg_window = (used[-min(14, len(used))][0], used[-1][0])

    extra = (latest.meta or {}).get("extra") or {}
    if len(result.series) >= 3:
        result.trend_daily = [
            (d.day.strftime("%m-%d"), d.used_kwh) for d in result.series
        ]
        result.trend_source = "local"
    else:
        result.trend_daily = _parse_usage(extra.get("usage_history"), day_labels=True)
        result.trend_source = "history"
    result.trend_monthly = _parse_usage(extra.get("usage_monthly"))

    if result.avg_daily and result.avg_daily > 0 and latest.balance_kwh is not None:
        result.days_left = round(latest.balance_kwh / result.avg_daily, 1)
        result.runout_date = latest.ts.date() + timedelta(
            days=int(math.floor(result.days_left))
        )

    if not alerts_enabled:
        return result

    bal = latest.balance_kwh
    if bal is not None:
        if bal <= 0:
            result.alerts.append(str(t("alert_exhausted")))
        elif low_balance_kwh is not None and bal < low_balance_kwh:
            result.alerts.append(str(t("alert_low", bal=f"{bal:.1f}")))

    if result.days_left is not None and low_days_left is not None:
        if result.days_left < low_days_left:
            result.alerts.append(
                str(
                    t(
                        "alert_runout",
                        days=f"{result.days_left:.1f}",
                        date=f"{result.runout_date}",
                    )
                )
            )

    if (
        spike_ratio
        and result.last_used is not None
        and len(result.series) >= 4
    ):
        others = [d.used_kwh for d in result.series[:-1]]
        baseline = statistics.fmean(others)
        if baseline > 0 and result.last_used > baseline * spike_ratio:
            result.alerts.append(
                str(
                    t(
                        "alert_spike",
                        used=f"{result.last_used:.1f}",
                        avg=f"{baseline:.1f}",
                    )
                )
            )

    if silent_days is not None:
        gap = (now - latest.ts).total_seconds() / 86400
        if gap > silent_days:
            result.alerts.append(str(t("alert_silent", days=f"{gap:.1f}")))

    return result
