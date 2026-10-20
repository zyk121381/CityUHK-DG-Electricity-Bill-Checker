# 注册 Windows 计划任务：每天定点跑一次电量检查。
# 用法（普通 PowerShell 即可，不需要管理员，任务以当前用户身份运行）：
#   .\scripts\register-task.ps1                 # 默认每天 08:00
#   .\scripts\register-task.ps1 -At 07:30,21:00 # 一天跑两次
#   .\scripts\register-task.ps1 -Remove         # 删除任务

param(
    [string[]]$At = @("08:00"),
    [string]$Name = "CityU Power Checker",
    [switch]$Remove
)

$root = Split-Path -Parent $PSScriptRoot

if ($Remove) {
    Unregister-ScheduledTask -TaskName $Name -Confirm:$false
    Write-Host "已删除任务：$Name"
    return
}

$action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$root\scripts\run-check.ps1`""

$triggers = $At | ForEach-Object { New-ScheduledTaskTrigger -Daily -At $_ }

$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -DontStopOnIdleEnd `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 10) `
    -MultipleInstances IgnoreNew

Register-ScheduledTask `
    -TaskName $Name `
    -Action $action `
    -Trigger $triggers `
    -Settings $settings `
    -Description "港城莞宿舍电量抓取与推送" `
    -Force | Out-Null

Write-Host "已注册任务：$Name"
$At | ForEach-Object { Write-Host "  每天 $_" }
Write-Host "手动试跑：Start-ScheduledTask -TaskName `"$Name`""
Write-Host "查看日志：Get-Content `"$root\logs\task.log`" -Tail 30"
