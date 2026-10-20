"""
报告渲染：纯文本，Markdown，HTML。
所有文案都从 i18n 取，语言由 `app.locale` 决定，默认英文。
"""

from __future__ import annotations

import re
from datetime import datetime

from .analyzer import Analysis
from .config import to_float
from .i18n import LINKS, t

SPARK = "▁▂▃▄▅▆▇█"


def _wrap(text: str) -> str:
    return str(t("wrap", text=text))


def _sep() -> str:
    return str(t("sep"))


def _pad() -> int:
    try:
        return int(t("label_pad"))
    except (TypeError, ValueError):
        return 4


def _human_interval(seconds: float | None) -> str:
    """计算秒数：5.20min / 3.10h / 1.00d。"""
    if seconds is None:
        return ""
    seconds = abs(seconds)
    if seconds < 60:
        return str(t("unit_seconds", value=f"{seconds:.0f}"))
    if seconds < 3600:
        return str(t("unit_minutes", value=f"{seconds / 60:.2f}"))
    if seconds < 86400:
        return str(t("unit_hours", value=f"{seconds / 3600:.2f}"))
    return str(t("unit_days", value=f"{seconds / 86400:.2f}"))


def _month_label(raw: str) -> str:
    """解析往期账单时间"""
    text = (raw or "").strip()
    match = re.search(r"(\d{4})\s*[-年/]\s*(\d{1,2})", text)
    if match:
        year, month = match.group(1), int(match.group(2))
        return f"{year}-{month:02d}"
    return text[:6] + ("…" if len(text) > 6 else "")


def _bill_name(raw: str) -> str:
    """将学校接口返回的中文翻译成英文"""
    text = (raw or "").strip()
    match = re.match(r"(\d{4})年(\d{1,2})月账单电费", text)
    if match:
        return str(
            t(
                "bill_name",
                year=match.group(1),
                month=f"{int(match.group(2)):02d}",
            )
        )
    return text


def _bills(extra: dict, limit: int = 3) -> list[dict]:
    items = [b for b in (extra.get("bill_history") or []) if isinstance(b, dict)]
    items.sort(key=lambda b: str(b.get("billTime") or ""), reverse=True)
    return items[:limit]


def _bill_line(extra: dict, limit: int = 3) -> str:
    """把往期账单拼成一行：08月 ¥15.42 · 07月 ¥12.00"""
    bills = _bills(extra, limit)
    if len(bills) < 2:
        return ""
    parts: list[str] = []
    for bill in bills[1:]:
        label = _month_label(str(bill.get("billTime") or bill.get("billName") or ""))
        money = to_float(bill.get("money"))
        parts.append(f"{label} ¥{money:.2f}" if money is not None else label)
    return " · ".join(parts)


def _bar(values: list[float]) -> str:
    """把用电量画成一串柱状图"""
    if not values:
        return ""
    lo, hi = min(values), max(values)
    span = (hi - lo) or 1.0
    return "".join(
        SPARK[min(len(SPARK) - 1, int((v - lo) / span * (len(SPARK) - 1)))] for v in values
    )


def _balance(a: Analysis) -> str:
    """余额文本，标题里用。"""
    if a.latest.balance_kwh is None:
        return "—"
    return f"{a.latest.balance_kwh:.1f} kWh"


def subject(a: Analysis, kind: str | None = None) -> str:
    """
    标题。
    一天里第一条叫日报，之后叫更新。
    """
    if kind is None:
        kind = "alert" if a.alerts else "daily"
    label = t(f"subject_{kind}") if kind in ("daily", "update", "alert") else t("subject_daily")
    return str(
        t(
            "subject_fmt",
            kind=label,
            room=a.latest.room or t("html_room"),
            bal=_balance(a),
        )
    )


