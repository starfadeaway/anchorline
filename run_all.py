"""一键启动 Anchorline 后端 + 前端（仿 lorekeeper 的 run_all.py）。

用法：
    .venv\\Scripts\\python.exe run_all.py
    .venv\\Scripts\\python.exe run_all.py --only server     # 只起后端
    .venv\\Scripts\\python.exe run_all.py --only client     # 只起前端
    .venv\\Scripts\\python.exe run_all.py --port 8001

Ctrl+C 一次会把两个进程都收掉，不留占端口的孤儿进程。
后端：uvicorn anchorline.api.main:app（自动读 .env）；前端：npm run dev（frontend）。
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
venv_py = ROOT / ".venv" / "Scripts" / "python.exe"
if not venv_py.is_file():
    _posix = ROOT / ".venv" / "bin" / "python"
    venv_py = _posix if _posix.is_file() else Path(sys.executable)
    if venv_py != _posix:
        print(f"[警告] 没找到项目 venv（{ROOT / '.venv'}），改用当前解释器：{venv_py}")


def npm_cmd() -> str:
    exe = "npm.cmd" if os.name == "nt" else "npm"
    return shutil.which(exe) or "npm"


def spawn(label: str, args: list[str], cwd: Path) -> subprocess.Popen:
    print(f"[{label}] 启动: {' '.join(args[:4])} …")
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1", "PYTHONPATH": "src"}
    return subprocess.Popen(args, cwd=str(cwd), env=env)


def _env_value(key: str, default: str = "") -> str:
    """从项目 .env 读一个值（避免把密码硬编码在脚本里）。"""
    env_path = ROOT / ".env"
    if env_path.is_file():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith(key + "="):
                return line.split("=", 1)[1].strip()
    return default


def _port_in_use(port: int) -> bool:
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.3)
        return s.connect_ex(("127.0.0.1", port)) == 0


def main() -> None:
    ap = argparse.ArgumentParser(description="同时启动 Anchorline 前后端")
    ap.add_argument("--only", choices=["server", "client"], help="只启动其中一个")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--no-check-db", action="store_true", help="跳过 MySQL 连通性检查")
    args = ap.parse_args()

    if _port_in_use(args.port):
        print(f"[error] 端口 {args.port} 已被占用；请先停掉旧服务或换 --port")
        raise SystemExit(1)
    if args.only != "client" and _port_in_use(5173):
        print("[warn] 前端端口 5173 已被占用（可能是旧的 vite）")

    if not args.no_check_db and args.only != "client":
        try:
            import pymysql

            sys.path.insert(0, str(ROOT / "src"))
            from anchorline.config import Settings

            s = Settings(_env_file=str(ROOT / ".env"))
            c = pymysql.connect(
                host=s.mysql_host,
                port=s.mysql_port,
                user=s.mysql_user,
                password=s.mysql_password,
                database=s.mysql_database,
            )
            c.close()
            print("[check] MySQL 连接正常")
        except Exception:
            print("[check] MySQL 连接失败：先启动 MySQL 服务（例如 Start-Service mysql80，或用 mysqld 直接启动）")
            raise SystemExit(1)

    procs: list[tuple[str, subprocess.Popen]] = []
    if args.only != "client":
        procs.append((
            "server",
            spawn(
                "server",
                [str(venv_py), "-m", "uvicorn", "anchorline.api.main:app", "--host", "127.0.0.1", "--port", str(args.port)],
                ROOT,
            ),
        ))
    if args.only != "server":
        procs.append(("client", spawn("client", [npm_cmd(), "run", "dev"], ROOT / "frontend")))

    print("\n" + "=" * 56)
    print(f"  后端 API : http://127.0.0.1:{args.port}/health")
    print(f"  接口文档 : http://127.0.0.1:{args.port}/docs")
    print("  前端界面 : http://127.0.0.1:5173")
    print("  Ctrl+C 同时停止两者")
    print("=" * 56 + "\n")

    try:
        while True:
            time.sleep(1)
            for label, p in procs:
                if p.poll() is not None:
                    print(f"[{label}] 已退出(code={p.returncode})，正在停止其余进程…")
                    raise SystemExit(p.returncode or 0)
    except KeyboardInterrupt:
        pass
    finally:
        for label, p in procs:
            if p.poll() is None:
                print(f"[{label}] 停止中…")
                if os.name == "nt":
                    subprocess.run(["taskkill", "/F", "/T", "/PID", str(p.pid)], capture_output=True, check=False)
                else:
                    p.terminate()
        print("全部停止。")


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        print(f"启动失败：{type(exc).__name__}: {exc}")
        sys.exit(1)
