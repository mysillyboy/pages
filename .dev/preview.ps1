#Requires -Version 5.1
<#
.SYNOPSIS
    启动本地静态预览服务器。

.DESCRIPTION
    在浏览器里预览站点，效果与 GitHub Pages 基本一致。
    默认监听 http://127.0.0.1:8000/，按 Ctrl+C 停止。

.PARAMETER Port
    监听端口，默认 8000。

.PARAMETER NoOpen
    不自动打开浏览器。
#>
[CmdletBinding()]
param(
    [int]$Port = 8000,
    [switch]$NoOpen
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$url = "http://127.0.0.1:$Port/"

Write-Host "[PREVIEW] 目录: $root"
Write-Host "[PREVIEW] 地址: $url"
Write-Host '[PREVIEW] Ctrl+C 停止。'

if (-not $NoOpen) {
    Start-Job -ScriptBlock {
        param($u)
        Start-Sleep -Seconds 2
        Start-Process $u
    } -ArgumentList $url | Out-Null
}

$python = Get-Command python -ErrorAction SilentlyContinue
if ($python) {
    & $python.Source -m http.server $Port --bind 127.0.0.1 --directory $root
    exit $LASTEXITCODE
}

$node = Get-Command node -ErrorAction SilentlyContinue
if ($node) {
    & $node.Source (Join-Path $PSScriptRoot 'serve.mjs') $root $Port
    exit $LASTEXITCODE
}

Write-Host '[PREVIEW] 未找到 python 或 node，无法启动预览服务器。' -ForegroundColor Red
exit 1