def _avg_tag(a: Analysis) -> str:
    """日均的口径说明。"""
    if a.avg_window:
        key = "average_of" if a.avg_source == "history" else "average_of_local"
        return _wrap(str(t(key, start=a.avg_window[0], end=a.avg_window[1])))
    if a.avg_source == "history":
        return _wrap(str(t("server_average")))
    return _wrap(str(t("local_readings")))


def _items(a: Analysis) -> list[tuple[str, str, str]]:
    """
    报告条目：[(键, 标签, 值)]，三种格式共用一份，保证一致。
    顺序：宿舍号 → 剩余电量 → 查询时间 → 电量变动 → 上次查询 → 其余。
    """
    r = a.latest
    extra = (r.meta or {}).get("extra") or {}
    rows: list[tuple[str, str, str]] = []

    if r.room:
        rows.append(("room", str(t("room")), r.room))

    if r.balance_kwh is not None:
        amount = (
            _wrap(f"≈ ¥{a.balance_cny:.2f}") if a.balance_cny is not None else ""
        )
        rows.append(("remaining", str(t("remaining")), f"{r.balance_kwh:.2f} kWh{amount}"))
    else:
        rows.append(("remaining", str(t("remaining")), "—"))

    rows.append(("read_at", str(t("read_at")), f"{r.ts:%m-%d %H:%M:%S}"))

    if a.delta_kwh is not None:
        if a.delta_kwh > 0:
            value = f"+{a.delta_kwh:.2f} kWh{_wrap(str(t('topped_up')))}"
        elif a.delta_kwh < 0:
            value = f"{a.delta_kwh:.2f} kWh{_wrap(str(t('consumed')))}"
        else:
            value = f"0.00 kWh{_wrap(str(t('no_change')))}"
        rows.append(("change", str(t("change")), value))

    if a.prev_ts is not None:
        rows.append(
            (
                "last_check",
                str(t("last_check")),
                "{ts}{gap}".format(
                    ts=f"{a.prev_ts:%m-%d %H:%M:%S}",
                    gap=_wrap(
                        str(t("interval", gap=_human_interval(a.interval_seconds)))
                    ),
                ),
            )
        )

    if a.avg_daily is not None:
        rows.append(("daily_avg", str(t("daily_avg")), f"{a.avg_daily:.2f} kWh{_avg_tag(a)}"))

    if a.days_left is not None:
        tail = (
            _wrap(str(t("until", date=f"{a.runout_date:%m-%d}")))
            if a.runout_date
            else ""
        )
        rows.append(("runs_for", str(t("runs_for")), f"{a.days_left:.1f} {t('unit_day')}{tail}"))

    if extra.get("bill_name"):
        money = f"{t('money_sep')}¥{extra['bill_money']}" if extra.get("bill_money") else ""
        rows.append(("latest_bill", str(t("latest_bill")), f"{_bill_name(extra['bill_name'])}{money}"))

    history = _bill_line(extra)
    if history:
        rows.append(("past_bills", str(t("past_bills")), history))

    return rows


def _rows(a: Analysis) -> list[tuple[str, str]]:
    return [(label, value) for _, label, value in _items(a)]


def _title(a: Analysis) -> str:
    bal = (
        f"{a.latest.balance_kwh:.2f} kWh"
        if a.latest.balance_kwh is not None
        else "—"
    )
    return str(
        t("report_title", room=a.latest.room or t("html_room"), balance=bal)
    )


def _links_md() -> str:
    """报告末尾的主页链接。"""
    return (
        f"[GitHub]({LINKS['github']}) · "
        f"[{t('blog')}]({LINKS['blog']})"
    )


# 邮件客户端会把内联 SVG 的属性剥掉（图标撑成默认尺寸、fill 丢失变黑块），
# 所以这里用图片：GitHub 官方 PNG 和博客自己的 favicon。
_ICON_GITHUB = "https://github.githubassets.com/assets/GitHub-Mark-ea2971cee799.png"
_ICON_BLOG = "https://www.040426.xyz/favicon.ico"


