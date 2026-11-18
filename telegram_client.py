"""Telegram client management using Telethon."""

from __future__ import annotations

from typing import Optional

from telethon import TelegramClient
from telethon.errors import (
    ApiIdInvalidError,
    FloodWaitError,
    PhoneCodeInvalidError,
    PhoneNumberInvalidError,
    SessionPasswordNeededError,
)
from logger import setup_logger

logger = setup_logger(__name__)


class TelegramClientManager:
    def __init__(self, api_id: int, api_hash: str, session_name: str = "teledo"):
        self.api_id = api_id
        self.api_hash = api_hash
        self.session_name = session_name
        self.client: Optional[TelegramClient] = None

    def _require_client(self) -> TelegramClient:
        if self.client is None:
            raise RuntimeError("The Telegram client is not connected. Call connect() first.")
        return self.client

    async def connect(self) -> TelegramClient:
        """Connect and ensure the user is authorized."""
        client = TelegramClient(
            self.session_name,
            self.api_id,
            self.api_hash,
            flood_sleep_threshold=60,  # auto-sleep short flood waits
        )
        self.client = client

        try:
            await client.connect()
        except ApiIdInvalidError:
            raise RuntimeError("API_ID or API_HASH is invalid. Check the .env file.")
        except Exception as e:
            logger.exception("Failed to connect to Telegram")
            raise RuntimeError(f"Failed to connect to Telegram: {e}") from e

        if not await client.is_user_authorized():
            await self._login()

        me = await client.get_me()
        logger.info("Successfully logged in: %s (id=%s)", me.username or me.first_name, me.id)
        print(f"\n✓ Connected account: {me.first_name or ''} (@{me.username or 'no username'})")
        return client

    async def _login(self) -> None:
        """Interactive login flow."""
        client = self._require_client()
        print("\n=== Telegram Login ===")
        phone = input("Enter your phone number (with country code, example +9665xxxxxxx): ").strip()
        if not phone:
            raise RuntimeError("The phone number is required")

        try:
            await client.send_code_request(phone)
        except PhoneNumberInvalidError:
            raise RuntimeError("The phone number is invalid")
        except FloodWaitError as e:
            raise RuntimeError(f"Wait {e.seconds} seconds before trying again (FloodWait)")
        except Exception as e:
            logger.exception("Failed to send the verification code")
            raise RuntimeError(f"Failed to send the verification code: {e}") from e

        code = input("Enter the verification code sent to you on Telegram: ").strip()
        if not code:
            raise RuntimeError("The verification code is required")

        try:
            await client.sign_in(phone, code)
        except PhoneCodeInvalidError:
            raise RuntimeError("The verification code is invalid")
        except SessionPasswordNeededError:
            password = input("The account is protected by 2FA. Enter the password: ").strip()
            if not password:
                raise RuntimeError("The 2FA password is required")
            try:
                await client.sign_in(password=password)
            except Exception as e:
                logger.exception("Failed to log in with 2FA")
                raise RuntimeError(f"Failed to log in with 2FA: {e}") from e
        except Exception as e:
            logger.exception("Failed to log in")
            raise RuntimeError(f"Failed to log in: {e}") from e

    async def get_entity(self, username_or_id: str):
        """Resolve channel/entity and return it."""
        client = self._require_client()
        try:
            entity = await client.get_entity(username_or_id)
            return entity
        except ValueError as e:
            raise RuntimeError(f"Cannot access channel '{username_or_id}'. Check the link and permissions.") from e
        except Exception as e:
            logger.exception("Error while fetching the channel")
            raise RuntimeError(f"Error while fetching the channel: {e}") from e

    async def disconnect(self) -> None:
        if self.client and self.client.is_connected():
            await self.client.disconnect()
            logger.info("Disconnected from Telegram")
        self.client = None