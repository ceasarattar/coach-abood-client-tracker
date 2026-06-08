"""
Launcher for the Coach Abood dashboard.

Goals:
  * Single instance — if the dashboard is already running, just open the
    browser to it instead of starting a second copy.
  * Zero-friction — double-click the desktop shortcut (which calls this) and
    the browser opens on the dashboard automatically.

This is the entry point the desktop shortcut and setup scripts use. Running
`python app.py` directly still works for development.
"""
import os
import sys
import socket
import threading
import webbrowser

HOST = "127.0.0.1"
PORT = int(os.environ.get("PORT", "5000"))
URL = f"http://{HOST}:{PORT}/"


def _already_running() -> bool:
    """True if something is already accepting connections on HOST:PORT."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.4)
        return sock.connect_ex((HOST, PORT)) == 0


def main() -> int:
    if _already_running():
        print(f"Dashboard already running — opening {URL}")
        webbrowser.open(URL)
        return 0

    # Import here so the port check above stays fast and import errors surface
    # only when we actually intend to start the server.
    import app

    # Open the browser shortly after the server starts listening.
    threading.Timer(1.5, lambda: webbrowser.open(URL)).start()

    print(f"Starting Coach Abood dashboard on {URL}")
    try:
        # use_reloader=False so we never spawn a second (child) process — that
        # would defeat single-instance and double-open the browser.
        app.app.run(host=HOST, port=PORT, debug=False, use_reloader=False)
    except OSError as exc:
        # Lost the race (started between our check and bind) — just open it.
        print(f"Could not bind {URL} ({exc}); opening existing instance.")
        webbrowser.open(URL)
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