def _links_html() -> str:
    """HTML 报告末尾的主页链接，带图标，居中。"""
    icon = (
        'style="width:14px;height:14px;vertical-align:-2px;border-radius:3px"'
    )
    return (
        '<p style="margin-top:16px;padding-top:12px;border-top:1px solid #eef0f4;'
        'font-size:12px;color:#9ca3af;text-align:center">'
        f'<a href="{LINKS["github"]}" style="color:#6b7280;text-decoration:none;'
        f'margin-right:18px">'
        f'<img src="{_ICON_GITHUB}" width="14" height="14" alt="" {icon}> GitHub</a>'
        f'<a href="{LINKS["blog"]}" style="color:#6b7280;text-decoration:none">'
        f'<img src="{_ICON_BLOG}" width="14" height="14" alt="" {icon}> '
        f"{t('blog')}</a></p>"
    )


def _sparkline(values: list[float]) -> str:
    return _bar(values)


def _span(points: list[tuple[str, float]], monthly: bool = False) -> str:
    """
    趋势覆盖的真实区间。日：09-22–09-28；月：2026-04–09。
    数据是服务端给的最后 N 条，未必截止到今天，所以写区间而不是「近 N 天」。
    """
    if not points:
        return ""
    first, last = points[0][0], points[-1][0]
    return f"{first}–{last[5:]}" if monthly else f"{first}–{last}"


def _source_label(a: Analysis) -> str:
    return str(t("server_history") if a.trend_source == "history" else t("local_readings"))


def render_markdown(a: Analysis, trend_days: int = 7, month_days: int = 6) -> str:
    """
    给会渲染 Markdown 的渠道用。
    不用表格 —— 企业微信机器人不认表格语法。
    """
    lines: list[str] = [f"**{_title(a)}**", ""]

    for alert in a.alerts:
        lines.append(f"> ⚠️ {alert}")
    if a.alerts:
        lines.append("")

    for label, value in _rows(a):
        lines.append(f"- **{label}**{_sep()}{value}")

    trend: list[str] = []
    if a.trend_daily:
        tail = a.trend_daily[-trend_days:]
        avg = sum(v for _, v in tail) / len(tail)
        trend.append(
            f"{_span(tail)}　{_sparkline([v for _, v in tail])}　"
            f"{t('avg_per_day', value=f'{avg:.2f}')}"
        )
    if a.trend_monthly:
        tail = a.trend_monthly[-month_days:]
        trend.append(
            f"{_span(tail, monthly=True)}　{_sparkline([v for _, v in tail])}　"
            f"{t('latest_month', value=f'{tail[-1][1]:.1f}')}"
        )
    if trend:
        source = (
            t("server_not_live")
            if a.trend_source == "history"
            else t("local_readings")
        )
        lines.append("")
        lines.append(f"**{t('usage_trend')}**{_wrap(str(source))}")
        lines.extend(trend)

    lines.append("")
    lines.append(_links_md())

    return "\n".join(lines)


def render_text(a: Analysis, trend_days: int = 7, month_days: int = 6) -> str:
    r = a.latest
    pad = _pad()
    lines: list[str] = [_title(a), ""]
    lines += [f"{label.ljust(pad)}{_sep()}{value}" for label, value in _rows(a)]

    if a.trend_daily:
        tail = a.trend_daily[-trend_days:]
        lines.append("")
        lines.append(
            f"{t('usage_of', span=_span(tail))}"
            f"{_wrap(str(t('source_suffix', source=_source_label(a))))}"
        )
        for (label, value), bar in zip(tail, _sparkline([v for _, v in tail])):
            lines.append(f"{label}  {bar}  {value:.2f}")

    if a.trend_monthly:
        tail = a.trend_monthly[-month_days:]
        lines.append("")
        lines.append(
            f"{t('usage_of', span=_span(tail, monthly=True))}"
            f"{_wrap(str(t('source_suffix', source=t('server_history'))))}"
        )
        for (label, value), bar in zip(tail, _sparkline([v for _, v in tail])):
            lines.append(f"{label[2:].replace('-', '/')}  {bar}  {value:.1f}")

    if a.alerts:
        lines.append("")
        for msg in a.alerts:
            lines.append(f"[!] {msg}")

    if (r.meta or {}).get("mock"):
        lines.append("")
        lines.append(str(t("mock_note")))
    return "\n".join(lines)


