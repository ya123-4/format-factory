# 格式工厂（自用版）

Windows 桌面多格式转换器：视频 / 音频 / 图片 / 文档互转，支持批量队列、文件夹递归（保留相对目录结构）、停止、日志与冲突策略。核心诉求：行车记录仪 `.vdat` → `mp4`。

## 启动

双击 `格式工厂.bat`（要求系统 Python 3.11+ 已安装且带 tkinter）。首次使用在窗口内选择输出目录。

## 支持格式

| 类别 | 目标格式 |
|---|---|
| 视频 | mp4 / mkv / avi / mov / webm / gif |
| 音频 | mp3 / wav / flac / m4a / aac / ogg |
| 图片 | jpg / png / webp / bmp / tiff |
| 文档 | pdf / docx / odt / txt / xlsx / csv / pptx（按矩阵过滤，见下） |

**文档转换矩阵**（rev 5：Office 格式走 LibreOffice Kit，PDF 源走进程内引擎群）：

| 源 ↓ \ 目标 → | pdf | docx | odt | txt | xlsx | csv | pptx |
|---|---|---|---|---|---|---|---|
| pdf | ✗ | ✓ | ✗ | ✓ | ✓ | ✗ | ✓ |
| docx | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| odt | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| xlsx | ✓ | ✗ | ✗ | ✗ | ✓ | ✓ | ✗ |
| pptx | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ | ✓ |

- **PDF 源四种能力**：
  - `pdf → docx`：pdf2docx **版式重建**（表格/图片/布局还原，可编辑）；组件缺失时自动降级文本流还原。
  - `pdf → txt`：文本层提取；**扫描件（无文本层）自动 OCR**（RapidOCR，中文可用），日志会提示「已启用 OCR 识别」。
  - `pdf → xlsx`：自动检测表格（每个表格一个 sheet）；无表格的 PDF 会报「未检测到表格」。
  - `pdf → pptx`：**有文本层 → 可编辑文本框（按原坐标还原位置）**；扫描件自动回退整页图片幻灯片。
- `xlsx → csv` 即原设计的 CSV 导出语义（逗号分隔文本）。
- `txt` 文件作为转换**源**暂不支持（本机 LibreOffice Kit 无此输入能力）；安装传统 LibreOffice 后可在 `config.json` 的 `soffice_path` 配置扩展。
- `.vdat`：自动探测文件头，支持两类：
  1. **MP4 变体**（行车记录仪常见）：直接按视频转换，目标格式建议 mp4；
  2. **HLS 播放列表**（cosblaster 类工具）：`.vdat` 本体是 M3U8 清单，**分片必须位于同目录的 `<文件名>.vdat_contents\` 文件夹**内（清单缺失分片时该文件会报错并标红，其余文件不受影响）。

## 质量预设

- 音视频：同源无损（容器兼容时秒转流复制；不兼容自动降级高质量重编码并在日志提示）/ 高质量 / 中等 / 低质量。
- 图片：高质量（jpg q=2 / webp 90）/ 中等（4 / 80）/ 低（7 / 65）；png/bmp/tiff 无损。
- 文档：忽略质量设置。

## 行为约定

- 输出冲突默认**自动重命名**（`name_1.ext`），可在配置切换 覆盖 / 跳过（跳过不算失败，汇总单列）。
- 失败不自动重试；失败/取消行可右键「重新转换」。
- 停止 = 终止当前任务进程树并清理临时文件，剩余任务标记「已取消」。
- 日志：`%APPDATA%\FormatFactory\logs\conversions.log`，轮转 5MB × 3。
- 配置：`%APPDATA%\FormatFactory\config.json`。

## 第三方组件（来源 / 版本 / 许可 / 校验）

- **FFmpeg** `tools/ffmpeg/ffmpeg.exe`：ffmpeg 4.4-essentials，来源本机 ZWCAD 附带（gyan.dev essentials 构建，GPL v3）。
  - SHA-256：`8D7E6CF86BA7E0462643D3CC3745455ADCA6C9AF5795574D67D125AE238296B2`（76,434,432 字节）
  - 重建：从 <https://www.gyan.dev/ffmpeg/builds/> 下载 release-essentials 并解压 `bin/ffmpeg.exe`（可选 `ffprobe.exe`，有则优先用于媒体探测）。
- **LibreOffice Kit**（DSH bundled，`@deepseek-ai/libreoffice-kit` 0.1.2，MPL/LGPL）：默认路径写入 `config.json` 的 `kit_node` / `kit_cli`，可自行调整。

## 开发与测试

```powershell
# 测试依赖装在 workspace 内（沙箱环境无法用 pip 装到系统）
$env:PYTHONPATH="$PWD\.pytest-libs"
python -m pytest tests -v
```

- 引擎层（`app/engine/`）零 GUI 依赖，单测覆盖格式映射、兼容矩阵、冲突策略、状态机、参数构建、日志轮转。
- 集成测试用 FFmpeg lavfi 现场生成素材，真跑四类转换、递归目录、跳过、停止。

## 从源码重建（新机器/无预装依赖时）

仓库不包含体积大的二进制（`tools/`、`libs/`），按以下步骤重建：

```powershell
# 1. Python 运行依赖（PyMuPDF/pdf2docx/OCR/openpyxl/pptx 等）→ libs\
python .pytest-bootstrap\fetch_doc_tools.py
python .pytest-bootstrap\fetch_rapidocr_deps.py
python .pytest-bootstrap\fix_wheels.py        # 修正 wheel 平台变体

# 2. FFmpeg → tools\ffmpeg\
#    从 https://www.gyan.dev/ffmpeg/builds/ 下载 release-essentials，
#    解压 bin\ffmpeg.exe 到 tools\ffmpeg\（可选 ffprobe.exe）

# 3. 测试环境（可选）
python .pytest-bootstrap\fetch_pdf_tools.py   # 旧测试依赖（已并入 1）
python .pytest-bootstrap\fetch_pyinstaller.py # 打包工具

# 4. 打包 exe
powershell -ExecutionPolicy Bypass -File .pytest-bootstrap\build_exe.ps1
```

> 注：`libs/` 的 wheel 选择逻辑要求 Python 3.14（cp314 变体，排除 free-threaded cp314t 与 32 位）。

## exe 打包（FormatFactory.exe）

打包产物 `dist\FormatFactory.exe`（onefile，含 FFmpeg 与全部运行时依赖，约 250MB）。
- 设计文档：`../docs/superpowers/specs/2026-10-09-format-factory-design.md`（本仓库外）。

## 打包 exe（阶段二，验收后）

PyInstaller 打包 `app/main.py`，`tools/ffmpeg/` 随包分发。
