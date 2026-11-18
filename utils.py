"""Utility functions for Telegram Video Downloader."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse


INVALID_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
TELEGRAM_URL_RE = re.compile(
    r"(?:https?://)?(?:t\.me|telegram\.me)/(?:(?P<private>c)/)?(?P<username>[a-zA-Z0-9_]+)/(?P<msg_id>\d+)",
    re.IGNORECASE,
)
CHANNEL_URL_RE = re.compile(
    r"(?:https?://)?(?:t\.me|telegram\.me)/(?:(?P<private>c)/)?(?P<username>[a-zA-Z0-9_]+)/?(?:\?.*)?$",
    re.IGNORECASE,
)
USERNAME_RE = re.compile(r"^@?(?P<username>[a-zA-Z0-9_]{4,})$")


def sanitize_filename(name: str, max_length: int = 180) -> str:
    """Remove illegal characters and limit length for Windows compatibility."""
    if not name or not name.strip():
        return "video"

    name = name.strip()
    name = INVALID_FILENAME_CHARS.sub("_", name)
    name = re.sub(r"\s+", " ", name)
    name = name.strip(" .")

    if len(name) > max_length:
        name = name[:max_length].rstrip(" .")

    return name or "video"


def format_size(size_bytes: Optional[int]) -> str:
    if size_bytes is None or size_bytes < 0:
        return "Unknown"
    size = float(size_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024:
            return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} B"
        size /= 1024
    return f"{size:.1f} PB"


def format_duration(seconds: Optional[int]) -> str:
    if seconds is None or seconds < 0:
        return "Unknown"
    hours, remainder = divmod(int(seconds), 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def format_date(dt: Optional[datetime]) -> str:
    if not dt:
        return "Unknown"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone().strftime("%Y-%m-%d %H:%M")


def parse_channel_input(text: str) -> dict:
    """
    Parse channel link / username / message link.
    Returns dict with keys: username, message_id (optional), raw
    """
    text = text.strip()

    # Message link
    m = TELEGRAM_URL_RE.search(text)
    if m and not (m.group("username").lower() == "c" and not m.group("private")):
        username = m.group("username")
        if m.group("private"):
            username = f"-100{username}"
        return {
            "username": username,
            "message_id": int(m.group("msg_id")),
            "raw": text,
        }

    # Channel link
    m = CHANNEL_URL_RE.search(text)
    if m:
        username = m.group("username")
        if m.group("private"):
            username = f"-100{username}"
        return {
            "username": username,
            "message_id": None,
            "raw": text,
        }

    # @username or plain username
    m = USERNAME_RE.match(text)
    if m:
        return {
            "username": m.group("username"),
            "message_id": None,
            "raw": text,
        }

    raise ValueError(f"Invalid channel link or username: {text}")


def parse_selection(text: str, max_index: int) -> list[int]:
    """
    Parse selection like: 1,3,5-8,12
    Returns sorted unique 1-based indices.
    """
    text = text.strip().replace(" ", "")
    if not text:
        raise ValueError("No numbers were entered")

    selected: set[int] = set()

    for part in text.split(","):
        if not part:
            continue
        if "-" in part:
            try:
                start_s, end_s = part.split("-", 1)
                start, end = int(start_s), int(end_s)
            except ValueError:
                raise ValueError(f"Invalid range: {part}")
            if start > end:
                start, end = end, start
            for i in range(start, end + 1):
                if 1 <= i <= max_index:
                    selected.add(i)
                else:
                    raise ValueError(f"Number {i} is out of range (1-{max_index})")
        else:
            try:
                num = int(part)
            except ValueError:
                raise ValueError(f"Invalid number: {part}")
            if 1 <= num <= max_index:
                selected.add(num)
            else:
                raise ValueError(f"Number {num} is out of range (1-{max_index})")

    if not selected:
        raise ValueError("No valid videos were selected")

    return sorted(selected)


def ensure_unique_path(path: Path) -> Path:
    """If file exists, append (1), (2), ... until unique."""
    if not path.exists():
        return path

    stem = path.stem
    suffix = path.suffix
    parent = path.parent
    counter = 1
    while True:
        new_path = parent / f"{stem} ({counter}){suffix}"
        if not new_path.exists():
            return new_path
        counter += 1


def print_header(title: str) -> None:
    line = "=" * 60
    print(f"\n{line}")
    print(f"  {title}")
    print(f"{line}")


def print_separator() -> None:
    print("-" * 60)