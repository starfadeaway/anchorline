param(
    [string]$OutDir = "$PSScriptRoot\..\data\backups",
    [string]$DbHost = "127.0.0.1",
    [int]$Port = 3306,
    [string]$User = "root",
    [string]$Password = $env:ANCHORLINE_DB_PASSWORD,  # U18：从环境变量读取，不硬编码
    [string]$Database = "anchorline"
)

$ErrorActionPreference = "Stop"
if (-not (Get-Command mysqldump -ErrorAction SilentlyContinue)) {
    throw "未找到 mysqldump：请把 MySQL 的 bin 目录加入 PATH（例如 C:\Program Files\MySQL\MySQL Server 8.4\bin）"
}
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$file = Join-Path $OutDir "anchorline-$stamp.sql"

# 密码走临时 defaults 文件：不进命令行（进程列表）也不触发 insecure 警告
$opt = [System.IO.Path]::GetTempFileName()
Set-Content -Path $opt -Value "[client]`npassword=$Password" -Encoding ascii
try {
    Write-Host "正在导出 $Database -> $file"
    mysqldump --defaults-extra-file="$opt" --host=$DbHost --port=$Port --user=$User --single-transaction --routines --triggers --default-character-set=utf8mb4 --result-file="$file" $Database
    if ($LASTEXITCODE -ne 0) { throw "mysqldump 失败（exit=$LASTEXITCODE）" }
} finally {
    Remove-Item $opt -Force -ErrorAction SilentlyContinue
}
Write-Host "完成：$file（$([math]::Round((Get-Item $file).Length / 1KB, 1)) KB）"
