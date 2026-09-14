"""
UniScholar WebUI 快速启动入口
直接运行: py -3.10 app.py 或双击 run.bat
"""
import os
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

import utils.network_config  # noqa: F401
from web.app import build_ui, launch_claude_ui

if __name__ == "__main__":
    demo = build_ui()
    port = int(os.getenv("PORT", "7860"))
    print("========================================================")
    print("  UniScholar (联智学者) WebUI 正在启动...")
    print(f"  浏览器访问地址: http://127.0.0.1:{port}")
    print("========================================================")
    launch_claude_ui(demo, server_name="127.0.0.1", server_port=port, inbrowser=False)

