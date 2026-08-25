# ============================================================
# LLM 训推平台 · 本地打包脚本（Windows PowerShell）
#
# 用法：
#   powershell -ExecutionPolicy Bypass -File deploy/notebook/package.ps1
#   或（PowerShell 7+）：pwsh -File deploy/notebook/package.ps1
#
# 输出：项目根目录下 model_train_upload.zip（内含 model_train/ 目录，仅几 MB）
#
# 排除项（保持 zip 小、且不含本机敏感/冗余文件）：
#   目录：node_modules / tmp / dist / storage / logs / workspace
#         __pycache__ / .git / .venv / venv / .idea / .vscode
#   文件：.env / *.log / *.db / *.pyc
#
# 说明：
#   - backend/.env 不打包：Notebook 上由 init_env.sh 从 .env.notebook 自动重新生成
#   - web-ui/dist 不打包：Notebook 上由 init_env.sh 重新 npm run build
#   - 打包后上传到 Notebook，终端执行：
#       unzip model_train_upload.zip && cd model_train
#       bash deploy/notebook/init_env.sh
# ============================================================
$ErrorActionPreference = 'Stop'

$root        = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
# GetFullPath 规范化（$env:TEMP 可能是 8.3 短路径，与文件 FullName 的长路径长度不一致，会导致相对路径偏移）
$stageParent = [System.IO.Path]::GetFullPath((Join-Path $env:TEMP 'model_train_pkg'))
$stage       = [System.IO.Path]::GetFullPath((Join-Path $stageParent 'model_train'))
$zip         = Join-Path $root 'model_train_upload.zip'

Write-Host "==> 项目根目录: $root"

# 清理旧的 staging 与 zip
if (Test-Path $stageParent) { Remove-Item $stageParent -Recurse -Force }
if (Test-Path $zip)         { Remove-Item $zip -Force }
New-Item -ItemType Directory -Path $stage -Force | Out-Null

# robocopy 复制（/XD /XF 按目录名/文件名排除；退出码 0-7 均视为成功，>=8 为失败）
robocopy $root $stage /E `
  /XD node_modules tmp dist storage logs workspace __pycache__ .git .venv venv .idea .vscode `
  /XF .env *.log *.db *.pyc model_train_upload.zip `
  /NFL /NDL /NJH /NJS /NP | Out-Null
if ($LASTEXITCODE -ge 8) { throw "robocopy 失败（exit code $LASTEXITCODE）" }

$fileCount = (Get-ChildItem $stage -Recurse -File | Measure-Object).Count
Write-Host "==> 已收集 $fileCount 个文件，正在压缩..."

# 手动写 zip 条目：顶层目录为 model_train/，分隔符强制为 /（Linux unzip 兼容；
# Windows 下 Compress-Archive / .NET Framework CreateFromDirectory 会写入反斜杠）
Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem
$fs = [System.IO.File]::Open($zip, [System.IO.FileMode]::Create, [System.IO.FileAccess]::Write)
$archive = New-Object System.IO.Compression.ZipArchive($fs, [System.IO.Compression.ZipArchiveMode]::Create)
foreach ($file in Get-ChildItem $stage -Recurse -File) {
    $rel = $file.FullName.Substring($stageParent.Length + 1).Replace('\', '/')
    $entry = $archive.CreateEntry($rel, [System.IO.Compression.CompressionLevel]::Optimal)
    $es = $entry.Open()
    $bs = [System.IO.File]::OpenRead($file.FullName)
    $bs.CopyTo($es)
    $bs.Dispose()
    $es.Dispose()
}
foreach ($dir in Get-ChildItem $stage -Recurse -Directory) {
    $rel = $dir.FullName.Substring($stageParent.Length + 1).Replace('\', '/') + '/'
    [void]$archive.CreateEntry($rel)
}
$archive.Dispose()
$fs.Dispose()

$sizeMB = [math]::Round((Get-Item $zip).Length / 1MB, 2)
Write-Host ""
Write-Host "==> 打包完成: $zip ($sizeMB MB)"
Write-Host "    1) 在 Notebook 文件管理界面拖拽上传该 zip"
Write-Host "    2) 终端执行: unzip model_train_upload.zip && cd model_train"
Write-Host "    3) bash deploy/notebook/init_env.sh"