def _bar_row(label: str, pct: float, value: str, color: str, width: int = 60) -> str:
    return (
        "<div style='margin-bottom:8px;font-size:13px;color:#4b5563'>"
        "<table width='100%' cellpadding='0' cellspacing='0' border='0'><tr>"
        f"<td width='{width}' style='padding-right:10px;white-space:nowrap'>{label}</td>"
        "<td><div style='background:#e5e7eb;border-radius:4px;height:14px;width:100%'>"
        f"<div style='background:{color};width:{pct:.0f}%;height:14px;border-radius:4px'></div>"
        "</div></td>"
        "<td width='45' style='text-align:right;white-space:nowrap'>"
        f"{value}</td></tr></table></div>"
    )


def _bill_entries(extra: dict, limit: int = 3) -> list[tuple[str, float | None]]:
    """账单期间和金额，最新的在前。"""
    out: list[tuple[str, float | None]] = []
    for bill in _bills(extra, limit):
        period = _month_label(str(bill.get("billTime") or bill.get("billName") or ""))
        out.append((period, to_float(bill.get("money"))))
    return out


def _monthly_groups(points: list[tuple[str, float]]) -> list[tuple[str, float]]:
    """把连续的零值月份并成一段，免得图表里全是空条。"""
    groups: list[tuple[str, float]] = []
    for label, value in points:
        if groups and groups[-1][1] == 0 and value == 0:
            first = groups[-1][0].split("~")[0]
            groups[-1] = (f"{first}~{label[5:]}", 0.0)
        else:
            groups.append((label, value))
    return groups


