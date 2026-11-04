"""Small helpers used by several pages."""

import sys
from datetime import datetime
from pathlib import Path


def format_number(value: int) -> str:
    return f"{int(value):,}"


def format_percent(value: float, digits: int = 1) -> str:
    return f"{value:.{digits}f}%"


def format_timestamp(value: datetime, time_format: str = "24-hour") -> str:
    if time_format == "12-hour":
        return value.strftime("%d %b %Y, %I:%M %p")
    return value.strftime("%d %b %Y, %H:%M:%S")


def _development_root() -> Path:
    return Path(__file__).resolve().parents[2]


def resource_root() -> Path:
    """Read-only bundled files for development and a PyInstaller one-folder build."""
    candidates: list[Path] = []
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            candidates.append(Path(meipass))
        exe_dir = Path(sys.executable).resolve().parent
        candidates.append(exe_dir / "_internal")
        candidates.append(exe_dir)
    candidates.append(_development_root())
    for root in candidates:
        if (root / "app" / "styles" / "theme.qss").exists():
            return root
    return candidates[0]


def project_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return _development_root()


def asset_path(*parts: str) -> Path:
    return resource_root().joinpath("app", "assets", *parts)


def bundled_data_path(*parts: str) -> Path:
    return resource_root().joinpath("data", *parts)


def qss_file_url(path: Path) -> str:
    """Absolute file URL that Qt Style Sheets can load from a packaged EXE."""
    return path.resolve().as_posix()


def data_dir() -> Path:
    folder = project_root() / "data"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def settings_path() -> Path:
    return data_dir() / "settings.json"
