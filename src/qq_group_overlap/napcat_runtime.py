"""Integrated NapCat runtime: download, configure, launch, and login detection.

Goal: the user opens the app, scans a QR code, and gets their data. No manual
NapCat install, no WebUI visit, no token copying.

Layout inside the per-user data directory (see paths.default_data_dir):

    napcat/            downloaded runtime (AppImage + squashfs-root, or OneKey dir)
    napcat-home/       isolated NapCat home; NAPCAT_WORKDIR points here, so
                       config lands in napcat-home/config and the login QR in
                       napcat-home/cache/qrcode.png
    napcat-token.txt   self-generated OneBot token, reused across runs

Linux uses the official NapCat AppImage (NapNeko/NapCatAppImageBuild). Windows
uses the official OneKey installer (NapNeko/NapCatQQ), which downloads QQ and
NapCat itself; we then launch the generated napcat.bat.
"""

from __future__ import annotations

import json
import os
import platform
import secrets
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from typing import Any, Callable

from .onebot import OneBotClient, OneBotError
from .paths import default_data_dir

APPIMAGE_RELEASES_API = (
    "https://api.github.com/repos/NapNeko/NapCatAppImageBuild/releases/latest"
)
WINDOWS_RELEASES_API = (
    "https://api.github.com/repos/NapNeko/NapCatQQ/releases/latest"
)
# Download mirrors tried in order when the direct GitHub URL stalls. Downloads
# intentionally respect the system proxy (unlike loopback OneBot calls).
DOWNLOAD_MIRRORS = ("", "https://gh-proxy.com/", "https://ghfast.top/")

ONEBOT_HOST = "127.0.0.1"
ONEBOT_PORT = 3000
WEBUI_PORT = 6099
CHUNK = 1 << 16

Progress = Callable[[str, float | None], None]
Log = Callable[[str], None]


class RuntimeBootstrapError(RuntimeError):
    """Raised when the NapCat runtime cannot be prepared or started."""


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------


def runtime_dir(base: Path | None = None) -> Path:
    return (base or default_data_dir()) / "napcat"


def napcat_home(base: Path | None = None) -> Path:
    return (base or default_data_dir()) / "napcat-home"


def token_path(base: Path | None = None) -> Path:
    return (base or default_data_dir()) / "napcat-token.txt"


def platform_key() -> str:
    system = sys.platform
    machine = platform.machine().lower()
    arch = "arm64" if machine in {"arm64", "aarch64"} else "amd64"
    if system.startswith("linux"):
        return f"linux-{arch}"
    if system.startswith("win"):
        return "windows-amd64"
    raise RuntimeBootstrapError(f"暂不支持在此平台自动安装 NapCat：{system}")


# ---------------------------------------------------------------------------
# Token
# ---------------------------------------------------------------------------