def render_html(a: Analysis, trend_days: int = 7) -> str:
    r = a.latest
    extra = (r.meta or {}).get("extra") or {}

    kwh = f"{r.balance_kwh:.2f}" if r.balance_kwh is not None else "—"
    cny = f"¥{a.balance_cny:.2f}" if a.balance_cny is not None else "—"
    days = f"{a.days_left:.1f}" if a.days_left is not None else "—"
    avg = f"{a.avg_daily:.2f}" if a.avg_daily is not None else "—"
    runout = (
        str(t("until", date=f"{a.runout_date:%m-%d}")) if a.runout_date else ""
    )

    if a.delta_kwh is None:
        change_num, change_note, change_color = "—", "", "#111827"
    elif a.delta_kwh > 0:
        change_num, change_note, change_color = f"+{a.delta_kwh:.2f}", str(t("topped_up")), "#16a34a"
    elif a.delta_kwh < 0:
        change_num, change_note, change_color = f"{a.delta_kwh:.2f}", str(t("consumed")), "#ef4444"
    else:
        change_num, change_note, change_color = "0.00", str(t("no_change")), "#111827"

    prev_line = ""
    if a.prev_ts is not None:
        prev_line = (
            f"{a.prev_ts:%m-%d %H:%M:%S}"
            f"{_wrap(str(t('interval', gap=_human_interval(a.interval_seconds))))}"
        )

    bills = _bill_entries(extra)
    bill_html = ""
    if bills:
        period, money = bills[0]
        parts = [
            f"{t('latest_bill')} ({period})："
            f"<span style='color:#374151;font-weight:500'>{'¥%.2f' % money if money is not None else '—'}</span>"
        ]
        for period, money in bills[1:]:
            parts.append(
                f"{t('past_bills')} ({period})："
                f"<span style='color:#374151;font-weight:500'>{'¥%.2f' % money if money is not None else '—'}</span>"
            )
        bill_html = (
            "<div class='pad bill' style='padding:16px 24px;font-size:13px;color:#6b7280;"
            "border-bottom:1px solid #eef0f4'>"
            + "&nbsp;&nbsp;·&nbsp;&nbsp;".join(parts)
            + "</div>"
        )
    elif extra.get("bill_name"):
        money = f" ¥{extra['bill_money']}" if extra.get("bill_money") else ""
        bill_html = (
            "<div class='pad bill' style='padding:16px 24px;font-size:13px;color:#6b7280;"
            "border-bottom:1px solid #eef0f4'>"
            f"{t('latest_bill')}：<span style='color:#374151;font-weight:500'>"
            f"{_bill_name(extra['bill_name'])}{money}</span></div>"
        )

    alert_html = ""
    if a.alerts:
        items = "".join(f"<li style='margin:4px 0'>{m}</li>" for m in a.alerts)
        alert_html = (
            "<div class='pad' style='background:#fff4e5;border-left:3px solid #d97706;"
            "padding:12px 18px;margin:16px 24px;border-radius:6px'>"
            f"<div style='font-weight:600;color:#b45309;margin-bottom:6px'>{t('alert_box_title')}</div>"
            f"<ul style='margin:0;padding-left:18px;color:#7c2d12;font-size:14px'>{items}</ul></div>"
        )

    daily_rows = ""
    if a.trend_daily:
        tail = a.trend_daily[-trend_days:]
        peak = max(value for _, value in tail) or 1
        for label, value in tail:
            daily_rows += _bar_row(label, value / peak * 100, f"{value:.2f}", "#10b981")

    monthly_rows = ""
    if a.trend_monthly:
        groups = _monthly_groups(a.trend_monthly[-6:])
        peak = max(value for _, value in groups) or 1
        for label, value in groups:
            monthly_rows += _bar_row(label, value / peak * 100, f"{value:.1f}", "#3b82f6", width=80)

    daily_block = ""
    if daily_rows:
        daily_block = (
            "<div class='pad' style='padding:24px 24px 0'>"
            f"<div style='font-size:14px;font-weight:bold;color:#374151;margin-bottom:16px'>"
            f"{t('usage_of', span=_span(a.trend_daily[-trend_days:]))}"
            f"{_wrap(str(t('source_suffix', source=_source_label(a))))}</div>"
            f"{daily_rows}</div>"
        )

    monthly_block = ""
    if monthly_rows:
        monthly_block = (
            "<div class='pad' style='padding:0 24px 24px'>"
            f"<div style='font-size:14px;font-weight:bold;color:#374151;margin-bottom:16px'>"
            f"{t('usage_of', span=_span(a.trend_monthly[-6:], monthly=True))}"
            f"{_wrap(str(t('source_suffix', source=t('server_history'))))}</div>"
            f"{monthly_rows}</div>"
        )

    links_html = _links_html()
    note = (
        f"<p class='pad' style='color:#9ca3af;font-size:12px;padding:0 24px 20px'>{t('mock_note')}</p>"
        if (r.meta or {}).get("mock")
        else ""
    )

    return f"""<!doctype html>
<html lang="{t('html_lang')}"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{t('html_title')}</title>
<style>
@media only screen and (max-width: 480px) {{
  .card {{ margin: 0 !important; border-radius: 0 !important; box-shadow: none !important; }}
  .pad {{ padding-left: 16px !important; padding-right: 16px !important; }}
  .big {{ font-size: 23px !important; }}
  .mid {{ font-size: 17px !important; }}
  .lbl {{ font-size: 12px !important; }}
  .sub {{ font-size: 10px !important; }}
  .bill {{ font-size: 12px !important; }}
  .ts {{ display: block !important; width: 100% !important; padding-right: 0 !important; }}
}}
</style></head>
<body style="margin:0;padding:0;background:#f5f7fa;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;-webkit-font-smoothing:antialiased">
<div class="card" style="max-width:600px;margin:20px auto;background:#ffffff;border-radius:8px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.05)">

  <div class="pad" style="padding:20px 24px;border-bottom:1px solid #eef0f4">
    <div style="font-size:14px;color:#6b7280;margin-bottom:4px">{t('html_title')}</div>
    <div style="font-size:20px;font-weight:bold;color:#111827">{r.room or t('html_room')}</div>
  </div>

  <div class="pad" style="padding:24px;background:#f8fafc">
    <table width="100%" cellpadding="0" cellspacing="0" border="0"><tr>
      <td width="50%" style="vertical-align:top">
        <div class="lbl" style="font-size:14px;color:#6b7280;margin-bottom:8px">{t('remaining')}</div>
        <div class="big" style="font-size:28px;font-weight:bold;color:#111827;white-space:nowrap">{kwh} <span style="font-size:16px;font-weight:normal;color:#6b7280">kWh</span></div>
      </td>
      <td width="50%" style="vertical-align:top">
        <div class="lbl" style="font-size:14px;color:#6b7280;margin-bottom:8px">{t('amount')}</div>
        <div class="big" style="font-size:28px;font-weight:bold;color:#111827;white-space:nowrap">{cny}</div>
      </td>
    </tr></table>
  </div>

  <div class="pad" style="padding:0 24px 24px;background:#f8fafc;border-bottom:1px solid #eef0f4">
    <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-bottom:16px"><tr>
      <td width="33.33%" style="vertical-align:top">
        <div class="lbl" style="font-size:13px;color:#6b7280;margin-bottom:6px">{t('daily_avg')}</div>
        <div class="mid" style="font-size:20px;font-weight:bold;color:#111827;white-space:nowrap">{avg} <span style="font-size:13px;font-weight:normal;color:#6b7280">kWh</span></div>
        <div class="sub" style="font-size:11px;color:#9ca3af">{_avg_tag(a).strip('（）()')}</div>
      </td>
      <td width="33.33%" style="vertical-align:top">
        <div class="lbl" style="font-size:13px;color:#6b7280;margin-bottom:6px">{t('runs_for')}</div>
        <div class="mid" style="font-size:20px;font-weight:bold;color:#111827;white-space:nowrap">{days} <span style="font-size:13px;font-weight:normal;color:#6b7280">{t('unit_day')}</span></div>
        <div class="sub" style="font-size:11px;color:#9ca3af">{runout}</div>
      </td>
      <td width="33.33%" style="vertical-align:top">
        <div class="lbl" style="font-size:13px;color:#6b7280;margin-bottom:6px">{t('change')}</div>
        <div class="mid" style="font-size:20px;font-weight:bold;color:{change_color};white-space:nowrap">{change_num} <span style="font-size:13px;font-weight:normal;color:#6b7280">kWh</span></div>
        <div class="sub" style="font-size:11px;color:#9ca3af">{change_note}</div>
      </td>
    </tr></table>

    <div style="font-size:12px;color:#9ca3af;line-height:1.6;border-top:1px dashed #e2e8f0;padding-top:12px">
      <table width="100%" cellpadding="0" cellspacing="0" border="0"><tr>
        <td width="50%" class="ts" style="vertical-align:top">
          <span style="display:inline-block;width:4px;height:4px;background:#9ca3af;border-radius:50%;margin-right:6px;vertical-align:middle"></span>{t('read_at')} {r.ts:%m-%d %H:%M:%S}
        </td>
        <td width="50%" class="ts" style="vertical-align:top">
          <span style="display:inline-block;width:4px;height:4px;background:#9ca3af;border-radius:50%;margin-right:6px;vertical-align:middle"></span>{t('last_check')} {prev_line or '—'}
        </td>
      </tr></table>
    </div>
  </div>

  {bill_html}
  {alert_html}
  {daily_block}
  {monthly_block}
  {links_html}
  {note}
</div>
</body></html>"""
