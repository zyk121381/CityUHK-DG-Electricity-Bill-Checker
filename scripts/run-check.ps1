# 定时任务实际执行的脚本。日志追加到 logs/task.log，方便事后查为什么没推送。
$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

# 优先用项目内的虚拟环境，没有就退回系统 python
$py = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) { $py = "python" }

New-Item -ItemType Directory -Force -Path (Join-Path $root "logs") | Out-Null
$stamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
"[任务] $stamp" | Out-File -FilePath (Join-Path $root "logs\task.log") -Append -Encoding utf8

& $py (Join-Path $root "run.py") check *>&1 |
    Tee-Object -FilePath (Join-Path $root "logs\task.log") -Append

exit $LASTEXITCODE
