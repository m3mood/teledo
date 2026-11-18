#!/usr/bin/env python3
"""
Telegram Video Downloader
CLI tool to scan a channel and download selected videos using Telethon.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from config import ConfigError, load_config
from downloader import download_videos, print_summary
from logger import setup_logger
from selector import confirm_selection, select_by_range, select_manual
from telegram_client import TelegramClientManager
from utils import parse_channel_input, print_header
from video_scanner import print_video_list, scan_channel_videos

logger = setup_logger("main")


def ask_download_folder() -> Path:
    print_header("DOWNLOAD FOLDER")
    while True:
        raw = input("Enter the download folder path: ").strip().strip('"').strip("'")
        if not raw:
            print("The path is required.")
            continue

        path = Path(raw).expanduser()

        if path.exists() and not path.is_dir():
            print("The path exists but is not a directory.")
            continue

        if not path.exists():
            create = input(f"The folder does not exist. Create it? [Y/n]: ").strip().lower()
            if create in ("", "y", "yes"):
                try:
                    path.mkdir(parents=True, exist_ok=True)
                except OSError as e:
                    print(f"Failed to create the folder: {e}")
                    continue
            else:
                continue

        # Check write permission
        test_file = path / ".write_test_telegram_dl"
        try:
            test_file.write_text("ok", encoding="utf-8")
            test_file.unlink()
        except OSError as e:
            print(f"Cannot write to this folder: {e}")
            continue

        return path


async def run() -> None:
    print_header("TELEGRAM VIDEO DOWNLOADER")

    # 1. Config
    try:
        cfg = load_config()
    except ConfigError as e:
        print(f"\nConfiguration error:\n{e}")
        sys.exit(1)

    manager = TelegramClientManager(
        api_id=cfg["api_id"],
        api_hash=cfg["api_hash"],
        session_name=cfg["session_name"],
    )

    client = None
    try:
        # 2. Connect / Login
        client = await manager.connect()

        # 3. Channel
        print_header("ENTER CHANNEL")
        while True:
            channel_raw = input(
                "Enter the channel link, @username, or message link:\n> "
            ).strip()
            if not channel_raw:
                continue
            try:
                parsed = parse_channel_input(channel_raw)
                break
            except ValueError as e:
                print(f"Error: {e}")

        username = parsed["username"]
        entity = await manager.get_entity(username)

        # Display channel info
        title = getattr(entity, "title", None) or getattr(entity, "first_name", "Unknown")
        uname = getattr(entity, "username", None)
        print(f"\n✓ Channel: {title}")
        if uname:
            print(f"  Username: @{uname}")
        else:
            print("  Username: (private / no username)")

        channel_username = uname or username

        # 4. Scan
        videos = await scan_channel_videos(client, entity, channel_username)

        if not videos:
            print("\nNo downloadable videos were found in this channel.")
            return

        print_video_list(videos)

        # 5. Selection method
        print_header("SELECT DOWNLOAD METHOD")
        print("1. Select videos manually")
        print("2. Select videos by start/end Telegram message links")
        print()

        while True:
            method = input("Choose a method [1/2]: ").strip()
            if method == "1":
                selected = select_manual(videos)
                break
            if method == "2":
                selected = await select_by_range(
                    client, entity, channel_username, videos
                )
                break
            print("Enter 1 or 2 only.")

        if not selected:
            print("No videos selected. Exiting.")
            return

        # 6. Confirm
        if not confirm_selection(selected):
            print("Cancelled by user.")
            return

        # 7. Folder
        download_dir = ask_download_folder()

        # 8. Download
        stats = await download_videos(client, selected, download_dir)

        # 9. Summary
        print_summary(stats, download_dir)

    except KeyboardInterrupt:
        print("\n\nDownload cancelled by user.")
        logger.info("Cancelled by user (Ctrl+C)")
    except Exception as e:
        logger.exception("Unexpected error")
        print(f"\nAn error occurred: {e}")
        sys.exit(1)
    finally:
        if manager:
            await manager.disconnect()


def main() -> None:
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        print("\nDownload cancelled by user.")


if __name__ == "__main__":
    main()