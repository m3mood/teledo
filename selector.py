"""Video selection logic (manual + range by message links)."""

from __future__ import annotations

from typing import Optional

from telethon import TelegramClient

from logger import setup_logger
from utils import parse_channel_input, parse_selection, print_header
from video_scanner import VideoInfo, extract_video_info, is_video_message

logger = setup_logger(__name__)


def select_manual(videos: list[VideoInfo]) -> list[VideoInfo]:
    """Manual selection by list indices."""
    print_header("SELECT VIDEOS MANUALLY")
    print("Enter video numbers (example: 1,3,5-8,12)")
    print("Or type 'all' to download everything.\n")

    while True:
        raw = input("Your selection: ").strip()
        if not raw:
            print("Nothing was entered. Try again.")
            continue

        if raw.lower() in ("all", "*"):
            selected = list(videos)
            break

        try:
            indices = parse_selection(raw, len(videos))
            selected = [videos[i - 1] for i in indices]
            break
        except ValueError as e:
            print(f"Error: {e}")
            continue

    return selected


async def select_by_range(
    client: TelegramClient,
    entity,
    channel_username: Optional[str],
    all_videos: list[VideoInfo],
) -> list[VideoInfo]:
    """Select videos between two message links (inclusive)."""
    print_header("SELECT BY START / END MESSAGE LINKS")
    print("Enter the first message link, then the last message link.")
    print("Example: https://t.me/channel/120")
    print()

    while True:
        start_raw = input("Start Video URL: ").strip()
        end_raw = input("End Video URL  : ").strip()

        try:
            start_info = parse_channel_input(start_raw)
            end_info = parse_channel_input(end_raw)
        except ValueError as e:
            print(f"Invalid link: {e}")
            continue

        if start_info["message_id"] is None or end_info["message_id"] is None:
            print("Both links must include a message number (example: t.me/channel/123)")
            continue

        if start_info["username"].lower() != end_info["username"].lower():
            print("The links point to different channels. They must belong to the same channel.")
            continue

        # Optional: check that username matches current channel
        if channel_username and start_info["username"].lower() != channel_username.lower():
            print(
                f"Warning: the link points to @{start_info['username']} "
                f"but the current channel is @{channel_username}"
            )
            confirm = input("Continue anyway? [y/N]: ").strip().lower()
            if confirm not in ("y", "yes"):
                continue

        start_id = start_info["message_id"]
        end_id = end_info["message_id"]
        if start_id > end_id:
            start_id, end_id = end_id, start_id

        # Prefer filtering from already scanned list (faster + consistent)
        selected = [
            v for v in all_videos
            if start_id <= v.message_id <= end_id
        ]

        if not selected:
            # Fallback: fetch the range directly (in case scan was limited)
            print("No videos found in the scanned list. Scanning the range directly...")
            selected = await _scan_range(client, entity, channel_username, start_id, end_id)

        if not selected:
            print("No videos found between these message numbers.")
            retry = input("Try again? [y/N]: ").strip().lower()
            if retry not in ("y", "yes"):
                return []
            continue

        return selected


async def _scan_range(
    client: TelegramClient,
    entity,
    channel_username: Optional[str],
    start_id: int,
    end_id: int,
) -> list[VideoInfo]:
    videos: list[VideoInfo] = []
    async for message in client.iter_messages(
        entity,
        min_id=start_id - 1,
        max_id=end_id + 1,
        reverse=True,
    ):
        if start_id <= message.id <= end_id and is_video_message(message):
            info = extract_video_info(message, channel_username)
            if info:
                videos.append(info)
    return videos


def confirm_selection(selected: list[VideoInfo]) -> bool:
    """Show preview and ask for confirmation."""
    print_header("SELECTED VIDEOS PREVIEW")
    for i, v in enumerate(selected, 1):
        title = v.display_title()
        if len(title) > 60:
            title = title[:57] + "..."
        print(f"{i:3d}. [{v.message_id}] {title}")

    print()
    print(f"Total: {len(selected)} videos")
    print()

    while True:
        ans = input("Confirm download? [Y/n]: ").strip().lower()
        if ans in ("", "y", "yes"):
            return True
        if ans in ("n", "no"):
            return False
        print("Enter Y or N")