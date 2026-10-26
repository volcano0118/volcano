"""Local settings and filesystem helpers for the Kuromi app."""

from __future__ import annotations

import os
import sys
from pathlib import Path

try:  # local file, not tracked by git
    from ui.secrets import DEEPSEEK_API_KEY
except ImportError:
    DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-chat"

SYSTEM_PROMPT = (
    "你是库洛米（Kuromi），三丽鸥的兔子角色：黑兜帽、粉色骷髅、调皮又爱逞强，"
    "说话活泼、带点小傲娇，但心很软。用中文回答，简洁自然，不要长篇大论。"
)


def resource_path(name: str) -> Path:
    """Path to a bundled asset (works from source and from a PyInstaller build)."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return base / "character" / "assets" / name


def user_data_path(name: str) -> Path:
    """Writable per-user location for runtime data."""
    base = Path(os.environ.get("APPDATA") or Path.home()) / "KuromiPet"
    base.mkdir(parents=True, exist_ok=True)
    return base / name
