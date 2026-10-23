"""
命令行入口。

    python run.py init              # 生成 config.yaml
    python run.py doctor            # 体检：配置、凭据、渠道
    python run.py probe             # 打一次真实接口，把原始响应存下来看
    python run.py check             # 抓取 + 存库 + 分析 + 推送（定时任务跑这个）
    python run.py report            # 只用库里数据出一份报告，不联网
    python run.py history -n 20     # 看最近读数
    python run.py notify-test       # 测试推送渠道通不通
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import shutil
import sqlite3
import sys
from datetime import date, datetime
from pathlib import Path

from . import __version__, providers
from .analyzer import Analysis, analyze, avg_from_history, bill_rates, derived_price
from .config import Config, load, to_float
from .i18n import set_locale, t
from .models import Reading
from .notify import NotifyError, build_channels, send_all
from .report import render_html, render_markdown, render_text, subject as make_subject
from .storage import Storage

log = logging.getLogger("cityu_power")


def _fix_console() -> None:
    """Windows 控制台默认 GBK，中文和符号会炸，强制 UTF-8。"""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        except Exception:
            pass


def _setup_logging(cfg: Config) -> None:
    path = cfg.resolve_path(cfg.get("app.log_path", "logs/checker.log"))
    path.parent.mkdir(parents=True, exist_ok=True)
    fmt = logging.Formatter("%(asctime)s  %(levelname)-7s %(message)s", "%Y-%m-%d %H:%M:%S")
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers.clear()
    try:
        fh = logging.FileHandler(path, encoding="utf-8")
        fh.setFormatter(fmt)
        root.addHandler(fh)
    except OSError:
        pass
    sh = logging.StreamHandler(sys.stderr)
    sh.setFormatter(fmt)
    root.addHandler(sh)

    for noisy in ("httpx", "httpcore"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def _load(path: str) -> Config:
    """读配置，顺手把语言切过去。"""
    cfg = load(path)
    set_locale(cfg.get("app.locale", "en"))
    return cfg


def _price(cfg: Config, extra: dict) -> tuple[float | None, str]:
    """单价和它的来源。配置里写了就用配置的，否则从账单反推。"""
    price = cfg.get("electricity.price_per_kwh", 0) or 0
    if price:
        return float(price), "config"
    derived, periods = derived_price(extra)
    if derived:
        return derived, f"bills:{periods}"
    return None, "none"


def _push_report(cfg: Config) -> bool:
    """
    没有告警的时候，要不要也推一份常规报告。
    配置项叫 push_report：报告每次运行都推。
    旧配置里的 daily_report 是同一个意思，只是名字不准，保留作兜底。
    """
    value = cfg.get("notify.push_report")
    if value is None:
        value = cfg.get("notify.daily_report", True)
    return bool(value)


def _open_storage(cfg: Config) -> Storage:
    return Storage(cfg.resolve_path(cfg.get("storage.db_path", "data/readings.db")))


def _analyze(cfg: Config, latest: Reading, storage: Storage) -> Analysis:
    alerts = cfg.get("notify.alerts", {}) or {}
    extra = (latest.meta or {}).get("extra") or {}

    recent = storage.last(2)
    previous = recent[1] if len(recent) > 1 else None
    price, price_source = _price(cfg, extra)

    result = analyze(
        latest=latest,
        readings=storage.since(int(cfg.get("storage.analysis_window_days", 7)) + 1),
        window_days=int(cfg.get("storage.analysis_window_days", 7)),
        min_local_days=float(cfg.get("storage.min_local_days", 3)),
        alerts_enabled=bool(alerts.get("enabled", True)),
        low_balance_kwh=alerts.get("low_balance_kwh"),
        low_days_left=alerts.get("low_days_left"),
        spike_ratio=alerts.get("spike_ratio"),
        silent_days=alerts.get("silent_days"),
        fallback_avg=avg_from_history(extra.get("usage_history")),
        previous=previous,
        price_per_kwh=float(price) if price else None,
        price_source=price_source,
    )

    unpaid = [b for b in (extra.get("unpaid_items") or []) if isinstance(b, dict)]
    if unpaid and bool(alerts.get("enabled", True)):
        total = sum(to_float(b.get("money")) or 0 for b in unpaid)
        result.alerts.append(
            str(t("alert_unpaid", count=len(unpaid), money=f"¥{total:.2f}"))
        )
    return result


def _today_key() -> str:
    return date.today().isoformat()


def cmd_init(args: argparse.Namespace) -> int:
    root = Path(args.config).parent
    target = root / "config.yaml"
    example = root / "config.example.yaml"
    if not example.exists():
        print(f"找不到模板 {example}，请从仓库里复制一份")
        return 1
    if target.exists() and not args.force:
        print(f"{target} 已存在。要覆盖请加 --force")
        return 1
    shutil.copyfile(example, target)
    env_example = root / ".env.example"
    if env_example.exists() and not (root / ".env").exists():
        shutil.copyfile(env_example, root / ".env")
    print(f"已生成 {target}")
    print("接下来：在 .env 里填账号密码和推送渠道，config.yaml 里的数据源一般不用改")
    print("然后跑 python run.py doctor 检查一下")
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    cfg = _load(args.config)
    print(f"配置文件      {cfg.path}")
    print(f"数据源类型    {cfg.get('provider.type', 'mock')}")

    if cfg.missing_env:
        print("缺失环境变量  " + ", ".join(sorted(cfg.missing_env)))
    else:
        print("缺失环境变量  无")

    channels = build_channels(cfg)
    if channels:
        print("推送渠道      " + "、".join(f"{c.label}" for c in channels))
    else:
        print("推送渠道      （未启用任何渠道）")

    try:
        provider = providers.build(cfg)
    except providers.ProviderError:
        provider = None
    if provider is not None and hasattr(provider, "validate_token"):
        token = provider.current_token()  # type: ignore[attr-defined]
        if not token:
            print("token         未配置，先跑 python run.py token")
        else:
            meta = provider.token_meta()  # type: ignore[attr-defined]
            ok, message = provider.validate_token(token)  # type: ignore[attr-defined]
            status = "有效" if ok else f"失效（{message}）"
            print(f"token         {status}，缓存于 {meta.get('obtained_at', '未知')}")

    try:
        storage = _open_storage(cfg)
        latest = storage.latest()
        print(f"数据库        {storage.path}")
        print(f"累计天数      {storage.day_count()} 天")
        sources = storage.sources()
        if sources:
            print("数据来源      " + "、".join(f"{s or '未知'} {n} 条" for s, n in sources))
        if latest:
            print(
                f"最近一条      {latest.ts:%Y-%m-%d %H:%M}  "
                f"{latest.balance_kwh} kWh"
            )
    except sqlite3.Error as exc:
        print(f"数据库异常    {exc}")
        return 1
    return 0


def cmd_probe(args: argparse.Namespace) -> int:
    cfg = _load(args.config)
    if str(cfg.get("provider.type", "mock")) != "http":
        print("provider.type 不是 http，没有真实接口可打。先在 config.yaml 里改成 http。")
        return 1
    try:
        provider = providers.build(cfg)
        entries = provider.probe()  # type: ignore[attr-defined]
    except providers.ProviderError as exc:
        print(f"请求失败：{exc}")
        if getattr(exc, "detail", None):
            print(json.dumps(exc.detail, ensure_ascii=False)[:2000])
        return 2

    out = cfg.resolve_path("data")
    out.mkdir(parents=True, exist_ok=True)
    dump = out / f"probe-{datetime.now():%Y%m%d-%H%M%S}.json"
    dump.write_text(json.dumps(entries, ensure_ascii=False, indent=2), "utf-8")

    for entry in entries:
        print(f"\n=== {entry['name']}  HTTP {entry['status']} ===")
        print(entry["url"])
        body = entry.get("request_body")
        if body:
            print("发送:", json.dumps(body, ensure_ascii=False)[:300])
        print((entry["text"] or "")[:1500])
    print(f"\n完整响应已存到 {dump}")
    print("下一步：在 config.yaml 的 provider.http.extract 里填字段路径，例如 data.remainKwh")
    return 0


def cmd_login(args: argparse.Namespace) -> int:
    cfg = _load(args.config)
    provider = providers.build(cfg)
    if not hasattr(provider, "relogin"):
        print("当前数据源不需要登录（provider.type = mock？）")
        return 1
    try:
        info = provider.relogin()  # type: ignore[attr-defined]
    except providers.ProviderError as exc:
        print(f"登录失败：{exc}")
        message = str(exc)
        if "Authentication failed" in message:
            print(
                "\n账号或密码不对。几点提醒：\n"
                "  · AccountName 不一定是学号，学校预建的账号可能是手机号\n"
                "  · 先在浏览器登录页手工试，别在这里反复试，连续失败可能锁账号\n"
                "  · 试出来之后把 .env 的 EPAY_ACCOUNT / EPAY_PASSWORD 改掉，重跑本命令"
            )
        elif "二次认证" in message:
            print(
                "\n浏览器里打开 onebill，把跳出来的二次认证走完（能勾「信任此设备」就勾上），\n"
                "  然后立刻回到 DevTools 重新复制 Cookie 填进 .env。\n"
                "  注意：cookie 在二次认证前后可能会变，复制旧的没用。"
            )
        elif "Cookie" in message or "会话" in message:
            print(
                "\nIDP_COOKIE 为空或已失效。\n"
                "  浏览器登录 idp.cityu-dg.edu.cn → F12 → Network → 任意请求 →\n"
                "  复制 Request Headers 里的 Cookie 整行，贴进 .env 的 IDP_COOKIE"
            )
        return 2
    print(
        f"登录成功，token 已缓存（{info['length']} 字符）\n"
        f"文件：{info['file']}\n"
        f"时间：{info['obtained_at']}"
    )
    return 0


def cmd_token(args: argparse.Namespace) -> int:
    """更新 bearer token：校验一次，通过才落盘。"""
    cfg = _load(args.config)
    provider = providers.build(cfg)
    if not hasattr(provider, "validate_token"):
        print("当前数据源不需要 token（provider.type = mock？）")
        return 1

    raw = args.value
    if not raw:
        print("浏览器 F12 → Network → 任意一个 onebill 请求 → 复制 authorization 头里的 uuid")
        raw = input("粘贴 token：")
    token = (raw or "").strip()
    for prefix in ("Bearer ", "bearer ", "Authorization: "):
        if token.startswith(prefix):
            token = token[len(prefix):].strip()
    if not token:
        print("没输入内容")
        return 1

    ok, message = provider.validate_token(token)  # type: ignore[attr-defined]
    if not ok:
        print(f"校验失败：{message}")
        return 2

    provider.save_token(token)  # type: ignore[attr-defined]
    print(f"校验通过，已保存（{len(token)} 字符）到 data/token.json")
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    cfg = _load(args.config)
    _setup_logging(cfg)
    storage = _open_storage(cfg)

    try:
        provider = providers.build(cfg)
    except providers.ProviderError as exc:
        log.error("数据源初始化失败：%s", exc)
        return 1

    try:
        reading = provider.fetch(storage.latest())
    except providers.ProviderError as exc:
        log.error("抓取失败：%s", exc)
        _report_failure(cfg, storage, str(exc))
        return 2

    storage.add(reading)
    log.info("已记录 %s → %.2f kWh", reading.ts.strftime("%F %T"), reading.balance_kwh or 0)

    analysis = _analyze(cfg, reading, storage)
    text = render_text(analysis)
    html = render_html(analysis)
    markdown = render_markdown(analysis)

    today = _today_key()
    alert_sig = hashlib.sha1("|".join(analysis.alerts).encode()).hexdigest()[:10]
    aler_key = f"alert:{today}:{alert_sig}"
    daily_key = f"daily:{today}"

    reason = None
    if analysis.alerts:
        reason = "alert"
    elif _push_report(cfg):
        reason = "daily"

    if reason == "alert":
        kind = "alert"
    elif storage.has_notice(daily_key):
        kind = "update"
    else:
        kind = "daily"

    subj = make_subject(analysis, kind)
    print(f"\n{subj}\n{text}\n")

    if args.no_notify:
        log.info("--no-notify，跳过推送")
        return 0

    if reason is None and not args.force:
        log.info("无需推送")
        return 0

    # 常规报告每次运行都推；只有告警才需要去重，
    # 否则自己定频跑的时候，同一条告警会推一遍又一遍。
    once_per_day = cfg.get("notify.alert_once_per_day")
    if once_per_day is None:
        once_per_day = cfg.get("notify.notify_once_per_day", True)

    if not args.force and reason == "alert" and once_per_day:
        if storage.has_notice(aler_key):
            log.info("今天已经推过同类告警，跳过（想强制推送加 --force）")
            return 0
        key = aler_key
    else:
        key = f"manual:{datetime.now().isoformat(timespec='seconds')}"

    channels = build_channels(cfg)
    if not channels:
        log.warning("没有可用的推送渠道，先生成报告看看效果")
        return 0

    results = send_all(channels, subj, text, html, markdown)
    ok = 0
    for label, error in results:
        if error:
            log.error("%s 推送失败：%s", label, error)
        else:
            log.info("%s 推送成功", label)
            ok += 1

    if ok:
        storage.mark_notice(key)
        if reason == "daily":
            storage.mark_notice(daily_key)
    return 0 if ok else 3


def _report_failure(cfg: Config, storage: Storage, message: str) -> None:
    """抓取失败也要让人知道，否则定时任务静默失效最危险。"""
    key = f"fail:{_today_key()}"
    if storage.has_notice(key):
        return
    channels = build_channels(cfg)
    if not channels:
        return
    hint = ""
    low = message.lower()
    if "cookie" in low or "会话" in message or "session" in low or "code" in low:
        hint = str(t("fail_hint_cookie"))
    elif "401" in message or "鉴权" in message or "auth" in low:
        hint = str(t("fail_hint_token"))

    body = str(
        t(
            "fail_body",
            message=message,
            when=f"{datetime.now():%Y-%m-%d %H:%M}",
            hint=hint,
        )
    )
    results = send_all(channels, str(t("fail_subject")), body)
    for label, error in results:
        if error:
            log.error("失败通知推送失败（%s）：%s", label, error)
        else:
            log.info("失败通知已推送（%s）", label)
    if any(err is None for _, err in results):
        storage.mark_notice(key)
    else:
        log.error("没能把失败通知发出去，只能看日志了")


def cmd_report(args: argparse.Namespace) -> int:
    cfg = _load(args.config)
    storage = _open_storage(cfg)
    latest = storage.latest()
    if latest is None:
        print("库里还没有数据，先跑一次 python run.py check")
        return 1
    analysis = _analyze(cfg, latest, storage)
    print(render_text(analysis))
    if args.html:
        out = cfg.resolve_path("data/report.html")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(render_html(analysis), "utf-8")
        print(f"\nHTML 已写到 {out}")
    return 0


def cmd_history(args: argparse.Namespace) -> int:
    cfg = _load(args.config)
    storage = _open_storage(cfg)
    rows = storage.last(args.limit)
    if not rows:
        print("库里还没有数据")
        return 1
    latest = storage.latest()
    extra = ((latest.meta or {}).get("extra") or {}) if latest else {}
    price, _ = _price(cfg, extra)
    print(f"{'时间':<18}{'房间':<12}{'剩余 kWh':>10}{'金额':>10}  数据源")
    for r in rows:
        if r.balance_kwh is not None and price:
            cny = f"¥{r.balance_kwh * price:.2f}"
        elif r.balance_cny is not None:
            cny = f"¥{r.balance_cny:.2f}"
        else:
            cny = "—"
        kwh = f"{r.balance_kwh:.2f}" if r.balance_kwh is not None else "—"
        print(f"{r.ts:%Y-%m-%d %H:%M}  {r.room:<12}{kwh:>10}{cny:>10}  {r.source}")
    return 0


def cmd_notify_test(args: argparse.Namespace) -> int:
    cfg = _load(args.config)
    channels = build_channels(cfg)
    if not channels:
        print("没有启用任何推送渠道，检查 .env 的 NOTIFY_CHANNELS")
        return 1
    try:
        storage = _open_storage(cfg)
        latest = storage.latest()
    except sqlite3.Error:
        latest = None

    if latest is not None:
        analysis = _analyze(cfg, latest, storage)
        note = str(t("test_note", ts=f"{latest.ts:%m-%d %H:%M:%S}"))
        text = note + "\n\n" + render_text(analysis)
        html = (
            f"<p style='color:#9ca3af;font-size:12px'>{note}</p>"
            + render_html(analysis)
        )
        markdown = note + "\n\n" + render_markdown(analysis)
        subj = str(t("test_subject", ts=f"{latest.ts:%m-%d %H:%M:%S}"))
    else:
        text = str(t("test_empty"))
        html = f"<p>{text}</p>"
        markdown = text
        subj = str(t("test_subject", ts="—"))

    results = send_all(channels, subj, text, html, markdown)
    ok = 0
    for label, error in results:
        print(f"  {label:<20}{'OK' if error is None else 'FAIL  ' + error}")
        ok += error is None
    return 0 if ok else 3


def cmd_price(args: argparse.Namespace) -> int:
    """列出每期账单反推出来的单价。"""
    cfg = _load(args.config)
    storage = _open_storage(cfg)
    latest = storage.latest()
    if latest is None:
        print("库里还没有数据，先跑一次 python run.py check")
        return 1
    extra = (latest.meta or {}).get("extra") or {}
    rows = bill_rates(extra)
    if not rows:
        print("没有可用的账单或月度用电量，无法反推单价")
        return 1

    print(f"{'月份':<10}{'用电 kWh':>10}{'账单 ¥':>10}{'单价':>9}")
    for month, kwh, money, rate in rows:
        print(f"{month:<10}{kwh:>10.2f}{money:>10.2f}{rate:>9.4f}")

    derived, periods = derived_price(extra)
    print()
    print(f"合计 {periods} 期 → 单价 {derived:.4f} 元/度" if derived else "算不出单价")
    print("注：各期单价不一致说明电价带阶梯/峰谷/优惠，总额除以总电量只是平均口径。")
    return 0


def cmd_purge(args: argparse.Namespace) -> int:
    cfg = _load(args.config)
    storage = _open_storage(cfg)
    if args.source:
        n = storage.delete_source(args.source)
        print(f"已删除 source={args.source} 的 {n} 条记录")
        return 0
    n = storage.purge_old(args.keep_days)
    print(f"已清理 {n} 条 {args.keep_days} 天前的记录")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="run.py",
        description="香港城市大学（东莞）宿舍电量查询器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--config", default="config.yaml", help="配置文件路径")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command")

    p = sub.add_parser("init", help="生成配置文件")
    p.add_argument("--force", action="store_true", help="覆盖已有文件")
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("doctor", help="检查配置与数据库状态")
    p.set_defaults(func=cmd_doctor)

    p = sub.add_parser("probe", help="打一次真实接口并保存原始响应")
    p.set_defaults(func=cmd_probe)

    p = sub.add_parser("login", help="用账号密码登录并缓存 token")
    p.set_defaults(func=cmd_login)

    p = sub.add_parser("token", help="手动更新 token（过期时用）")
    p.add_argument("value", nargs="?", default="", help="直接给 token，不带就交互输入")
    p.set_defaults(func=cmd_token)

    p = sub.add_parser("check", help="抓取 + 分析 + 推送")
    p.add_argument("--no-notify", action="store_true", help="只抓取不推送")
    p.add_argument("--force", action="store_true", help="忽略每日去重，强制推送")
    p.set_defaults(func=cmd_check)

    p = sub.add_parser("report", help="用已有数据出报告")
    p.add_argument("--html", action="store_true", help="同时导出 HTML")
    p.set_defaults(func=cmd_report)

    p = sub.add_parser("history", help="查看最近读数")
    p.add_argument("-n", "--limit", type=int, default=20)
    p.set_defaults(func=cmd_history)

    p = sub.add_parser("notify-test", help="测试推送渠道")
    p.set_defaults(func=cmd_notify_test)

    p = sub.add_parser("price", help="查看每期账单反推的电价")
    p.set_defaults(func=cmd_price)

    p = sub.add_parser("purge", help="清理旧记录")
    p.add_argument("--keep-days", type=int, default=400)
    p.add_argument("--source", default="", help="只删某个数据源，如 seed / mock")
    p.set_defaults(func=cmd_purge)

    return parser


def main(argv: list[str] | None = None) -> int:
    _fix_console()
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help()
        return 0
    try:
        return int(args.func(args))
    except FileNotFoundError as exc:
        print(f"错误：{exc}")
        return 1
    except KeyError as exc:
        print(f"错误：{exc}")
        return 1
    except NotifyError as exc:
        print(f"推送错误：{exc}")
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
