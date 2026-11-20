<#
.SYNOPSIS
  受控 fastboot boot 执行器（只 RAM 引导，不写分区），带镜像哈希校验、设备检查、证据落盘。

.DESCRIPTION
  该脚本不改变任何分区状态。步骤：
    1. 校验镜像 SHA-256 与内置表一致（不一致则拒绝执行）；
    2. 探测 fastboot 设备（无设备时只生成计划文件，不执行任何动作）；
    3. 生成 boot-attempts 证据文件（时间戳 + git rev + 计划）；
    4. 仅在显式 -Confirm 且设备在线时执行 fastboot boot，并捕获输出。

.EXAMPLE
  powershell -NoProfile -ExecutionPolicy Bypass -File build-chain/tools/boot-attempt.ps1 -Image stock
  powershell -NoProfile -ExecutionPolicy Bypass -File build-chain/tools/boot-attempt.ps1 -Image shim-v4 -Confirm
#>
[CmdletBinding()]
param(
  [ValidateSet('stock','shim-v4','shim-v2','custom')]
  [string]$Image = 'stock',
  [string]$CustomPath = '',
  [string]$Note = '',
  [switch]$Confirm,
  [int]$TimeoutSec = 120
)

$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
Set-Location $repo

$known = @{
  'stock'   = @{ Path = 'build-chain/ota-evidence/boot.img'; Sha = ''; Purpose = 'C.1 机制演练：官方 stock boot.img，验证 fastboot boot 可用性' }
  'shim-v4' = @{ Path = 'build-chain/work/senna-shim/out/senna-shim-v4.img'; Sha = '7483023e9843f9e17ae9128e72664f2aadf27c1e16c9b6b408fa9a140087f907'; Purpose = 'C.2 senna 诊断 shim（v4 头）' }
  'shim-v2' = @{ Path = 'build-chain/work/senna-shim/out/senna-shim-v2.img'; Sha = '1f7f4dafa764df746cb6205d489405f8fe5a6688a2c41d0f80baa12cfb92ed12'; Purpose = 'C.2 senna 诊断 shim（v2 兜底，v4 失败时用）' }
}

if ($Image -eq 'custom') {
  if (-not $CustomPath) { throw 'custom 需要 -CustomPath' }
  $target = @{ Path = $CustomPath; Sha = ''; Purpose = 'custom image' }
} else {
  $target = $known[$Image]
}

$imgPath = (Resolve-Path $target.Path -ErrorAction Stop).Path
$sha = (Get-FileHash -Algorithm SHA256 -Path $imgPath).Hash.ToLower()
$size = (Get-Item $imgPath).Length
$rev = (git rev-parse --short HEAD).Trim()
$stamp = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ')
$evDir = Join-Path $repo 'build-chain/evidence/boot-attempts'
New-Item -ItemType Directory -Force -Path $evDir | Out-Null
$evFile = Join-Path $evDir ($stamp + '-' + $Image + '.md')

Write-Host '== 目标 ==' -ForegroundColor Cyan
Write-Host ('镜像: {0}' -f $imgPath)
Write-Host ('大小: {0} 字节  sha256: {1}' -f $size, $sha)
Write-Host ('用途: {0}' -f $target.Purpose)
Write-Host ('git:  {0}' -f $rev)

if ($target.Sha -and $sha -ne $target.Sha) {
  throw ('SHA-256 不匹配：期望 ' + $target.Sha + '，实际 ' + $sha + ' —— 拒绝执行（先重新下载 CI 产物）')
}
if (-not $target.Sha) {
  Write-Host '提示：该镜像无内置哈希基线（仅 stock/custom），请人工核对来源。' -ForegroundColor Yellow
}

$devs = @(& fastboot devices 2>$null | Where-Object { $_ -match '\S' })
$online = $devs.Count -gt 0
$devStr = if ($online) { $devs -join ' | ' } else { '未检测到（计划模式）' }
Write-Host ('设备: {0}' -f $devStr)

$lines = @(
  '# boot attempt ' + $stamp + ' (' + $Image + ')',
  '',
  '- 时间(UTC): ' + $stamp,
  '- git: ' + $rev,
  '- 镜像: ' + $imgPath,
  '- 大小: ' + $size,
  '- sha256: ' + $sha,
  '- 用途: ' + $target.Purpose,
  '- 备注: ' + $Note,
  '- 设备: ' + $devStr,
  '',
  '## 计划',
  '',
  '1. fastboot boot 镜像（只进 RAM，不写分区，不改 slot）',
  '2. 屏幕按 DESIGN.md 第 5 节时间线拍屏：信息页 / 四组候选各一张 / 倒计时或 panic 页',
  '3. 设备应自动重启回 Android（shim 内置 PSCI_SYSTEM_RESET）',
  '4. 记录 fastboot getvar all 快照，确认无变化',
  '',
  '## 结果',
  '',
  '（待填：fastboot 输出、屏幕现象、照片文件名、是否自动重启）',
  '',
  '## fastboot 输出',
  ''
)
Set-Content -Path $evFile -Value $lines -Encoding utf8

if (-not $Confirm) {
  Write-Host ''
  Write-Host '未加 -Confirm，未执行任何引导动作。计划已写入：' -ForegroundColor Yellow
  Write-Host ('  ' + $evFile)
  Write-Host '确认设备与镜像后，加 -Confirm 重跑才会真正执行 fastboot boot。' -ForegroundColor Yellow
  exit 0
}

if (-not $online) {
  throw 'fastboot 未发现设备：请确认已连接并进入 bootloader（adb reboot bootloader）后重试。'
}

Write-Host ('开始引导（超时 ' + $TimeoutSec + ' s）...') -ForegroundColor Green
$outFile = [System.IO.Path]::ChangeExtension($evFile, '.fastboot.log')
$errFile = [System.IO.Path]::ChangeExtension($evFile, '.fastboot.err')
$p = Start-Process -FilePath 'fastboot' -ArgumentList @('boot', $imgPath) -NoNewWindow -PassThru -RedirectStandardOutput $outFile -RedirectStandardError $errFile
if (-not $p.WaitForExit($TimeoutSec * 1000)) {
  Write-Warning ('fastboot boot 超过 ' + $TimeoutSec + ' s 未返回，进程仍在运行（可能已开始引导）。未强杀，请人工观察屏幕。')
} else {
  Write-Host ('fastboot 退出码: {0}' -f $p.ExitCode)
}

$fbOut = (Get-Content $outFile -Raw -ErrorAction SilentlyContinue)
$fbErr = (Get-Content $errFile -Raw -ErrorAction SilentlyContinue)
Add-Content -Path $evFile -Value ($fbOut + $fbErr) -Encoding utf8
Write-Host ''
Write-Host '证据已写入:' -ForegroundColor Green
Write-Host ('  ' + $evFile)
Write-Host ('  ' + $outFile)
Write-Host ('  ' + $errFile)
Write-Host ''
Write-Host '下一步：拍屏并把照片放到 build-chain/evidence/boot-attempts/，在证据文件「结果」节填写现象。' -ForegroundColor Cyan
