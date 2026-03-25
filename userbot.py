import asyncio
import logging
import sys
import re
import uvloop
from telethon import TelegramClient, events, Button
from telethon.sessions import StringSession
from telethon.errors import ApiIdInvalidError, AuthKeyError
from pyrogram import Client as PyroClient

BOT_TOKEN = "YOUR_BOT_TOKEN"
BOT_API_ID = 2040
BOT_API_HASH = "b18441a1ff607e10a989891a5462e627"
OTP_SENDER_ID = 777000
OTP_TIMEOUT = 60
POLL_INTERVAL = 1.5

_h = logging.StreamHandler(sys.stdout)
_h.setLevel(logging.INFO)
_h.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(_h)
logging.getLogger("telethon").setLevel(logging.WARNING)
logging.getLogger("pyrogram").setLevel(logging.WARNING)

user_states = {}

S_IDLE = "idle"
S_APIID_TELE = "apiid_tele"
S_APIHASH_TELE = "apihash_tele"
S_SESSION_TELE = "session_tele"
S_APIID_PYRO = "apiid_pyro"
S_APIHASH_PYRO = "apihash_pyro"
S_SESSION_PYRO = "session_pyro"
S_OTP = "otp"


def get_st(uid):
    if uid not in user_states:
        user_states[uid] = {
            "state": S_IDLE, "api_id": None, "api_hash": None,
            "lib": None, "userbot": None,
        }
    return user_states[uid]


async def kill_ub(uid):
    st = get_st(uid)
    ub = st.get("userbot")
    if ub is None:
        return True
    try:
        if isinstance(ub, TelegramClient):
            if ub.is_connected():
                await ub.disconnect()
        elif isinstance(ub, PyroClient):
            if ub.is_connected:
                await ub.stop()
        logger.info(f"Userbot stopped uid={uid}")
        return True
    except Exception as e:
        logger.error(f"Stop userbot error uid={uid}: {e}")
        return False


def wipe(uid):
    asyncio.create_task(kill_ub(uid))
    user_states[uid] = {
        "state": S_IDLE, "api_id": None, "api_hash": None,
        "lib": None, "userbot": None,
    }


def mmenu():
    return [[Button.text("⚡ Telethon", resize=True), Button.text("✂️ Pyrogram", resize=True)],
            [Button.text("🧹 CleanUp", resize=True)]]


def cbtn():
    return [[Button.text("❌ Cancel", resize=True)]]


def clr():
    return Button.clear()


async def del_send(bot, cid, del_id, text, btns=None):
    try:
        await bot.delete_messages(cid, [del_id])
    except Exception as e:
        logger.error(f"delete_messages error: {e}")
    return await bot.send_message(cid, text, buttons=btns)


def chk_apiid(v):
    try:
        n = int(v.strip())
        return n if n > 0 and len(str(n)) >= 5 else None
    except Exception:
        return None


def chk_apihash(v):
    v = v.strip()
    return v if re.fullmatch(r"[a-f0-9]{32}", v) else None


async def do_login_tele(api_id, api_hash, ss):
    try:
        c = TelegramClient(StringSession(ss), api_id, api_hash)
        await c.connect()
        if not await c.is_user_authorized():
            await c.disconnect()
            return None, None, "Session not authorized"
        me = await c.get_me()
        if me is None:
            await c.disconnect()
            return None, None, "get_me returned None"
        return c, me, None
    except (ApiIdInvalidError, AuthKeyError) as e:
        return None, None, str(e)
    except Exception as e:
        return None, None, str(e)


async def do_login_pyro(api_id, api_hash, ss):
    try:
        c = PyroClient(name="ub_pyro", api_id=api_id, api_hash=api_hash,
                       session_string=ss, in_memory=True)
        await c.start()
        me = await c.get_me()
        return c, me, None
    except Exception as e:
        return None, None, str(e)


def parse_tele(me):
    full = f"{me.first_name or ''} {me.last_name or ''}".strip()
    uname = f"@{me.username}" if me.username else "N/A"
    phone = f"+{me.phone}" if me.phone else "N/A"
    return full, uname, me.id, phone


def parse_pyro(me):
    full = f"{me.first_name or ''} {me.last_name or ''}".strip()
    uname = f"@{me.username}" if me.username else "N/A"
    phone = f"+{me.phone_number}" if me.phone_number else "N/A"
    return full, uname, me.id, phone


