"""
Growcom Ecosystem Launcher (Local & Cloud Ready).
Starts the Central Data API (FastAPI) and automatically launches the Growcom Events Discord bot
inside a single unified process tree (allowing 100% free single-container hosting on Render,
Koyeb, or Hugging Face Spaces!).
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")

PYTHON_EXE = sys.executable


def main() -> None:
    os.environ["PYTHONUTF8"] = "1"
    processes: list[tuple[str, subprocess.Popen]] = []

    print("=" * 68)
    print(" [Growcom] Starting Growcom Events by Manwel Ecosystem")
    print("=" * 68)

    # Support cloud platforms (Render / Koyeb / HF Spaces) that inject $PORT
    cloud_port = os.getenv("PORT", "").strip()
    api_host = "0.0.0.0" if cloud_port else os.getenv("CENTRAL_API_HOST", "127.0.0.1")
    api_port = cloud_port or os.getenv("CENTRAL_API_PORT", "8000")

    # Ensure bots connect to the local FastAPI instance on the active port
    os.environ["CENTRAL_API_URL"] = f"http://127.0.0.1:{api_port}"

    api_cmd = [
        PYTHON_EXE,
        "-m",
        "uvicorn",
        "app.main:app",
        "--host",
        api_host,
        "--port",
        api_port,
    ]
    print(f"[1/2] Launching Central Data API on http://{api_host}:{api_port} ...")
    api_proc = subprocess.Popen(api_cmd, cwd=str(ROOT / "services" / "central-data-api"))
    processes.append(("central-data-api", api_proc))
    time.sleep(2.5)

    # Launch Growcom Events Bot ( plus any optional extra bots if tokens are provided)
    bot_configs = [
        ("event-bot", "EVENT_BOT_TOKEN", ROOT / "bots" / "event-bot" / "src" / "bot.py"),
        ("parser-bot", "PARSER_BOT_TOKEN", ROOT / "bots" / "parser-bot" / "src" / "bot.py"),
        ("converter-bot", "CONVERTER_BOT_TOKEN", ROOT / "bots" / "converter-bot" / "src" / "bot.py"),
    ]

    for name, env_var, script_path in bot_configs:
        token = os.getenv(env_var, "").strip()
        if token and script_path.exists():
            print(f"[2/2] Launching {name} ...")
            proc = subprocess.Popen([PYTHON_EXE, str(script_path)], cwd=str(ROOT))
            processes.append((name, proc))

    print("\n[OK] Growcom Events by Manwel is online! Press Ctrl+C to stop.\n")
    try:
        while True:
            # Self-healing check: if a child process exits unexpectedly in the cloud, restart it
            for idx, (name, proc) in enumerate(processes):
                if proc.poll() is not None:
                    print(f"[WARN] Process {name} exited with code {proc.returncode}. Restarting...")
                    if name == "central-data-api":
                        new_proc = subprocess.Popen(api_cmd, cwd=str(ROOT / "services" / "central-data-api"))
                    else:
                        script_map = {b[0]: b[2] for b in bot_configs}
                        new_proc = subprocess.Popen([PYTHON_EXE, str(script_map[name])], cwd=str(ROOT))
                    processes[idx] = (name, new_proc)
            time.sleep(3.0)
    except KeyboardInterrupt:
        print("\nShutting down Growcom services...")
        for _, proc in processes:
            proc.terminate()
        for _, proc in processes:
            proc.wait(timeout=5)


if __name__ == "__main__":
    main()
