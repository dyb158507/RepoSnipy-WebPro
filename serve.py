# -*- coding: utf-8 -*-
"""RepoSnipy 启动器。

负责：设置离线环境变量 -> 启动 FastAPI 后端 -> 等服务就绪后自动打开浏览器。
双击 run_api.bat 即可，不需要手动敲命令。
"""
from __future__ import annotations

import os
import socket
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# 离线运行：模型就在项目内的 models 目录，不需要联网
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
os.environ.setdefault("HF_HOME", str(PROJECT_ROOT / "models" / "hf"))
os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

HOST = os.environ.get("REPOSNIPY_HOST", "127.0.0.1")
PORT = int(os.environ.get("REPOSNIPY_PORT", "8000"))
DATASET = os.environ.get("REPOSNIPY_DATASET", "developing").strip().lower()
INDEX_FILE = PROJECT_ROOT / "data" / ("index.bin" if DATASET == "product" else "index_developing.bin")
OPEN_URL = os.environ.get("REPOSNIPY_OPEN", f"http://localhost:{PORT}/")
OPEN_BROWSER = os.environ.get("REPOSNIPY_NO_BROWSER", "").strip() not in ("1", "true", "yes")


def port_in_use(host: str, port: int) -> bool:
    target = "127.0.0.1" if host in ("0.0.0.0", "") else host
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.6)
        return sock.connect_ex((target, port)) == 0


def open_browser_when_ready() -> None:
    """等后端起来、索引载入完成后再打开浏览器。"""
    health = f"http://127.0.0.1:{PORT}/api/health"
    deadline = time.time() + 90
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(health, timeout=2) as response:
                if response.status == 200:
                    break
        except (urllib.error.URLError, OSError):
            time.sleep(0.5)
    else:
        return

    ready = f"http://127.0.0.1:{PORT}/api/meta"
    deadline = time.time() + 120
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(ready, timeout=3) as response:
                if b'"status":"ready"' in response.read():
                    break
        except (urllib.error.URLError, OSError):
            pass
        time.sleep(0.5)

    try:
        webbrowser.open(OPEN_URL)
    except Exception:  # noqa: BLE001
        pass


def main() -> int:
    print("=" * 62)
    print("  RepoSnipy · 语义化 Python 仓库检索")
    print("=" * 62)

    if not INDEX_FILE.exists():
        print(f"[!] 找不到索引文件 {INDEX_FILE.relative_to(PROJECT_ROOT)}")
        print("    请确认 data 目录完整。")
        return 1

    if not (PROJECT_ROOT / "models" / "RepoSim4Py").exists():
        print("[!] 找不到 models/RepoSim4Py，编码新仓库时会不可用；")
        print("    已有的索引检索不受影响。")

    if not (PROJECT_ROOT / "frontend" / "dist" / "index.html").exists():
        print("[!] 前端还没有构建（缺少 frontend/dist/index.html）。")
        print("    在 frontend 目录执行 npm install 与 npm run build，")
        print("    或者改用 run_web.bat 启动开发模式。")
        return 1

    if port_in_use(HOST, PORT):
        print(f"[!] 端口 {PORT} 已被占用，可能上一个实例还在运行。")
        print(f"    若 {OPEN_URL} 能打开就直接用；否则先关掉旧窗口，")
        print("    或设置环境变量 REPOSNIPY_PORT 换一个端口再启动。")
        if OPEN_BROWSER:
            try:
                webbrowser.open(OPEN_URL)
            except Exception:  # noqa: BLE001
                pass
        return 1

    device_note = "CPU"
    try:
        import torch

        if torch.cuda.is_available():
            device_note = f"CUDA ({torch.cuda.get_device_name(0)})"
    except Exception:  # noqa: BLE001
        pass

    print(f"  数据集   : {DATASET}")
    print(f"  计算设备 : {device_note}")
    print(f"  界面地址 : {OPEN_URL}")
    print(f"  接口文档 : http://localhost:{PORT}/docs")
    print("  首次启动需要读取向量索引，约 3-5 秒；按 Ctrl+C 停止。")
    print("-" * 62)

    if OPEN_BROWSER:
        threading.Thread(target=open_browser_when_ready, daemon=True).start()

    import uvicorn

    from api.main import app

    uvicorn.run(app, host=HOST, port=PORT, log_level="info")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\n已停止。")
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        print("\n启动失败：")
        print(f"  {type(exc).__name__}: {exc}")
        import traceback

        traceback.print_exc()
        try:
            input("\n按回车键关闭窗口…")
        except EOFError:
            pass
        raise SystemExit(1)
