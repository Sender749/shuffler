from pyrogram import Client, filters, enums
from vars import *
from Database.maindb import mdb
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
from pyrogram.types import *
import asyncio
import time
from pyrogram.errors import FloodWait, MessageNotModified


lock = asyncio.Lock()
CANCEL_INDEX = False
INDEX_STATE = {}

@Client.on_message(filters.chat(DATABASE_CHANNEL_ID) & filters.video)
async def save_video(client: Client, message: Message):
    try:
        video_id = message.id
        video_duration = message.video.duration
        is_premium = video_duration > FREE_VIDEO_DURATION
        await mdb.save_video_id(video_id, video_duration, is_premium)
        text = f"**✅ Saved | ID: {video_id} | ⏱️ {video_duration}s | 💎 {is_premium}**"
        await client.send_message(chat_id=DATABASE_CHANNEL_LOG, text=text)
    except Exception as t:
        print(f"Error: {str(t)}")

@Client.on_message(filters.command("index") & filters.private & filters.user(ADMIN_ID))
async def start_index(client, message):
    if lock.locked():
        return await message.reply("⏳ An indexing process is already running.")
    INDEX_STATE[message.from_user.id] = {"step": "await_channel"}
    await message.reply(
        "📌 Forward last database channel message or send channel message link."
    )

@Client.on_message(filters.private & filters.user(ADMIN_ID))
async def index_flow(client, message):
    state = INDEX_STATE.get(message.from_user.id)
    if not state:
        return

    # ---- STEP 1: channel input ----
    if state["step"] == "await_channel":
        chat_id, last_msg_id = parse_channel_message(message)
        if not chat_id or str(chat_id) != str(DATABASE_CHANNEL_ID):
            return await message.reply("❌ Invalid database channel.")

        state.update({
            "step": "await_skip",
            "last_msg_id": last_msg_id
        })
        return await message.reply("🔢 Send skip count (0 for full index).")

    # ---- STEP 2: skip ----
    if state["step"] == "await_skip":
        try:
            skip = int(message.text)
        except:
            return await message.reply("❌ Skip must be a number.")

        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ START", callback_data=f"index#start#{state['last_msg_id']}#{skip}")],
            [InlineKeyboardButton("❌ CANCEL", callback_data="index#abort")]
        ])

        state["step"] = "confirm"
        await message.reply("⚠️ Confirm indexing", reply_markup=buttons)



# -------------------------------
# Callback handler
# -------------------------------
@Client.on_callback_query(filters.regex("^index#") & filters.user(ADMIN_ID))
async def index_callback(client, query):
    global CANCEL_INDEX

    data = query.data.split("#")

    if data[1] == "abort":
        CANCEL_INDEX = True
        return await query.message.edit("🛑 Cancel requested…")

    if data[1] == "start":
        last_msg_id = int(data[2])
        skip = int(data[3])
        await query.message.edit("🚀 **Indexing started…**")
        await index_channel(client, query.message, last_msg_id, skip)


# -------------------------------
# Core indexing logic
# -------------------------------
async def index_channel(client, status_msg, last_msg_id, skip):
    global CANCEL_INDEX

    saved = dup = skipped = errors = 0
    start_time = time.time()

    async with lock:
        try:
            async for msg in client.iter_messages(
                DATABASE_CHANNEL_ID,
                offset_id=last_msg_id,
                reverse=False
            ):
                if skip > 0:
                    skip -= 1
                    continue

                if CANCEL_INDEX:
                    CANCEL_INDEX = False
                    break

                if not msg.video:
                    skipped += 1
                    continue

                try:
                    video_id = msg.id
                    duration = msg.video.duration
                    is_premium = duration > FREE_VIDEO_DURATION

                    await mdb.save_video_id(video_id, duration, is_premium)
                    saved += 1
                except Exception:
                    errors += 1

                if (saved + skipped) % 100 == 0:
                    try:
                        await status_msg.edit_text(
                            f"📊 **Indexing…**\n\n"
                            f"Saved: `{saved}`\n"
                            f"Skipped: `{skipped}`\n"
                            f"Errors: `{errors}`"
                        )
                    except MessageNotModified:
                        pass

        except FloodWait as e:
            await asyncio.sleep(e.value)

    elapsed = round(time.time() - start_time, 2)

    await status_msg.edit_text(
        f"✅ **Indexing completed**\n\n"
        f"Saved: `{saved}`\n"
        f"Skipped: `{skipped}`\n"
        f"Errors: `{errors}`\n"
        f"⏱ Time: `{elapsed}s`"
    )








