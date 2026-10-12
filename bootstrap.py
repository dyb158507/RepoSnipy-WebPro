# -*- coding: utf-8 -*-
"""启动前的环境自检与修复。

这个项目按"整个文件夹拷走就能跑"设计，但有两处会写死绝对路径：

1. `.venv/pyvenv.cfg` 里的 `home` —— 指向基础解释器所在的目录
2. `.venv/Scripts/python.exe` —— 这是 CPython 生成的启动器，里面也内嵌了基础解释器的路径

换目录或换电脑之后这两处都会失效，表现为：
    - "Python path configuration" 致命错误（pyvenv.cfg 失效）
    - "找不到 python310.dll"（启动器失效）
    - "uv trampoline failed to spawn Python child process"（如果是 uv 建的 venv）

本脚本由**项目自带的 Python310** 运行——它不依赖虚拟环境，所以哪怕 venv 已经坏了
也照样能跑。它会按顺序尝试修复，最后实际启动一次 venv 验证结果。

重复运行是安全的：一切正常时不会改动任何文件。
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENV_DIR = ROOT / ".venv"
SCRIPTS_DIR = VENV_DIR / "Scripts"
VENV_PYTHON = SCRIPTS_DIR / "python.exe"
VENV_CFG = VENV_DIR / "pyvenv.cfg"


def note(message: str) -> None:
    print(f"  {message}")


def fail(message: str) -> int:
    print(f"\n[!] {message}")
    return 1


def find_base_python() -> Path | None:
    """在 Python310 下找基础解释器。

    只认 Python310 的**直接子目录**：标准库里还有几个同名模板
    （如 `Lib\\venv\\scripts\\nt\\python.exe`），递归搜索会误把它们当基础解释器。
    再用同目录下有没有 `python3*.dll` 做一次校验。
    """
    base_root = ROOT / "Python310"
    if not base_root.is_dir():
        return None

    candidates = []
    for child in sorted(base_root.iterdir()):
        exe = child / "python.exe"
        if not (child.is_dir() and exe.is_file()):
            continue
        if not any(child.glob("python3*.dll")):
            continue
        candidates.append(exe)
    if not candidates:
        return None

    # 优先用 pyvenv.cfg 里记录的那个（前提是它确实是 Python310 的直接子目录）
    home = recorded_home()
    if home:
        home_path = Path(home)
        if home_path.parent == base_root:
            for exe in candidates:
                if exe.parent == home_path:
                    return exe
    return candidates[0]


def read_cfg() -> list[str]:
    return VENV_CFG.read_text(encoding="utf-8").splitlines()


def recorded_home() -> str | None:
    if not VENV_CFG.exists():
        return None
    for line in read_cfg():
        if line.strip().lower().startswith("home"):
            return line.partition("=")[2].strip()
    return None


def write_cfg(lines: list[str]) -> None:
    VENV_CFG.write_text("\r\n".join(lines) + "\r\n", encoding="utf-8", newline="")


def fix_cfg(base_dir: Path) -> bool:
    """把 pyvenv.cfg 里的 home 改成本机路径。返回是否改动过。"""
    lines = read_cfg()
    new_lines = [
        f"home = {base_dir}" if line.strip().lower().startswith("home") else line
        for line in lines
    ]
    if new_lines == lines:
        return False
    write_cfg(new_lines)
    return True


def venv_runs() -> tuple[bool, str]:
    if not VENV_PYTHON.exists():
        return False, "找不到 .venv\\Scripts\\python.exe"
    try:
        result = subprocess.run(
            [str(VENV_PYTHON), "-c", "print(1)"],
            capture_output=True,
            timeout=120,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return False, f"{type(exc).__name__}: {exc}"
    if result.returncode == 0:
        return True, ""
    detail = (result.stderr or result.stdout or b"").decode("utf-8", "replace").strip()
    return False, detail.splitlines()[-1] if detail else f"退出码 {result.returncode}"


def rebuild_launcher(base_python: Path) -> None:
    """用自带解释器即时生成一个空 venv，把它的启动器拿来替换掉失效的那个。

    CPython 的 venv 启动器里内嵌了基础解释器的路径，只能在目标机器上现生成。
    """
    temp_root = Path(tempfile.mkdtemp(prefix="reposnipy_launcher_"))
    try:
        subprocess.run(
            [str(base_python), "-m", "venv", "--without-pip", str(temp_root / "v")],
            check=True,
            capture_output=True,
            timeout=300,
        )
        for name in ("python.exe", "pythonw.exe"):
            source = temp_root / "v" / "Scripts" / name
            if source.exists():
                shutil.copy2(source, SCRIPTS_DIR / name)
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)


def main() -> int:
    print("=" * 62)
    print("  RepoSnipy 环境自检")
    print("=" * 62)

    if not VENV_DIR.is_dir():
        return fail("找不到 .venv 目录，请确认文件夹是完整复制的。")
    if not VENV_CFG.exists():
        return fail("找不到 .venv\\pyvenv.cfg，虚拟环境不完整。")

    base_python = find_base_python()
    if base_python is None:
        return fail("找不到项目自带的 Python310\\...\\python.exe，请确认文件夹完整。")

    ok, detail = venv_runs()
    if ok:
        home = recorded_home()
        if home and home != str(base_python.parent):
            fix_cfg(base_python.parent)
            note("虚拟环境路径记录已更新（本次不影响使用）")
        else:
            note("虚拟环境正常")
        print("-" * 62)
        return 0

    note(f"虚拟环境无法启动：{detail}")
    note("正在修复 ...")

    if fix_cfg(base_python.parent):
        note(f"已修正 .venv\\pyvenv.cfg 的 home -> {base_python.parent}")

    ok, detail = venv_runs()
    if not ok:
        note("启动器失效，正在按当前路径重新生成 ...")
        try:
            rebuild_launcher(base_python)
        except Exception as exc:  # noqa: BLE001
            return fail(
                f"重新生成启动器失败：{type(exc).__name__}: {exc}\n"
                "    请确认 .venv\\Scripts 目录可写，且杀毒软件没有拦截。"
            )
        ok, detail = venv_runs()

    if not ok:
        return fail(
            f"修复后仍无法启动：{detail}\n"
            "    可以把这段信息发给维护者；或删除 .venv 后按 requirements.txt 重建。"
        )

    note("修复完成，虚拟环境已可用")
    print("-" * 62)
    return 0


if __name__ == "__main__":
    sys.exit(main())
