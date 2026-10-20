"""灌入 N 天演示数据，用来看报告长什么样（不联网、不推送）。

    python scripts/seed_demo.py -d 10
    python run.py report --html
    python run.py purge --keep-days 0   # 清干净
"""

from __future__ import annotations

import argparse
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from cityu_power.config import load  # noqa: E402
from cityu_power.models import Reading  # noqa: E402
from cityu_power.storage import Storage  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("-d", "--days", type=int, default=10)
    parser.add_argument("--room", default="12A-508")
    parser.add_argument("--balance", type=float, default=120.0, help="当前剩余电量")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    random.seed(args.seed)
    cfg = load(ROOT / "config.yaml")
    storage = Storage(cfg.resolve_path(cfg.get("storage.db_path", "data/readings.db")))

    now = datetime.now().replace(minute=0, second=0, microsecond=0)
    days = [now - timedelta(days=offset) for offset in range(args.days, -1, -1)]
    usages = [round(random.uniform(4.5, 9.5), 2) for _ in days]

    # 倒推：最新一天等于目标余额，往前每天加上当天用量
    balances = [0.0] * len(days)
    running = args.balance
    for idx in range(len(days) - 1, -1, -1):
        balances[idx] = round(running, 2)
        running += usages[idx]

    for day, balance in zip(days, balances):
        storage.add(
            Reading(
                ts=day.replace(hour=8),
                room=args.room,
                balance_kwh=balance,
                balance_cny=round(balance * 0.65, 2),
                source="seed",
                meta={"mock": True, "seeded": True},
            )
        )

    print(f"已写入 {len(days)} 天数据，最新剩余 {args.balance:.2f} kWh")
    print("接着跑：python run.py report --html")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
