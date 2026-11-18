# Teledo

**Teledo** is a Python CLI application for downloading and organizing videos from Telegram channels using Telethon.

## Features

- Connect to Telegram with an existing account
- Browse Telegram channels and select videos
- Download video files with configurable quality and paths
- Interactive CLI with progress and logging
- Keeps credentials and Telegram session files out of source control

## Requirements
- Python 3.11+
- A Telegram account
- API_ID and API_HASH from https://my.telegram.org

## Quick Installation (Windows PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
# Edit .env and add API_ID and API_HASH
python main.py