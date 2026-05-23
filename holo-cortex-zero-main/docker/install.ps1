param (
    [string]$InstallPath
)

if ([string]::IsNullOrWhiteSpace($InstallPath)) {
    $InstallPath = Join-Path $env:LOCALAPPDATA "HoloCortexZero"
}

$scriptPath = Join-Path $PSScriptRoot "wslinstall.ps1"
if (-not (Test-Path $scriptPath)) {
    Write-Host "未找到本地 wslinstall.ps1，请从仓库 docker/ 目录运行该脚本"
    Read-Host "按 Enter 键退出..."
    Exit 1
}

try {
    Write-Host "正在尝试以管理员权限启动本地脚本..."
    Start-Process PowerShell -Verb RunAs -ArgumentList @(
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-File", $scriptPath,
        "-InstallPath", $InstallPath
    ) -ErrorAction Stop -Wait
} catch {
    Write-Host "获取管理员权限失败，取消..."
}
