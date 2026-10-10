# 格式工厂 exe 打包脚本（可重复执行）
# 用法：在本目录运行 powershell -ExecutionPolicy Bypass -File .pytest-bootstrap\build_exe.ps1
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
  --noconfirm --clean --onefile --windowed `
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

Write-Host "BUILD DONE -> dist\FormatFactory.exe"
Get-Item "dist\FormatFactory.exe" | Select-Object Name, @{n="SizeMB";e={[math]::Round($_.Length/1MB,1)}}
