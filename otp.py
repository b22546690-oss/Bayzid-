import asyncio
import logging
import sys
from datetime import datetime

import uvloop
from pyrogram import Client, filters
from pyrogram.handlers import MessageHandler

API_ID = YOUR_API_ID
API_HASH = "YOUR_API_HASH"
SESSION_STRING = "YOUR_SESSION_STRING"
TELEGRAM_OTP_SENDER = 777000
OTP_TIMEOUT = 15

handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
handler.setFormatter(formatter)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(handler)
logging.getLogger("pyrogram").setLevel(logging.WARNING)

otp_event = asyncio.Event()
otp_message_text = None


async def otp_listener(client, message):
    global otp_message_text
    otp_message_text = message.text
    otp_event.set()


async def main():
    global otp_message_text

    logger.info("Creating User Client From SESSION_STRING")

    try:
        app = Client(
            name="userbot_session",
            api_id=API_ID,
            api_hash=API_HASH,
            session_string=SESSION_STRING,
            in_memory=True,
        )
        logger.info("User Client Created Successfully !")
    except Exception as e:
        logger.error(f"Failed To Create Client: {e}")
        sys.exit(1)

    try:
        await app.start()
        logger.info("User Successfully Started 💥")
    except Exception as e:
        logger.error(f"Failed To Start Client: {e}")
        sys.exit(1)

    try:
        me = await app.get_me()
        full_name = f"{me.first_name or ''} {me.last_name or ''}".strip()
        phone = me.phone_number or "N/A"
        username = f"@{me.username}" if me.username else "N/A"

        logger.info(f'User\'s Full Name "{full_name}"')
        logger.info(f'User\'s Number "{phone}"')
        logger.info(f'User\'s Username "{username}"')
    except Exception as e:
        logger.error(f"Failed To Fetch User Info: {e}")
        await app.stop()
        sys.exit(1)

    try:
        answer = input("\nDo you want To login To your Account? (yes/no): ").strip().lower()
    except (KeyboardInterrupt, EOFError):
        logger.info("Input Cancelled. Stopping Client.")
        await app.stop()
        sys.exit(0)

    if answer != "yes":
        logger.info("Login Skipped. Stopping Client.")
        await app.stop()
        sys.exit(0)

    logger.info(f"Waiting For OTP Message From Telegram (Timeout: {OTP_TIMEOUT}s)...")

    otp_filter = filters.chat(TELEGRAM_OTP_SENDER) & filters.text
    app.add_handler(MessageHandler(otp_listener, otp_filter))

    try:
        await asyncio.wait_for(otp_event.wait(), timeout=OTP_TIMEOUT)

        if otp_message_text:
            border = "─" * 50
            print(f"\n{border}")
            print(f"  📩 OTP MESSAGE RECEIVED")
            print(f"{border}")
            for line in otp_message_text.strip().split("\n"):
                print(f"  {line}")
            print(f"{border}\n")
            logger.info("OTP Message Captured Successfully.")
        else:
            logger.warning("OTP Event Triggered But Message Was Empty.")

    except asyncio.TimeoutError:
        logger.error(f"Timeout! No OTP Message Received Within {OTP_TIMEOUT} Seconds.")
    except Exception as e:
        logger.error(f"Unexpected Error While Waiting For OTP: {e}")
    finally:
        await app.stop()
        logger.info("Client Stopped Cleanly.")


if __name__ == "__main__":
    uvloop.install()
    asyncio.run(main())