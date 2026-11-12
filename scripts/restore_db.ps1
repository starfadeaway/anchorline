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

$opt = [System.IO.Path]::GetTempFileName()
Set-Content -Path $opt -Value "[client]`npassword=$Password" -Encoding ascii
try {
    Write-Host "正在恢复 $File -> $Database"
    # 管道导入（UTF-8）：比 --execute="source 中文路径" 稳，且不依赖 mysql source 指令
    $OutputEncoding = [System.Text.UTF8Encoding]::new($false)
    Get-Content -Raw -Encoding UTF8 $File | mysql --defaults-extra-file="$opt" --host=$DbHost --port=$Port --user=$User --default-character-set=utf8mb4 $Database
    if ($LASTEXITCODE -ne 0) { throw "mysql 恢复失败（exit=$LASTEXITCODE）" }
} finally {
    Remove-Item $opt -Force -ErrorAction SilentlyContinue
}
Write-Host "完成。建议执行：alembic upgrade head"
