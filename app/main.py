"""GUI entry point: pythonw app/main.py"""
import tkinter as tk

from app.config import Config
from app.gui.main_window import MainWindow


def main() -> None:
    root = tk.Tk()
    MainWindow(root, Config.load())
    root.mainloop()


if __name__ == "__main__":
    main()
