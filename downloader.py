"""Download videos with progress and safe file handling."""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Optional

from telethon import TelegramClient
from telethon.errors import FloodWaitError

from logger import setup_logger
from utils import ensure_unique_path, format_size, print_header, sanitize_filename
from video_scanner import VideoInfo

logger = setup_logger(__name__)


class DownloadStats:
    def __init__(self):
        self.total = 0
        self.success = 0
        self.skipped = 0
        self.failed = 0
        self.failed_items: list[tuple[str, str]] = []  # (name, reason)


def _build_filename(video: VideoInfo, index: int) -> str:
    """Create a safe filename."""
    if video.file_name:
        name = Path(video.file_name).stem
        ext = Path(video.file_name).suffix or ".mp4"
    else:
        name = video.display_title()
        ext = ".mp4"

    name = sanitize_filename(name)
    # Prefix with zero-padded index for ordering
    return f"{index:03d} - {name}{ext}"


class ProgressTracker:
    def __init__(self, label: str, total_size: Optional[int]):
        self.label = label
        self.total_size = total_size or 0
        self.start_time = time.time()
        self.last_print = 0.0

    def __call__(self, current: int, total: int):
        # Throttle printing
        now = time.time()
        if now - self.last_print < 0.35 and current != total:
            return
        self.last_print = now

        total = total or self.total_size or 1
        percent = min(100.0, (current / total) * 100) if total else 0
        elapsed = now - self.start_time
        speed = current / elapsed if elapsed > 0 else 0
        remaining = (total - current) / speed if speed > 0 else 0

        bar_len = 30
        filled = int(bar_len * percent / 100)
        bar = "█" * filled + "░" * (bar_len - filled)

        eta_str = time.strftime("%H:%M:%S", time.gmtime(remaining)) if remaining else "--:--"

        print(
            f"\r  {bar} {percent:5.1f}% | "
            f"{format_size(current)} / {format_size(total)} | "
            f"{format_size(int(speed))}/s | ETA {eta_str}   ",
            end="",
            flush=True,
        )


async def download_videos(
    client: TelegramClient,
    videos: list[VideoInfo],
    download_dir: Path,
) -> DownloadStats:
    stats = DownloadStats()
    stats.total = len(videos)

    print_header("DOWNLOADING")
    print(f"Folder: {download_dir}")
    print(f"Number of videos: {stats.total}\n")

    for idx, video in enumerate(videos, 1):
        filename = _build_filename(video, idx)
        target = download_dir / filename

        # Handle existing file
        if target.exists():
            print(f"[{idx}/{stats.total}] File already exists: {filename}")
            choice = input("  [S]kip / [O]verwrite / [R]ename ? [S]: ").strip().lower()
            if choice in ("o", "overwrite"):
                try:
                    target.unlink()
                except OSError as e:
                    reason = f"Cannot delete the existing file: {e}"
                    print(f"  ✗ {reason}")
                    stats.failed += 1
                    stats.failed_items.append((filename, reason))
                    continue
            elif choice in ("r", "rename"):
                target = ensure_unique_path(target)
                filename = target.name
            else:
                print("  → Skipped")
                stats.skipped += 1
                logger.info("Skipped existing file: %s", filename)
                continue

        print(f"[{idx}/{stats.total}] Downloading: {filename}")
        if video.file_size:
            print(f"  Expected size: {format_size(video.file_size)}")

        progress = ProgressTracker(filename, video.file_size)

        try:
            await client.download_media(
                video.message,
                file=str(target),
                progress_callback=progress,
            )
            print()  # newline after progress bar
            # Basic integrity check
            if target.exists() and target.stat().st_size > 0:
                print(f"  ✓ Saved: {target.name}")
                stats.success += 1
                logger.info("Downloaded: %s (msg_id=%s)", target.name, video.message_id)
            else:
                reason = "The output file is empty or missing"
                print(f"  ✗ {reason}")
                stats.failed += 1
                stats.failed_items.append((filename, reason))
                if target.exists():
                    target.unlink(missing_ok=True)

        except FloodWaitError as e:
            wait = e.seconds
            print(f"\n  ⚠ FloodWait: waiting {wait} seconds...")
            logger.warning("FloodWait: waited %s seconds while downloading %s", wait, filename)
            await asyncio.sleep(wait + 1)
            # Retry once
            try:
                await client.download_media(
                    video.message,
                    file=str(target),
                    progress_callback=progress,
                )
                print()
                if target.exists() and target.stat().st_size > 0:
                    print(f"  ✓ Saved after waiting: {target.name}")
                    stats.success += 1
                else:
                    raise RuntimeError("The file is empty after retry")
            except Exception as retry_err:
                reason = f"Failed after FloodWait: {retry_err}"
                print(f"  ✗ {reason}")
                stats.failed += 1
                stats.failed_items.append((filename, reason))
                target.unlink(missing_ok=True)

        except KeyboardInterrupt:
            print("\n  ✗ Download cancelled by user")
            target.unlink(missing_ok=True)
            raise

        except Exception as e:
            reason = str(e)
            print(f"\n  ✗ Download failed: {reason}")
            stats.failed += 1
            stats.failed_items.append((filename, reason))
            logger.exception("Failed to download %s (msg_id=%s)", filename, video.message_id)
            target.unlink(missing_ok=True)

    return stats


def print_summary(stats: DownloadStats, download_dir: Path) -> None:
    print_header("DOWNLOAD SUMMARY")
    print(f"Total selected        : {stats.total}")
    print(f"Downloaded successfully: {stats.success}")
    print(f"Skipped               : {stats.skipped}")
    print(f"Failed                : {stats.failed}")
    print(f"Saved to              : {download_dir.resolve()}")
    print("=" * 60)

    if stats.failed_items:
        print("\nFailed files:")
        for name, reason in stats.failed_items:
            print(f"  • {name}")
            print(f"    Reason: {reason}")