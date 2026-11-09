#!/bin/sh
# 容器入口，两种用法：
#
#   docker run ... cityu-power check        # 当普通 CLI 用，跑完退出
#   docker run -d ... cityu-power daemon    # 内置调度，每天按 RUN_AT 自己跑

set -eu

APP_DIR="${APP_DIR:-/app}"
CONFIG="$APP_DIR/config.yaml"

log() { echo "[entrypoint] $(date '+%F %T') $*"; }

if [ ! -f "$CONFIG" ]; then
    cp "$APP_DIR/config.example.yaml" "$CONFIG"
    log "未挂载 config.yaml，已从模板生成（要改告警阈值/电价/语言请挂载自己的）"
fi

mkdir -p "$APP_DIR/data" "$APP_DIR/logs"

run_check() {
    # check 的返回码 2=抓取失败、3=推送失败。
    set +e
    python "$APP_DIR/run.py" check "$@"
    _code=$?
    set -e
    [ "$_code" -eq 0 ] || log "check 返回码 $_code（继续运行）"
    return 0
}

case "${1:-daemon}" in
    daemon)
        if [ $# -gt 0 ]; then shift; fi
        ;;
    sh | shell | bash)
        exec /bin/sh
        ;;
    *)
        # init / doctor / probe / login / token / check / report / history /
        # notify-test / price / purge 以及以后的子命令，一律透传
        exec python "$APP_DIR/run.py" "$@"
        ;;
esac

trap 'log "收到停止信号，退出"; exit 0' TERM INT

if [ "${RUN_ON_START:-0}" = "1" ]; then
    log "RUN_ON_START=1，先跑一次"
    run_check
fi

_grace_used=0

while :; do
    _next=$(GRACE_USED=$_grace_used python - <<'PY'
import datetime as dt
import os

raw = os.environ.get("RUN_AT", "08:00")
points = []
for part in raw.replace(";", ",").split(","):
    part = part.strip()
    if not part:
        continue
    try:
        hh, mm = (int(x) for x in part.split(":")[:2])
    except ValueError:
        continue
    if 0 <= hh < 24 and 0 <= mm < 60:
        points.append((hh, mm))
if not points:
    points = [(8, 0)]

grace = dt.timedelta(0) if os.environ.get("GRACE_USED") == "1" else dt.timedelta(minutes=5)

now = dt.datetime.now()
candidates = []
for hh, mm in points:
    when = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
    if when + grace <= now:
        when += dt.timedelta(days=1)
    candidates.append(when)

target = min(candidates)
print(max(int((target - now).total_seconds()), 0), target.strftime("%Y-%m-%d %H:%M"))
PY
)

    delay=${_next%% *}
    when=${_next#* }

    case "$delay" in
        '' | *[!0-9]*)
            delay=3600
            when="未知"
            ;;
    esac

    if [ "$delay" -eq 0 ]; then
        _grace_used=1
        log "落在 $when 的补跑窗口内，立刻执行"
    else
        log "下次运行：$when（${delay}s 后）"
    fi

    sleep "$delay"
    log "开始抓取"
    run_check
done
