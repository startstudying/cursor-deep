from __future__ import annotations

import os
import socket
import sys
import threading
import time
from contextlib import closing
from pathlib import Path

import uvicorn

try:
    import webview
except ImportError as exc:  # pragma: no cover - startup dependency guard
    raise SystemExit(
        "pywebview is not installed. Run `pip install -r requirements.txt` before starting the desktop app."
    ) from exc

DEFAULT_APP_NAME = "cursor-deep-plus"
DEFAULT_PORT = 8787
DEFAULT_ENV_TEMPLATE = """APP_NAME=cursor-deep-plus
HOST=0.0.0.0
PORT=8787

OPENAI_BASE_URL=
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o-mini

PUBLIC_MODEL_NAME=cursor-proxy
MODEL_MAP_JSON={\"cursor-proxy\":\"gpt-4o-mini\",\"cursor-fast\":\"gpt-4.1-mini\"}

GATEWAY_API_KEY=local-dev-token
REQUEST_TIMEOUT_SECONDS=600
LOG_DB_PATH=storage/chat_logs.db
MAX_LOGGED_BODY_CHARS=12000
DROP_FIELDS=
"""


def _runtime_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def _bundle_root() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return _runtime_root()


def _user_data_dir() -> Path:
    base_dir = Path(os.getenv("LOCALAPPDATA") or (Path.home() / "AppData" / "Local"))
    return base_dir / DEFAULT_APP_NAME


def _preferred_env_path() -> Path:
    if getattr(sys, "frozen", False):
        return _user_data_dir() / ".env"
    return _runtime_root() / ".env"


def _env_template() -> str:
    candidates = [
        _runtime_root() / ".env.example",
        _bundle_root() / ".env.example",
    ]

    for candidate in candidates:
        if candidate.exists():
            return candidate.read_text(encoding="utf-8")

    return DEFAULT_ENV_TEMPLATE


def _ensure_env_file() -> Path:
    env_path = _preferred_env_path()
    env_path.parent.mkdir(parents=True, exist_ok=True)

    created = False
    if not env_path.exists():
        env_path.write_text(_env_template().rstrip() + "\n", encoding="utf-8")
        created = True

    os.environ["CURSOR_DEEP_ENV_FILE"] = str(env_path)
    os.environ["CURSOR_DEEP_ENV_AUTOCREATED"] = "1" if created else "0"
    os.environ["CURSOR_DEEP_ENV_FIRST_LAUNCH"] = "1" if created else "0"
    return env_path


def _icon_path() -> str | None:
    candidate = _bundle_root() / "assets" / "app.ico"
    return str(candidate) if candidate.exists() else None


class DesktopServer:
    def __init__(self, host: str = "127.0.0.1", preferred_port: int = DEFAULT_PORT) -> None:
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
    _ensure_env_file()

    from app.config import settings

    server = DesktopServer(preferred_port=settings.port)
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
