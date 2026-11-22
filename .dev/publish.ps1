#Requires -Version 5.1
<#
.SYNOPSIS
    提交改动 → 推送到 GitHub → 等待 GitHub Pages 发布并校验。

.DESCRIPTION
    1. 先跑 check-sync 校验本地与远端一致（落后或分叉时直接中止，不推送）；
    2. 有未提交改动则 git add -A + commit；
    3. 推送到 origin/main；
    4. 轮询线上站点，直到页面确实更新，或超时给出提示。

    注意：本站采用「从分支发布」，推送到 main 后 GitHub Pages 会自动构建，通常 30～90 秒生效。

.PARAMETER Message
    提交信息。

.PARAMETER Remote
    远端名称，默认 origin。

.PARAMETER Branch
    分支名称，默认 main。

.PARAMETER TimeoutSec
    等待线上更新确认的最长秒数，默认 600。

.PARAMETER NoVerify
    跳过线上发布确认，只推送。
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$Message,

    [string]$Remote = 'origin',
    [string]$Branch = 'main',
    [int]$TimeoutSec = 600,
    [switch]$NoVerify
)

$ErrorActionPreference = 'Continue'
$repoRoot = Split-Path -Parent $PSScriptRoot

# 没有 node 时的兜底实现：用 Invoke-WebRequest 轮询 Last-Modified。
function Wait-PagesFallback {
    param(
        [string]$Url,
        [datetime]$Since,
        [int]$TimeoutSec
    )
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    $attempt = 0
    $started = Get-Date
    while ((Get-Date) -lt $deadline) {
        $attempt++
        $sep = if ($Url.Contains('?')) { '&' } else { '?' }
        try {
            $resp = Invoke-WebRequest -Uri "$Url$sep_=$([DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds())" `
                -UseBasicParsing -TimeoutSec 20 -Headers @{ 'Cache-Control' = 'no-cache'; 'User-Agent' = 'dsh-pages-publisher' }
            $lmRaw = $resp.Headers['Last-Modified']
            $lm = if ($lmRaw -is [array]) { $lmRaw[0] } else { $lmRaw }
            $elapsed = [int]((Get-Date) - $started).TotalSeconds
            if ($lm) {
                $lmTime = ([datetime]::Parse($lm, [System.Globalization.CultureInfo]::InvariantCulture, [System.Globalization.DateTimeStyles]::AdjustToUniversal))
                if ($lmTime -ge $Since) {
                    Write-Host "  [pages] 第 $attempt 次检查：已更新（last-modified=$lm，用时 ${elapsed}s）"
                    return 0
                }
                Write-Host "  [pages] 第 $attempt 次检查：尚未更新（last-modified=$lm），10s 后重试..."
            }
            elseif ($elapsed -ge 60) {
                Write-Host "  [pages] 第 $attempt 次检查：页面可访问，无 last-modified（用时 ${elapsed}s），视为已发布。"
                return 0
            }
            else {
                Write-Host "  [pages] 第 $attempt 次检查：尚未更新（无 last-modified），10s 后重试..."
            }
        }
        catch {
            Write-Host "  [pages] 第 $attempt 次检查：请求失败（$($_.Exception.Message)），10s 后重试..."
        }
        Start-Sleep -Seconds 10
    }
    Write-Host '  [pages] 超时。'
    return 2
}

Push-Location $repoRoot
try {
    # ---------- 1. 同步校验 ----------
    & (Join-Path $PSScriptRoot 'check-sync.ps1') -Remote $Remote -Branch $Branch
    $syncCode = $LASTEXITCODE
    if ($syncCode -eq 1 -or $syncCode -eq 2 -or $syncCode -eq 4) {
        Write-Host "[PUBLISH] 同步校验未通过（退出码 $syncCode），已中止。不要在不一致的状态下推送。" -ForegroundColor Red
        exit $syncCode
    }
    if ($syncCode -eq 5) {
        Write-Host '[PUBLISH] 本地有未提交改动，将随本次发布一起提交。'
    }

    # ---------- 2. 提交 ----------
    $changes = @(git status --porcelain 2>&1 | ForEach-Object { "$_" } | Where-Object { $_.Trim() -ne '' })
    if ($changes.Count -gt 0) {
        Write-Host "[PUBLISH] 暂存 $($changes.Count) 个改动..."
        git add -A
        if ($LASTEXITCODE -ne 0) { Write-Host '[PUBLISH] git add 失败。' -ForegroundColor Red; exit 1 }

        git commit -m $Message
        if ($LASTEXITCODE -ne 0) { Write-Host '[PUBLISH] git commit 失败。' -ForegroundColor Red; exit 1 }
    }
    else {
        Write-Host '[PUBLISH] 工作区没有新改动。'
    }

    # ---------- 3. 推送 ----------
    $aheadCount = [int]((((git rev-list --count "$Remote/$Branch..HEAD" 2>&1) -join '')).Trim())
    if ($aheadCount -eq 0) {
        Write-Host '[PUBLISH] 没有需要推送的提交，流程结束。' -ForegroundColor Green
        exit 0
    }

    $commitSha = ((git rev-parse HEAD 2>&1) -join '').Trim()
    $commitShort = $commitSha.Substring(0, 7)
    $pushTime = (Get-Date).ToUniversalTime()

    Write-Host "[PUBLISH] 推送 $aheadCount 个提交到 $Remote/$Branch ..."
    git push $Remote "HEAD:$Branch" 2>&1 | ForEach-Object { "$_" } | Out-Host
    if ($LASTEXITCODE -ne 0) {
        Write-Host '[PUBLISH] 推送失败。请检查凭据是否已存入 Windows 凭据管理器。' -ForegroundColor Red
        exit 1
    }
    Write-Host "[PUBLISH] 推送成功：$commitShort" -ForegroundColor Green

    # ---------- 4. 确认远端已更新 ----------
    $null = git fetch --prune $Remote 2>&1
    $remoteSha = ((git rev-parse "refs/remotes/$Remote/$Branch" 2>&1) -join '').Trim()
    if ($remoteSha -ne $commitSha) {
        $shortRemote = if ($remoteSha.Length -ge 7) { $remoteSha.Substring(0, 7) } else { $remoteSha }
        Write-Host "[PUBLISH] 警告：远端 $Remote/$Branch 当前指向 $shortRemote，与本地提交不一致。" -ForegroundColor Yellow
    }
    else {
        Write-Host "[PUBLISH] 已确认远端 $Remote/$Branch 指向本次提交。" -ForegroundColor Green
    }

    # ---------- 5. 等待 Pages 发布 ----------
    $remoteUrl = ((git remote get-url $Remote 2>&1) -join '').Trim()
    if ($remoteUrl -notmatch 'github\.com[:/](?<owner>[^/]+)/(?<repo>[^/]+?)(?:\.git)?/*$') {
        Write-Host "[PUBLISH] 无法从 remote 地址解析 GitHub 仓库：$remoteUrl" -ForegroundColor Yellow
        exit 0
    }
    $owner = $Matches['owner']
    $repoName = $Matches['repo']
    $siteUrl = "https://$owner.github.io/$repoName/"

    Write-Host ''
    Write-Host "  提交     : $commitShort"
    Write-Host "  线上地址 : $siteUrl"
    Write-Host ''

    if ($NoVerify) {
        Write-Host '[PUBLISH] 已跳过线上发布确认（-NoVerify）。' -ForegroundColor Yellow
        exit 0
    }

    Write-Host '[PUBLISH] 等待 GitHub Pages 构建完成...'
    $sinceIso = $pushTime.ToString('o')
    $nodeCmd = Get-Command node -ErrorAction SilentlyContinue
    if ($nodeCmd) {
        & $nodeCmd.Source (Join-Path $PSScriptRoot 'wait-pages.mjs') $siteUrl $sinceIso $TimeoutSec
        $verifyCode = $LASTEXITCODE
    }
    else {
        $verifyCode = Wait-PagesFallback -Url $siteUrl -Since $pushTime -TimeoutSec $TimeoutSec
    }

    if ($verifyCode -eq 0) {
        Write-Host ''
        Write-Host "[PUBLISH] 完成：已推送 $commitShort 并确认线上更新。" -ForegroundColor Green
        Write-Host "          $siteUrl" -ForegroundColor Green
        exit 0
    }
    else {
        Write-Host ''
        Write-Host "[PUBLISH] 已推送 $commitShort，但未在 ${TimeoutSec}s 内确认线上更新。" -ForegroundColor Yellow
        Write-Host '          GitHub Pages 构建偶尔较慢，请稍后刷新页面（Ctrl+F5 强制刷新）。' -ForegroundColor Yellow
        exit 2
    }
}
finally {
    Pop-Location
}
