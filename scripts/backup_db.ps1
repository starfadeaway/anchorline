param(
    [string]$OutDir = "$PSScriptRoot\..\data\backups",
    [string]$DbHost = "127.0.0.1",
    [int]$Port = 3306,
    [string]$User = "root",
    [string]$Password = "placeholder-local-password",
    [string]$Database = "anchorline"
)

$ErrorActionPreference = "Stop"
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$file = Join-Path $OutDir "anchorline-$stamp.sql"

Write-Host "正在导出 $Database -> $file"
mysqldump --host=$DbHost --port=$Port --user=$User --password=$Password --single-transaction --routines --triggers $Database > $file
if ($LASTEXITCODE -ne 0) { throw "mysqldump 失败（exit=$LASTEXITCODE）" }
Write-Host "完成：$file（$([math]::Round((Get-Item $file).Length / 1KB, 1)) KB）"
