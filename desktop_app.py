from __future__ import annotations

import socket
import sys
import threading
import time
from contextlib import closing
from pathlib import Path

import uvicorn

from app.config import settings

try:
    import webview
except ImportError as exc:  # pragma: no cover - startup dependency guard
    raise SystemExit(
        "pywebview is not installed. Run `pip install -r requirements.txt` before starting the desktop app."
    ) from exc


def _icon_path() -> str | None:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        candidate = Path(sys._MEIPASS) / "assets" / "app.ico"
    else:
        candidate = Path(__file__).resolve().parent / "assets" / "app.ico"
    return str(candidate) if candidate.exists() else None


class DesktopServer:
    def __init__(self, host: str = "127.0.0.1", preferred_port: int = settings.port) -> None:
        self.host = host
        self.port = self._find_free_port(preferred_port)
        self._server = uvicorn.Server(
            uvicorn.Config(
                "app.main:app",
                host=self.host,
                port=self.port,
                log_level="info",
                access_log=False,
            )
        )
        self._thread = threading.Thread(target=self._server.run, daemon=True)

    def start(self) -> None:
        self._thread.start()
        self._wait_until_ready()

    def stop(self) -> None:
        self._server.should_exit = True
        if self._thread.is_alive():
            self._thread.join(timeout=5)

    @property
    def desktop_url(self) -> str:
        return f"http://{self.host}:{self.port}/desktop"

    def _wait_until_ready(self, timeout_seconds: float = 20) -> None:
        deadline = time.time() + timeout_seconds

        while time.time() < deadline:
            if not self._thread.is_alive():
                raise RuntimeError("Desktop service stopped before the window could open.")

            with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as probe:
                probe.settimeout(0.2)
                if probe.connect_ex((self.host, self.port)) == 0:
                    return

            time.sleep(0.2)

        raise TimeoutError("Desktop service did not start within the expected time.")

    @staticmethod
    def _find_free_port(preferred_port: int) -> int:
        with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as probe:
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            if probe.connect_ex(("127.0.0.1", preferred_port)) != 0:
                return preferred_port

        with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as fallback:
            fallback.bind(("127.0.0.1", 0))
            return int(fallback.getsockname()[1])


def main() -> None:
    server = DesktopServer()
    server.start()

    window = webview.create_window(
        f"{settings.app_name} Desktop",
        server.desktop_url,
        width=1280,
        height=860,
        min_size=(1024, 700),
        confirm_close=True,
    )

    icon_path = _icon_path()
    if icon_path:
        try:
            window.icon = icon_path
        except Exception:
            pass

    try:
        webview.start()
    finally:
        server.stop()


if __name__ == "__main__":
    main()