def load_or_create_token(base: Path | None = None) -> str:
    path = token_path(base)
    try:
        token = path.read_text(encoding="utf-8").strip()
        if token:
            return token
    except OSError:
        pass
    token = secrets.token_urlsafe(24)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(token + "\n", encoding="utf-8")
    try:
        path.chmod(stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass
    return token


# ---------------------------------------------------------------------------
# Release lookup and download
# ---------------------------------------------------------------------------


def fetch_latest_assets(api_url: str) -> list[dict[str, Any]]:
    request = urllib.request.Request(
        api_url, headers={"User-Agent": "qq-group-overlap"}
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
        raise RuntimeBootstrapError(f"查询 NapCat 最新版本失败：{exc}") from exc
    assets = payload.get("assets")
    if not isinstance(assets, list) or not assets:
        raise RuntimeBootstrapError("NapCat 发布页没有可下载的文件")
    return assets


def pick_asset(assets: list[dict[str, Any]], key: str) -> tuple[str, str]:
    """Pick the download URL for the current platform from a release."""

    def named(name: str, url: str) -> tuple[str, str]:
        return name, url

    for asset in assets:
        name = str(asset.get("name") or "")
        url = str(asset.get("browser_download_url") or "")
        if not url:
            continue
        if key.startswith("linux") and name.startswith("QQ-"):
            if name.endswith(f"-{key.split('-', 1)[1]}.AppImage"):
                return named(name, url)
        if key.startswith("windows") and name == "NapCat.Shell.Windows.OneKey.zip":
            return named(name, url)
    raise RuntimeBootstrapError(f"发布页里找不到适合当前平台（{key}）的 NapCat 包")


def download(url: str, dest: Path, progress: Progress | None = None) -> Path:
    """Download url to dest, trying GitHub directly then mirror prefixes."""

    last_error: Exception | None = None
    for mirror in DOWNLOAD_MIRRORS:
        candidate = f"{mirror}{url}" if mirror else url
        try:
            return _download_once(candidate, dest, progress)
        except (OSError, urllib.error.URLError) as exc:
            last_error = exc
            if progress:
                progress("直连失败，尝试镜像加速…", None)
    raise RuntimeBootstrapError(f"下载 NapCat 失败：{last_error}")


def _download_once(url: str, dest: Path, progress: Progress | None) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    request = urllib.request.Request(url, headers={"User-Agent": "qq-group-overlap"})
    with urllib.request.urlopen(request, timeout=60) as response:
        total = int(response.headers.get("Content-Length") or 0)
        received = 0
        with tmp.open("wb") as out:
            while True:
                block = response.read(CHUNK)
                if not block:
                    break
                out.write(block)
                received += len(block)
                if progress:
                    if total:
                        progress(
                            f"下载 NapCat 中… {received // 1048576}/{total // 1048576} MB",
                            received / total,
                        )
                    else:
                        progress(f"下载 NapCat 中… {received // 1048576} MB", None)
    tmp.replace(dest)
    return dest


# ---------------------------------------------------------------------------
# Runtime readiness and bootstrap
# ---------------------------------------------------------------------------


def linux_launcher(base: Path | None = None) -> Path:
    return runtime_dir(base) / "squashfs-root" / "qq"


def windows_shell_dir(base: Path | None = None) -> Path | None:
    root = runtime_dir(base) / "onekey"
    if not root.is_dir():
        return None
    for child in sorted(root.iterdir()):
        if child.is_dir() and child.name.startswith("NapCat") and "Shell" in child.name:
            if (child / "napcat.bat").is_file():
                return child
    return None


def runtime_ready(base: Path | None = None) -> bool:
    try:
        key = platform_key()
    except RuntimeBootstrapError:
        return False
    if key.startswith("linux"):
        return linux_launcher(base).is_file()
    return windows_shell_dir(base) is not None


def ensure_runtime(
    progress: Progress | None = None, base: Path | None = None
) -> Path:
    """Make sure the NapCat runtime is present; download and unpack if not."""

    if runtime_ready(base):
        return runtime_dir(base)
    key = platform_key()
    assets = fetch_latest_assets(
        APPIMAGE_RELEASES_API if key.startswith("linux") else WINDOWS_RELEASES_API
    )
    name, url = pick_asset(assets, key)
    if key.startswith("linux"):
        _bootstrap_linux(url, name, progress, base)
    else:
        _bootstrap_windows(url, name, progress, base)
    if not runtime_ready(base):
        raise RuntimeBootstrapError("NapCat 安装未完成，请重试")
    return runtime_dir(base)


def _bootstrap_linux(
    url: str, name: str, progress: Progress | None, base: Path | None
) -> None:
    root = runtime_dir(base)
    root.mkdir(parents=True, exist_ok=True)
    image = download(url, root / "napcat.AppImage", progress)
    image.chmod(image.stat().st_mode | stat.S_IXUSR)
    old_extract = root / "squashfs-root"
    if old_extract.exists():
        shutil.rmtree(old_extract, ignore_errors=True)
    if progress:
        progress("解压 NapCat 运行时…", None)
    result = subprocess.run(
        [str(image), "--appimage-extract"],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=600,
    )
    if result.returncode != 0 or not linux_launcher(base).is_file():
        raise RuntimeBootstrapError(
            f"AppImage 解包失败：{result.stderr.strip() or result.stdout.strip()}"
        )


def _bootstrap_windows(
    url: str, name: str, progress: Progress | None, base: Path | None
) -> None:
    root = runtime_dir(base) / "onekey"
    root.mkdir(parents=True, exist_ok=True)
    archive = download(url, root / name, progress)
    with zipfile.ZipFile(archive) as zf:
        zf.extractall(root)
    installer = next(root.rglob("NapCatInstaller.exe"), None)
    if installer is None:
        raise RuntimeBootstrapError("OneKey 包里没有找到 NapCatInstaller.exe")
    if progress:
        progress("正在运行 NapCat 安装器（它会自动下载 QQ，请稍候）…", None)
    subprocess.Popen([str(installer)], cwd=installer.parent)
    deadline = time.monotonic() + 1800
    while time.monotonic() < deadline:
        if windows_shell_dir(base) is not None:
            return
        time.sleep(3)
    raise RuntimeBootstrapError("等待 NapCat 安装器完成超时")


# ---------------------------------------------------------------------------
# NapCat configuration (no WebUI needed)
# ---------------------------------------------------------------------------


def write_napcat_config(
    token: str,
    base: Path | None = None,
    port: int = ONEBOT_PORT,
) -> Path:
    """Write onebot11.json so NapCat serves OneBot HTTP on loopback.

    Written before every launch so a stale or missing config never blocks the
    integrated flow. On Windows the file also goes into the Shell directory's
    config folder, which NapCat.Shell reads regardless of NAPCAT_WORKDIR.
    """

    payload = {
        "network": {
            "httpServers": [
                {
                    "name": "qq-group-overlap",
                    "enable": True,
                    "port": port,
                    "host": ONEBOT_HOST,
                    "enableCors": False,
                    "enableWebsocket": False,
                    "messagePostFormat": "array",
                    "token": token,
                    "debug": False,
                }
            ],
            "httpClients": [],
            "websocketServers": [],
            "websocketClients": [],
        },
        "musicSignUrl": "",
        "enableLocalFile2Url": False,
        "parseMultMsg": False,
    }
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"

    targets = [napcat_home(base) / "config" / "onebot11.json"]
    shell = windows_shell_dir(base)
    if shell is not None:
        targets.append(shell / "config" / "onebot11.json")
    for target in targets:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    return targets[0]


# ---------------------------------------------------------------------------
# Session: process lifecycle + login detection
# ---------------------------------------------------------------------------


class NapCatSession:
    """Owns the NapCat child process and login polling for the GUI."""

    def __init__(
        self,
        token: str,
        base: Path | None = None,
        port: int = ONEBOT_PORT,
        log: Log | None = None,
    ) -> None:
        self.base = base
        self.token = token
        self.port = port
        self.log = log or (lambda _msg: None)
        self.process: subprocess.Popen[bytes] | None = None
        self._client = OneBotClient(f"http://{ONEBOT_HOST}:{port}", token, timeout=5)

    # -- paths -------------------------------------------------------------

    @property
    def qr_path(self) -> Path:
        return napcat_home(self.base) / "cache" / "qrcode.png"

    @property
    def api_url(self) -> str:
        return f"http://{ONEBOT_HOST}:{self.port}"

    # -- lifecycle ---------------------------------------------------------

    def is_running(self) -> bool:
        return self.process is not None and self.process.poll() is None

    def start(self) -> None:
        if self.is_running():
            return
        key = platform_key()
        home = napcat_home(self.base)
        for sub in ("cache", "config", "logs", "home"):
            (home / sub).mkdir(parents=True, exist_ok=True)
        write_napcat_config(self.token, self.base, self.port)
        if key.startswith("linux"):
            self._start_linux(home)
        else:
            self._start_windows(home)

    def stop(self) -> None:
        process = self.process
        self.process = None
        if process is None or process.poll() is not None:
            return
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()

    # -- platform launchers --------------------------------------------------

    def _start_linux(self, home: Path) -> None:
        launcher = linux_launcher(self.base)
        if not launcher.is_file():
            raise RuntimeBootstrapError("NapCat 运行时缺失，请先完成下载")
        if not os.environ.get("DISPLAY"):
            raise RuntimeBootstrapError("检测不到图形界面（DISPLAY），无法弹出二维码登录")
        appdir = launcher.parent
        env = dict(os.environ)
        env.update(
            {
                "HOME": str(home / "home"),
                "NAPCAT_WORKDIR": str(home),
                "APPDIR": str(appdir),
                "PATH": f"{appdir}:{appdir / 'usr' / 'sbin'}:{env.get('PATH', '')}",
                "LD_LIBRARY_PATH": f"{appdir / 'usr' / 'lib'}"
                + (f":{os.environ['LD_LIBRARY_PATH']}" if os.environ.get("LD_LIBRARY_PATH") else ""),
                "XDG_DATA_DIRS": f"{appdir / 'usr' / 'share'}:{env.get('XDG_DATA_DIRS', '/usr/local/share:/usr/share')}",
                "XDG_CONFIG_HOME": str(home / "home" / ".config"),
            }
        )
        gsettings = appdir / "usr" / "share" / "glib-2.0" / "schemas"
        if gsettings.is_dir():
            env["GSETTINGS_SCHEMA_DIR"] = str(gsettings)
        log_file = (home / "logs" / "napcat.log").open("ab")
        self.process = subprocess.Popen(
            [str(launcher), "--no-sandbox"],
            cwd=str(home),
            env=env,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )
        self.log(f"NapCat 已启动（pid {self.process.pid}）")

    def _start_windows(self, home: Path) -> None:
        shell = windows_shell_dir(self.base)
        if shell is None:
            raise RuntimeBootstrapError("NapCat 运行时缺失，请先完成下载")
        env = dict(os.environ)
        env["NAPCAT_WORKDIR"] = str(home)
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        self.process = subprocess.Popen(
            ["cmd.exe", "/c", str(shell / "napcat.bat")],
            cwd=str(shell),
            env=env,
            stdin=subprocess.DEVNULL,
            creationflags=creationflags,
        )
        self.log(f"NapCat 已启动（pid {self.process.pid}）")

    # -- login ---------------------------------------------------------------

    def current_uin(self) -> str | None:
        """Return the logged-in QQ number, or None if not logged in yet."""

        try:
            return self._client.get_login_user_id()
        except (OneBotError, OSError):
            return None

    def wait_for_login(self, timeout: float = 120, interval: float = 2.0) -> str:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            uin = self.current_uin()
            if uin:
                return uin
            time.sleep(interval)
        raise RuntimeBootstrapError("等待扫码登录超时")