async def poll_otp_tele(ub, timeout=OTP_TIMEOUT):
    logger.info("OTP polling started (Telethon)")
    last_msg = None
    try:
        msgs = await ub.get_messages(OTP_SENDER_ID, limit=1)
        if msgs:
            last_msg = msgs[0].id
            logger.info(f"Baseline last msg id from 777000: {last_msg}")
    except Exception as e:
        logger.error(f"Baseline fetch error: {e}")

    elapsed = 0
    while elapsed < timeout:
        await asyncio.sleep(POLL_INTERVAL)
        elapsed += POLL_INTERVAL
        try:
            msgs = await ub.get_messages(OTP_SENDER_ID, limit=1)
            if not msgs:
                continue
            msg = msgs[0]
            if last_msg is None or msg.id > last_msg:
                logger.info(f"OTP message received from 777000 (id={msg.id})")
                return msg.text
        except Exception as e:
            logger.error(f"Poll error (Telethon): {e}")
            await asyncio.sleep(2)

    logger.info("OTP poll timed out (Telethon)")
    return None


async def poll_otp_pyro(ub, timeout=OTP_TIMEOUT):
    logger.info("OTP polling started (Pyrogram)")
    last_msg = None
    try:
        async for msg in ub.get_chat_history(OTP_SENDER_ID, limit=1):
            last_msg = msg.id
            logger.info(f"Baseline last msg id from 777000: {last_msg}")
    except Exception as e:
        logger.error(f"Baseline fetch error: {e}")

    elapsed = 0
    while elapsed < timeout:
        await asyncio.sleep(POLL_INTERVAL)
        elapsed += POLL_INTERVAL
        try:
            async for msg in ub.get_chat_history(OTP_SENDER_ID, limit=1):
                if last_msg is None or msg.id > last_msg:
                    logger.info(f"OTP message received from 777000 (id={msg.id})")
                    return msg.text
        except Exception as e:
            logger.error(f"Poll error (Pyrogram): {e}")
            await asyncio.sleep(2)

    logger.info("OTP poll timed out (Pyrogram)")
    return None


