"""冒烟测试：不需要联网，用本地假服务器验证整条链路。

    python tests/test_smoke.py
"""

from __future__ import annotations

import json
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from cityu_power.analyzer import analyze  # noqa: E402
from cityu_power.config import dig, to_float  # noqa: E402
from cityu_power.models import Reading  # noqa: E402
from cityu_power.providers import MockProvider  # noqa: E402
from cityu_power.providers.http import HttpProvider  # noqa: E402
from cityu_power.report import render_html, render_text  # noqa: E402
from cityu_power.storage import Storage  # noqa: E402

seen_tokens: list[str] = []


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):  # 静音
        pass

    def _send(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        data = json.loads(raw or b"{}")
        if self.path == "/api/login":
            assert data.get("username") == "stu", data
            self._send({"code": 0, "data": {"token": "tk-abc123"}})
        elif self.path == "/api/login2":
            self._send({"code": 0, "data": {"ticket": "tk-xyz"}})
        else:
            self._send({"code": 404, "msg": "no such path"}, 404)

    def do_GET(self):
        if self.path.startswith("/api/boom"):
            self._send({"code": 500, "msg": "boom"}, 500)
        elif self.path.startswith("/api/meter2"):
            self._send({"code": 0, "data": {"remainKwh": 55.5, "room": "12C-2-263"}})
        elif self.path.startswith("/api/meter"):
            seen_tokens.append(self.headers.get("Authorization", ""))
            self._send(
                {
                    "code": 0,
                    "data": {
                        "roomList": [
                            {
                                "roomName": "12A-508",
                                "remainKwh": "42.5",
                                "balance": "27.63",
                                "updateTime": "2026-10-20 08:00",
                            }
                        ]
                    },
                }
            )
        elif self.path.startswith("/api/html"):
            body = (
                "<html><body><span>剩余电量：38.7 度</span>"
                "<span>房间 12A-508</span></body></html>"
            ).encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self._send({"code": 404}, 404)


def serve() -> tuple[HTTPServer, str]:
    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    host, port = server.server_address
    return server, f"http://{host}:{port}"


def test_http_provider(base: str) -> None:
    provider = HttpProvider(
        {
            "timeout": 5,
            "verify_ssl": False,
            "steps": [
                {
                    "name": "login",
                    "method": "POST",
                    "url": f"{base}/api/login",
                    "json": {"username": "stu", "password": "pw"},
                },
                {
                    "name": "meter",
                    "method": "GET",
                    "url": f"{base}/api/meter",
                    "params": {"roomId": "${steps.0.json.data.token}"},
                    "headers": {"Authorization": "Bearer ${steps.0.json.data.token}"},
                },
            ],
            "extract": {
                "balance_kwh": "data.roomList[0].remainKwh",
                "balance_cny": "data.roomList[0].balance",
                "room": "data.roomList[0].roomName",
                "updated_at": "data.roomList[0].updateTime",
            },
        }
    )
    reading = provider.fetch()
    assert reading.balance_kwh == 42.5, reading.balance_kwh
    assert reading.balance_cny == 27.63, reading.balance_cny
    assert reading.room == "12A-508", reading.room
    assert seen_tokens and seen_tokens[-1] == "Bearer tk-abc123", seen_tokens
    print("  [ok] 多步骤请求 + token 透传 + 字段提取")


def test_regex_extract(base: str) -> None:
    provider = HttpProvider(
        {
            "steps": [{"method": "GET", "url": f"{base}/api/html"}],
            "extract": {
                "balance_kwh": {"regex": r"剩余电量：([\d.]+)", "group": 1},
                "room": {"regex": r"(12A-\d+)"},
            },
        }
    )
    reading = provider.fetch()
    assert reading.balance_kwh == 38.7, reading.balance_kwh
    assert reading.room == "12A-508", reading.room
    print("  [ok] HTML 正则提取")


def test_optional_step(base: str) -> None:
    """附加接口挂了不能影响主数据。"""
    provider = HttpProvider(
        {
            "steps": [
                {"name": "main", "method": "GET", "url": f"{base}/api/meter2"},
                {"name": "extra", "method": "GET", "url": f"{base}/api/boom", "optional": True},
            ],
            "extract": {
                "balance_kwh": {"step": 0, "path": "data.remainKwh"},
                "room": {"step": 0, "path": "data.room"},
            },
        }
    )
    reading = provider.fetch()
    assert reading.balance_kwh == 55.5, reading.balance_kwh
    assert reading.room == "12C-2-263", reading.room
    print("  [ok] optional 步骤失败不拖垮主流程")


def test_whole_pipeline() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        storage = Storage(Path(tmp) / "t.db")

        # 造 6 天历史（每天 08:00 一条）
        now = datetime.now().astimezone().replace(hour=8, minute=0, second=0, microsecond=0)
        for i, kwh in enumerate([100.0, 93.0, 88.0, 80.0, 75.0, 70.0]):
            storage.add(
                Reading(
                    ts=now - timedelta(days=5 - i),
                    room="12A-508",
                    balance_kwh=kwh,
                    balance_cny=round(kwh * 0.65, 2),
                    source="test",
                )
            )

        provider = MockProvider({"room": "12A-508", "start_kwh": 70.0})
        reading = provider.fetch(storage.latest())
        storage.add(reading)

        result = analyze(
            latest=reading,
            readings=storage.daily_latest(14),
            low_balance_kwh=20,
            low_days_left=5,
        )
        assert result.avg_daily and result.avg_daily > 0, result.avg_daily

        text = render_text(result)
        html = render_html(result)
        assert "剩余电量" in text or "Remaining" in text
        assert "<html" in html

        assert storage.day_count() >= 6
        assert storage.latest() is not None
        print(f"  [ok] 存储 + 分析 + 渲染（日均 {result.avg_daily} kWh）")
        storage.close()


def test_bill_list() -> None:
    """往期账单：条数变多、字段缺失时都不能把行撑爆或报错。"""
    from cityu_power.i18n import set_locale
    from cityu_power.report import _bill_line, _month_label

    set_locale("zh")
    assert _month_label("2026-09") == "2026-09"
    assert _month_label("2026年08月账单电费") == "2026-08"
    assert _month_label("2026-07-01") == "2026-07"
    assert len(_month_label("完全认不出来的名字啊啊啊")) <= 7

    set_locale("en")
    assert _month_label("2026-09") == "2026-09"
    assert _month_label("2026年08月账单电费") == "2026-08"
    set_locale("zh")

    def bills(n: int, *, no_time: bool = False, no_money: bool = False) -> dict:
        items = []
        for i in range(n):
            month = 9 - i
            year, month = (2026, month) if month > 0 else (2025, month + 12)
            items.append(
                {
                    "billName": f"{year}年{month:02d}月账单电费",
                    "billTime": "" if no_time else f"{year}-{month:02d}",
                    "money": "" if no_money else f"{10 + i:.2f}",
                }
            )
        return {"bill_history": items}

    assert _bill_line(bills(1)) == ""          # 只有一条，没有「往期」
    assert _bill_line(bills(2)).count("·") == 0
    assert _bill_line(bills(4)).count("·") == 1
    assert _bill_line(bills(12)).count("·") == 1   # 只展示两条往期，不无限增长
    assert len(_bill_line(bills(12))) < 40
    assert "2026-08" in _bill_line(bills(4, no_time=True))
    assert "¥" not in _bill_line(bills(4, no_money=True))
    print("  [ok] 往期账单多条目/缺字段不炸")


def test_helpers() -> None:
    assert dig({"a": {"b": [{"c": 1}]}}, "a.b[0].c") == 1
    assert dig({"a": {"b": [{"c": 1}]}}, "a.b.0.c") == 1
    assert dig({}, "x.y") is None
    assert to_float("¥1,234.50") == 1234.5
    assert to_float("12.3 度") == 12.3
    assert to_float(None) is None
    print("  [ok] 路径取值与数字解析")


def main() -> int:
    server, base = serve()
    try:
        print("本地假服务器:", base)
        test_helpers()
        test_bill_list()
        test_http_provider(base)
        test_regex_extract(base)
        test_optional_step(base)
        test_whole_pipeline()
    finally:
        server.shutdown()
    print("\n全部通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
