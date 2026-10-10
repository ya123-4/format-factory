# 格式工厂 exe 打包脚本（可重复执行）
# 用法：在本目录运行 powershell -ExecutionPolicy Bypass -File .pytest-bootstrap\build_exe.ps1
# 产物：dist\FormatFactory\ 目录（onedir 模式，启动不写 TEMP，火绒友好）+ dist\FormatFactory-v1.0.0.zip
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

# 沙箱/权限友好：所有临时与缓存重定向到 workspace
$env:TMP = "$root\.tmp"
$env:TEMP = "$root\.tmp"
$env:LOCALAPPDATA = "$root\.tmp-localapp"
New-Item -ItemType Directory -Force $env:TMP, $env:LOCALAPPDATA | Out-Null
$env:PYTHONPATH = "$root\.pytest-libs"

python -m PyInstaller `
  --noconfirm --clean --onedir --windowed `
  --name "FormatFactory" `
  --paths "libs" `
  --collect-all "rapidocr_onnxruntime" `
  --collect-all "onnxruntime" `
  --collect-all "pymupdf" `
  --collect-all "pdf2docx" `
  --hidden-import "app.engine.ocr" `
  --hidden-import "fitz" `
  --hidden-import "PIL" `
  --hidden-import "openpyxl" `
  --hidden-import "pptx" `
  --hidden-import "docx" `
  --hidden-import "shapely" `
  --hidden-import "pyclipper" `
  --hidden-import "cv2" `
  --add-data "tools/ffmpeg;tools/ffmpeg" `
  app/main.py

Write-Host "BUILD DONE -> dist\FormatFactory\FormatFactory.exe"

# 打包 zip（便于分发/上传 Release）
$zip = "$root\dist\FormatFactory-v1.0.0.zip"
if (Test-Path $zip) { Remove-Item $zip -Force }
Compress-Archive -Path "$root\dist\FormatFactory\*" -DestinationPath $zip
Write-Host "ZIP DONE -> $zip"
Get-Item $zip | Select-Object Name, @{n="SizeMB";e={[math]::Round($_.Length/1MB,1)}}