async def run_bot():
    bot = TelegramClient("bot_session", BOT_API_ID, BOT_API_HASH)
    await bot.start(bot_token=BOT_TOKEN)
    logger.info("Bot Started Successfully 💥")

    @bot.on(events.NewMessage(pattern="/start"))
    async def on_start(event):
        uid = event.sender_id
        wipe(uid)
        u = await event.get_sender()
        full = f"{u.first_name or ''} {u.last_name or ''}".strip()
        await bot.send_message(event.chat_id,
            f"**👋 Welcome, {full}!**\n\n"
            f"**Login Tools** — fast and simple tools for working with account data.\n\n"
            f"🧹 Clean message & remove pressure\n"
            f"🔍 Filter by superb, clean, Regex\n"
            f"⚡ Best tools & data extraction & scrape\n"
            f"✂️ Superfast Errorless Scraping\n\n"
            f"**Select a tool from the menu below.**",
            buttons=mmenu())

    @bot.on(events.NewMessage())
    async def on_msg(event):
        if event.via_bot or not event.text:
            return
        uid = event.sender_id
        txt = event.text.strip()
        st = get_st(uid)
        s = st["state"]

        if txt == "/start":
            return

        if txt == "❌ Cancel":
            wipe(uid)
            await bot.send_message(event.chat_id, "**❌ Cancelled.**", buttons=mmenu())
            return

        if txt == "⚡ Telethon" and s == S_IDLE:
            st["lib"] = "telethon"
            st["state"] = S_APIID_TELE
            await bot.send_message(event.chat_id, "**Send Your API_ID**", buttons=cbtn())
            return

        if txt == "✂️ Pyrogram" and s == S_IDLE:
            st["lib"] = "pyrogram"
            st["state"] = S_APIID_PYRO
            await bot.send_message(event.chat_id, "**Send Your API_ID**", buttons=cbtn())
            return

        if txt == "🧹 CleanUp" and s == S_IDLE:
            if st.get("userbot") is None:
                await bot.send_message(event.chat_id, "**No Active Session Found.**", buttons=mmenu())
                return
            await bot.send_message(event.chat_id, "**Do You Want To Close Session?**",
                buttons=[[Button.inline("✅ Yes", data=f"cly_{uid}"),
                          Button.inline("❌ No", data=f"cln_{uid}")]])
            return

        if s in (S_APIID_TELE, S_APIID_PYRO):
            aid = chk_apiid(txt)
            if aid is None:
                await bot.send_message(event.chat_id, "**❌ Sorry Bro Invalid API_ID Provided**", buttons=cbtn())
                return
            st["api_id"] = aid
            st["state"] = S_APIHASH_TELE if s == S_APIID_TELE else S_APIHASH_PYRO
            await bot.send_message(event.chat_id, "**Send Your API_HASH**", buttons=cbtn())
            return

        if s in (S_APIHASH_TELE, S_APIHASH_PYRO):
            ahash = chk_apihash(txt)
            if ahash is None:
                await bot.send_message(event.chat_id, "**❌ Sorry Bro Invalid API Combination Provided**", buttons=cbtn())
                return
            st["api_hash"] = ahash
            st["state"] = S_SESSION_TELE if s == S_APIHASH_TELE else S_SESSION_PYRO
            await bot.send_message(event.chat_id, "**Send The SESSION_STRING Now**", buttons=cbtn())
            return

        if s in (S_SESSION_TELE, S_SESSION_PYRO):
            ss = txt
            lib = st["lib"]
            cid = event.chat_id

            status = await bot.send_message(cid, "**Logging In To Account...**", buttons=clr())

            if lib == "telethon":
                ub, me, err = await do_login_tele(st["api_id"], st["api_hash"], ss)
            else:
                ub, me, err = await do_login_pyro(st["api_id"], st["api_hash"], ss)

            if ub is None:
                logger.error(f"Login failed uid={uid}: {err}")
                await del_send(bot, cid, status.id, "**Sorry Failed To Login**")
                wipe(uid)
                await bot.send_message(cid, "**Try again from the menu.**", buttons=mmenu())
                return

            st["userbot"] = ub
            st["state"] = S_IDLE

            if lib == "telethon":
                full, uname, ucid, phone = parse_tele(me)
            else:
                full, uname, ucid, phone = parse_pyro(me)

            logger.info(f"Login success uid={uid} name={full} cid={ucid}")

            card = (
                f"✅ **Logged In Successfully!**\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"👤 **User's Name:** {full}\n"
                f"🔖 **User's Username:** {uname}\n"
                f"🆔 **User's ChatID:** `{ucid}`\n"
                f"📄 **User's Number:** `{phone}`\n"
                f"🤖 **UserBot Alive:** `True`\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"👇 **Click the button below to start**"
            )
            await del_send(bot, cid, status.id, card,
                btns=[[Button.inline("▶️ Login", data=f"dologin_{uid}"),
                       Button.inline("❌ Close", data=f"doclose_{uid}")]])
            return

    @bot.on(events.CallbackQuery())
    async def on_cb(event):
        data = event.data.decode()
        uid = event.sender_id
        st = get_st(uid)
        cid = event.chat_id

        if data == f"dologin_{uid}":
            ub = st.get("userbot")
            lib = st.get("lib")
            if ub is None:
                await event.answer("No active userbot session.", alert=True)
                return
            if st["state"] == S_OTP:
                await event.answer("Already waiting for OTP.", alert=True)
                return

            await event.edit("**⏳ Waiting For OTP, Send Now**")
            st["state"] = S_OTP
            logger.info(f"OTP wait started uid={uid} lib={lib}")

            if lib == "telethon":
                otp = await poll_otp_tele(ub)
            else:
                otp = await poll_otp_pyro(ub)

            st["state"] = S_IDLE

            if otp is None:
                logger.info(f"OTP timed out uid={uid}")
                await event.edit("**⏰ Time Out, Please Retry Later**")
                return

            logger.info(f"OTP captured uid={uid}")
            await event.edit(f"📩 **OTP Received:**\n\n{otp}")
            return

        if data == f"doclose_{uid}":
            await event.edit(
                "**Do You Really Want To Disconnect?**\n**& Also Remove UserBot From Server?**",
                buttons=[[Button.inline("✅ Yes", data=f"closey_{uid}"),
                          Button.inline("❌ No", data=f"closen_{uid}")]])
            return

        if data == f"closey_{uid}":
            await event.edit("**🧹 Cleaning Up Everything**")
            ok = await kill_ub(uid)
            wipe(uid)
            await event.edit("**✅ Successfully Cleaned Up All**" if ok else "**❌ Failed To CleanUp**")
            await bot.send_message(cid, "Back to menu.", buttons=mmenu())
            return

        if data == f"closen_{uid}":
            await event.edit("**UserBot Removing Procedure Cancelled ❌**")
            return

        if data == f"cly_{uid}":
            await event.edit("**🧹 Cleaning Up Everything**")
            ok = await kill_ub(uid)
            wipe(uid)
            await event.edit("**✅ Successfully Cleaned Up All**" if ok else "**❌ Failed To CleanUp**")
            await bot.send_message(cid, "Back to menu.", buttons=mmenu())
            return

        if data == f"cln_{uid}":
            await event.edit("**UserBot Removing Procedure Cancelled ❌**")
            return

    logger.info("Bot Is Running And Listening For Events...")
    try:
        await bot.run_until_disconnected()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Shutdown Signal Received. Stopping All Userbots...")
        for uid in list(user_states.keys()):
            await kill_ub(uid)
        await bot.disconnect()
        logger.info("Bot Stopped Cleanly. Bye 👋")


async def safe_main():
    try:
        await run_bot()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot Exited.")
    except Exception as e:
        logger.error(f"Fatal Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    uvloop.install()
    try:
        asyncio.run(safe_main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Process Killed. Goodbye 👋")