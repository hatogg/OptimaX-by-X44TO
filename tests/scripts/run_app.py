"""Запуск OptimaX із вихідних файлів з аргументами (для --selftest у тестах)."""
import _boot
import os
import runpy
import sys

sys.argv = ["optimizer.py"] + sys.argv[1:]
runpy.run_path(os.path.join(_boot.ROOT, "optimizer.py"), run_name="__main__")
