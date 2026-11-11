param(
    [Parameter(Mandatory = $true)][string]$File,
    [string]$DbHost = "127.0.0.1",
    [int]$Port = 3306,
    [string]$User = "root",
    [string]$Password = $env:ANCHORLINE_DB_PASSWORD,  # U18：从环境变量读取，不硬编码
    [string]$Database = "anchorline"
)

$ErrorActionPreference = "Stop"
if (-not (Test-Path $File)) { throw "备份文件不存在：$File" }

Write-Host "正在恢复 $File -> $Database"
Get-Content $File -Raw | mysql --host=$DbHost --port=$Port --user=$User --password=$Password $Database
if ($LASTEXITCODE -ne 0) { throw "mysql 恢复失败（exit=$LASTEXITCODE）" }
Write-Host "完成。建议执行：alembic upgrade head"
