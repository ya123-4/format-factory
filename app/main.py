"""GUI entry point: pythonw -m app.main"""
import sys
from pathlib import Path

# 项目内 vendored 依赖（libs/）：PDF 引擎、OCR、Office 导出组件。
# 优先加载，保证双击 bat 时不依赖任何环境变量。
_LIBS = Path(__file__).resolve().parent.parent / "libs"
if _LIBS.is_dir() and str(_LIBS) not in sys.path:
    sys.path.insert(0, str(_LIBS))

import tkinter as tk

from app.config import Config
from app.gui.main_window import MainWindow


def main() -> None:
    root = tk.Tk()
    MainWindow(root, Config.load())
    root.mainloop()


if __name__ == "__main__":
    main()
