#!/usr/bin/env bash
# 定时任务实际执行的脚本。日志追加到 logs/task.log，方便事后查为什么没推送。
# 用法：bash scripts/run-check.sh            # 正常跑一次
#       bash scripts/run-check.sh --no-notify # 只抓不推

set -uo pipefail

# 找项目根目录：脚本在项目里就按脚本位置算，
# 被 1Panel 之类面板写进临时文件执行时退回到当前目录。
root=""
if [ -f "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." 2>/dev/null && pwd)/run.py" ]; then
  root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
elif [ -f "./run.py" ]; then
  root="$(pwd)"
fi

if [ -z "$root" ]; then
  echo "找不到项目目录（run.py）。" >&2
  echo "面板里请写这一行：bash /你的项目路径/scripts/run-check.sh" >&2
  exit 1
fi

cd "$root" || exit 1

# 优先用项目内的虚拟环境，没有就退回系统 python
if [ -x ".venv/bin/python" ]; then
  py=".venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  py="python3"
else
  py="python"
fi

if [ ! -x ".venv/bin/python" ] && ! command -v python3 >/dev/null 2>&1 && ! command -v python >/dev/null 2>&1; then
  echo "服务器上找不到 python，先装一个 Python 3.10+" >&2
  exit 1
fi

# 预检依赖：缺了就直接说怎么装，比抛一屏 traceback 强
if ! "$py" -c "import httpx, yaml" >/dev/null 2>&1; then
  echo "依赖没装：$py 里找不到 httpx / PyYAML" >&2
  echo "装一下：$py -m pip install -r requirements.txt" >&2
  exit 1
fi

mkdir -p logs
log="logs/task.log"
stamp="$(date '+%Y-%m-%d %H:%M:%S')"

# 输出同时写日志和 stderr：面板的失败信息里能直接看到原因，
# 不用再自己去翻 logs/task.log。
echo "[任务] $stamp" | tee -a "$log"
"$py" run.py check "$@" 2>&1 | tee -a "$log"
code=${PIPESTATUS[0]}

if [ "$code" -ne 0 ]; then
  echo "[任务] 失败，退出码 $code" | tee -a "$log"
else
  echo "[任务] 完成" | tee -a "$log"
fi
exit "$code"
