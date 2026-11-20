"""NETWORK WATCH - Windows desktop launcher."""

import ctypes
import os
import socket
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path


# Configure environment BEFORE importing the backend.
os.environ["DEMO_MODE"] = "false"
os.environ["FRONTEND_ORIGIN"] = "http://127.0.0.1"

if getattr(sys, "frozen", False):
    PROJECT_DIR = Path(sys._MEIPASS)
else:
    PROJECT_DIR = Path(__file__).resolve().parent

sys.path.insert(0, str(PROJECT_DIR))


def is_admin():
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def find_npcap():
    windows = Path(os.environ.get("SystemRoot", r"C:\Windows"))

    candidates = [
        windows / "System32" / "Npcap" / "wpcap.dll",
        windows / "System32" / "wpcap.dll",
        windows / "SysWOW64" / "Npcap" / "wpcap.dll",
        windows / "SysWOW64" / "wpcap.dll",
    ]

    return next((path for path in candidates if path.exists()), None)


def find_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def wait_for_backend(url, server_thread, timeout=45):
    deadline = time.time() + timeout

    while time.time() < deadline:
        if not server_thread.is_alive():
            return False

        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if response.status == 200:
                    return True
        except (urllib.error.URLError, TimeoutError, OSError):
            pass

        time.sleep(0.5)

    return False


def main():
    print("=" * 58)
    print("              NETWORK WATCH")
    print("          LOCAL NETWORK MONITOR")
    print("=" * 58)

    print("\n[1/4] Checking Windows permissions...")

    if is_admin():
        print("[OK] Administrator privileges detected.")
    else:
        print("[WARNING] Not running as Administrator.")
        print("         Packet capture may require elevated privileges.")

    print("\n[2/4] Checking Npcap...")

    npcap = find_npcap()

    if npcap:
        print(f"[OK] Npcap detected: {npcap}")
    else:
        print("[WARNING] Npcap was not detected.")
        print("         Live packet capture may not work.")
        print("         Install Npcap from https://npcap.com/")

    print("\n[3/4] Starting local monitoring server...")

    port = find_free_port()
    dashboard_url = f"http://127.0.0.1:{port}"
    health_url = f"{dashboard_url}/api/health"

    try:
        import uvicorn
        from backend.main import app
    except Exception as exc:
        print(f"\n[ERROR] Backend import failed: {exc}")
        input("\nPress Enter to exit...")
        return

    os.environ["DEMO_MODE"] = "false"

    config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=port,
        log_level="info",
        access_log=False,
    )

    server = uvicorn.Server(config)

    server_thread = threading.Thread(
        target=server.run,
        daemon=True,
        name="network-watch-server",
    )

    server_thread.start()

    if not wait_for_backend(health_url, server_thread):
        server.should_exit = True
        print("\n[ERROR] The local backend did not become ready.")
        input("\nPress Enter to exit...")
        return

    print(f"[OK] Backend running at {dashboard_url}")

    print("\n[4/4] Opening dashboard...")

    webbrowser.open(dashboard_url)

    print("\n" + "=" * 58)
    print(" NETWORK WATCH IS RUNNING")
    print(f" Dashboard: {dashboard_url}")
    print(" Mode: LOCAL LIVE MONITORING")
    print(" Database: %LOCALAPPDATA%\\NetworkWatch\\data")
    print("=" * 58)
    print("\nKeep this window open while using NETWORK WATCH.")
    print("Press Ctrl+C here to stop the application.\n")

    try:
        while server_thread.is_alive():
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[INFO] Shutting down NETWORK WATCH...")
    finally:
        server.should_exit = True
        server_thread.join(timeout=10)
        print("[OK] NETWORK WATCH stopped.")


if __name__ == "__main__":
    main()
