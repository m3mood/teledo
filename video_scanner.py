"""Scan Telegram channel for video messages only."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from telethon import TelegramClient
from telethon.tl.types import (
    DocumentAttributeFilename,
    DocumentAttributeVideo,
    Message,
    MessageMediaDocument,
)

from logger import setup_logger
from utils import format_date, format_duration, format_size

logger = setup_logger(__name__)


@dataclass
class VideoInfo:
    message_id: int
    caption: str
    date: datetime
    file_name: Optional[str]
    file_size: Optional[int]
    duration: Optional[int]
    message: Message  # keep reference for download
    link: Optional[str] = None

    def display_title(self) -> str:
        return self.caption if self.caption else "[Untitled]"


def is_video_message(message: Message) -> bool:
    """Return True only if the message contains a real video."""
    if not message or not message.media:
        return False

    if not isinstance(message.media, MessageMediaDocument):
        return False

    doc = message.media.document
    if not doc:
        return False

    # Check mime type
    mime = (doc.mime_type or "").lower()
    if mime.startswith("video/"):
        return True

    # Check for video attribute (covers some edge cases)
    for attr in doc.attributes or []:
        if isinstance(attr, DocumentAttributeVideo):
            return True

    return False


def extract_video_info(message: Message, channel_username: Optional[str] = None) -> Optional[VideoInfo]:
    if not is_video_message(message):
        return None

    doc = message.media.document
    caption = (message.message or "").strip() or "[Untitled]"

    file_name = None
    duration = None
    file_size = getattr(doc, "size", None)

    for attr in doc.attributes or []:
        if isinstance(attr, DocumentAttributeFilename):
            file_name = attr.file_name
        elif isinstance(attr, DocumentAttributeVideo):
            duration = getattr(attr, "duration", None)

    link = None
    if channel_username:
        link = f"https://t.me/{channel_username}/{message.id}"

    return VideoInfo(
        message_id=message.id,
        caption=caption,
        date=message.date,
        file_name=file_name,
        file_size=file_size,
        duration=duration,
        message=message,
        link=link,
    )


async def scan_channel_videos(
    client: TelegramClient,
    entity,
    channel_username: Optional[str] = None,
    limit: Optional[int] = None,
) -> list[VideoInfo]:
    """
    Iterate messages and collect only videos.
    Order: oldest → newest (natural channel order).
    """
    videos: list[VideoInfo] = []
    total_checked = 0

    print("\nScanning channel messages and extracting videos...")
    print("(This may take some time if the channel is large)\n")

    # reverse=True → oldest first
    async for message in client.iter_messages(entity, limit=limit, reverse=True):
        total_checked += 1
        if total_checked % 200 == 0:
            print(f"  Scanned {total_checked} messages... (videos so far: {len(videos)})")

        info = extract_video_info(message, channel_username)
        if info:
            videos.append(info)

    logger.info(
        "Scan complete. Messages checked=%s, videos=%s",
        total_checked,
        len(videos),
    )
    print(f"\n✓ Scanned {total_checked} messages.")
    print(f"✓ Found {len(videos)} videos.")
    return videos


def print_video_list(videos: list[VideoInfo], page_size: int = 15) -> None:
    """Print videos with simple pagination."""
    if not videos:
        print("No videos found in this channel.")
        return

    total = len(videos)
    page = 0

    while True:
        start = page * page_size
        end = min(start + page_size, total)
        page_videos = videos[start:end]

        print("\n" + "=" * 60)
        print(f"VIDEO LIST  (showing {start + 1}-{end} of {total})")
        print("=" * 60)

        for idx, v in enumerate(page_videos, start=start + 1):
            title = v.display_title()
            if len(title) > 55:
                title = title[:52] + "..."
            print(f"[{idx}] {title}")
            print(f"    Message ID : {v.message_id}")
            print(f"    Date       : {format_date(v.date)}")
            print(f"    Duration   : {format_duration(v.duration)}")
            print(f"    Size       : {format_size(v.file_size)}")
            if v.file_name:
                print(f"    File Name  : {v.file_name}")
            print()

        print("=" * 60)

        if end >= total:
            break

        choice = input(
            f"Show the next page? [Enter = yes / n = no / all = show all]: "
        ).strip().lower()
        if choice in ("n", "no"):
            break
        if choice in ("all", "a"):
            # print remaining
            for idx, v in enumerate(videos[end:], start=end + 1):
                title = v.display_title()
                if len(title) > 55:
                    title = title[:52] + "..."
                print(f"[{idx}] {title}")
                print(f"    Message ID : {v.message_id}")
                print(f"    Date       : {format_date(v.date)}")
                print(f"    Duration   : {format_duration(v.duration)}")
                print(f"    Size       : {format_size(v.file_size)}")
                print()
            break
        page += 1