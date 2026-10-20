#!/usr/bin/env bash
# 在 Linux 服务器上安装依赖并注册 systemd 定时任务。
#
#   bash scripts/install-linux.sh              # 安装 / 更新
#   bash scripts/install-linux.sh --uninstall  # 卸载
#
# 用普通账号执行，脚本内部按需调用 sudo。别用 root 直接跑，
# 否则 .venv 会变成 root 所有，以后更新依赖很麻烦。

set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_USER="$(id -un)"
UNIT_DIR="/etc/systemd/system"
SERVICE="cityu-power.service"
TIMER="cityu-power.timer"

if [ "$(id -u)" -eq 0 ]; then
    echo "请用普通账号执行：sudo 已由脚本自己调用。" >&2
    exit 1
fi

# ---------- 卸载 ----------
if [ "${1:-}" = "--uninstall" ]; then
    sudo systemctl disable --now "$TIMER" 2>/dev/null || true
    sudo rm -f "$UNIT_DIR/$TIMER" "$UNIT_DIR/$SERVICE"
    sudo systemctl daemon-reload
    echo "已移除定时任务。项目目录和数据库保留在 $APP_DIR"
    exit 0
fi

# ---------- 检查 python ----------
PY="${PYTHON:-python3}"
if ! command -v "$PY" >/dev/null 2>&1; then
    echo "找不到 $PY，先装 Python 3.9+" >&2
    exit 1
fi
"$PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' || {
    echo "Python 版本太低，需要 3.9+" >&2
    exit 1
}

# ---------- 虚拟环境与依赖 ----------
if [ ! -d "$APP_DIR/.venv" ]; then
    echo "创建虚拟环境 .venv"
    "$PY" -m venv "$APP_DIR/.venv" || {
        echo "创建失败。Debian/Ubuntu 需要先装：sudo apt install python3-venv" >&2
        exit 1
    }
fi
echo "安装依赖"
"$APP_DIR/.venv/bin/pip" install -q --upgrade pip
"$APP_DIR/.venv/bin/pip" install -q -r "$APP_DIR/requirements.txt"

# ---------- 配置文件 ----------
if [ ! -f "$APP_DIR/config.yaml" ]; then
    cp "$APP_DIR/config.example.yaml" "$APP_DIR/config.yaml"
    echo "已生成 config.yaml，记得填 provider 和 notify"
fi
if [ ! -f "$APP_DIR/.env" ] && [ -f "$APP_DIR/.env.example" ]; then
    cp "$APP_DIR/.env.example" "$APP_DIR/.env"
    chmod 600 "$APP_DIR/.env"
    echo "已生成 .env（权限 600），记得填凭据"
fi

mkdir -p "$APP_DIR/data" "$APP_DIR/logs"

# ---------- 安装 systemd 单元 ----------
render() {
    sed -e "s|__APP_DIR__|$APP_DIR|g" -e "s|__USER__|$RUN_USER|g" "$1"
}

render "$APP_DIR/scripts/$SERVICE" | sudo tee "$UNIT_DIR/$SERVICE" >/dev/null
render "$APP_DIR/scripts/$TIMER" | sudo tee "$UNIT_DIR/$TIMER" >/dev/null

sudo systemctl daemon-reload
sudo systemctl enable --now "$TIMER"

echo
echo "安装完成"
echo "  运行用户    $RUN_USER"
echo "  项目目录    $APP_DIR"
echo "  定时        $(systemctl show -p TimersCalendar --value "$TIMER" 2>/dev/null || echo '每天 08:00')"
echo
echo "常用命令："
echo "  systemctl list-timers $TIMER          # 下次触发时间"
echo "  sudo systemctl start $SERVICE         # 立刻跑一次"
echo "  journalctl -u $SERVICE -n 50 --no-pager"
echo "  $APP_DIR/.venv/bin/python $APP_DIR/run.py report"
