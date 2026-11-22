#Requires -Version 5.1
<#
.SYNOPSIS
    校验本地工作区与 GitHub 远端分支是否完全一致。

.DESCRIPTION
    在修改任何文件之前运行本脚本。退出码：

      0 = 本地干净，且与 origin/main 完全一致（可以开始改文件）
      1 = 无法访问远端（网络/凭据问题），或当前目录不是 git 仓库
      2 = 本地落后于远端（必须先 git pull --ff-only）
      3 = 本地领先（有未推送提交，远端内容已全部包含在本地）
      4 = 本地与远端已分叉（必须停下来人工处理）
      5 = 工作区有未提交的改动

.PARAMETER Remote
    远端名称，默认 origin。

.PARAMETER Branch
    分支名称，默认 main。
#>
[CmdletBinding()]
param(
    [string]$Remote = 'origin',
    [string]$Branch = 'main'
)

$ErrorActionPreference = 'Continue'
$repoRoot = Split-Path -Parent $PSScriptRoot

if (-not (Test-Path (Join-Path $repoRoot '.git'))) {
    Write-Host "[SYNC] 不是 git 仓库：$repoRoot"
    exit 1
}

Push-Location $repoRoot
try {
    $null = git rev-parse --git-dir 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host '[SYNC] 无法识别 git 仓库。'
        exit 1
    }

    Write-Host "[SYNC] 正在从 $Remote 拉取最新状态..."
    $fetchOut = @(git fetch --prune $Remote 2>&1 | ForEach-Object { "$_" })
    $fetchCode = $LASTEXITCODE
    if ($fetchCode -ne 0) {
        Write-Host "[SYNC] 无法访问远端（网络或凭据问题，git 返回 $fetchCode）："
        foreach ($line in $fetchOut) { Write-Host "       $line" }
        exit 1
    }

    $remoteRef = "$Remote/$Branch"
    $null = git rev-parse --verify --quiet "refs/remotes/$remoteRef" 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[SYNC] 远端不存在分支：$remoteRef"
        exit 1
    }

    $localSha = ((git rev-parse HEAD 2>&1) -join '').Trim()
    $remoteSha = ((git rev-parse "refs/remotes/$remoteRef" 2>&1) -join '').Trim()
    $countText = ((git rev-list --left-right --count "HEAD...$remoteRef" 2>&1) -join ' ').Trim()
    $countParts = $countText -split '\s+'
    $ahead = [int]$countParts[0]
    $behind = [int]$countParts[1]

    $changes = @(git status --porcelain 2>&1 | ForEach-Object { "$_" } | Where-Object { $_.Trim() -ne '' })
    $dirty = $changes.Count -gt 0

    $localShort = if ($localSha.Length -ge 7) { $localSha.Substring(0, 7) } else { $localSha }
    $remoteShort = if ($remoteSha.Length -ge 7) { $remoteSha.Substring(0, 7) } else { $remoteSha }

    Write-Host ''
    Write-Host "  本地 HEAD        : $localShort"
    Write-Host "  远端 $remoteRef  : $remoteShort"
    Write-Host "  领先 / 落后      : $ahead / $behind"
    if ($dirty) {
        Write-Host "  未提交改动       : $($changes.Count) 个文件"
        foreach ($line in $changes) { Write-Host "                     $line" }
    }
    else {
        Write-Host '  未提交改动       : 无'
    }
    Write-Host ''

    if ($ahead -gt 0 -and $behind -gt 0) {
        Write-Host '[SYNC] 本地与远端已分叉，禁止自动处理。请先告知用户并征求意见。' -ForegroundColor Red
        exit 4
    }
    if ($behind -gt 0) {
        Write-Host "[SYNC] 本地落后于远端 $behind 个提交。请先执行：git pull --ff-only $Remote $Branch" -ForegroundColor Yellow
        exit 2
    }
    if ($dirty) {
        Write-Host '[SYNC] 工作区有未提交的改动。请先提交或处理干净再继续。' -ForegroundColor Yellow
        exit 5
    }
    if ($ahead -gt 0) {
        Write-Host "[SYNC] 本地有 $ahead 个未推送提交（远端内容已全部包含在本地），可以继续修改，收尾时记得推送。" -ForegroundColor Yellow
        exit 3
    }

    Write-Host '[SYNC] 本地与远端完全一致，可以开始修改文件。' -ForegroundColor Green
    exit 0
}
finally {
    Pop-Location
}
