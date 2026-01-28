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
async def start_index(client: Client, message: Message):
    if lock.locked():
        return await message.reply("⏳ An indexing process is already running.")

    ask = await message.reply(
        "📌 **Forward the last message of the database channel**\n"
        "or send the **channel message link**."
    )

    try:
        msg = await client.listen(message.chat.id, timeout=120)
    except:
        return await ask.edit("❌ Timeout.")

    await ask.delete()

    # Resolve channel + last message ID
    try:
        if msg.text and msg.text.startswith("https://t.me/"):
            parts = msg.text.split("/")
            last_msg_id = int(parts[-1])
            chat_id = parts[-2]
            if chat_id.isnumeric():
                chat_id = int("-100" + chat_id)
        elif msg.forward_origin.chat.sender_chat:
            chat_id = msg.forward_from_chat.id
            last_msg_id = msg.forward_origin.message_id
        else:
            return await message.reply("❌ Invalid input.")
    except Exception:
        return await message.reply("❌ Failed to parse message.")

    if chat_id != DATABASE_CHANNEL_ID:
        return await message.reply("❌ This is not the configured DATABASE_CHANNEL_ID.")

    ask_skip = await message.reply("🔢 Send **skip message count** (0 for full index).")
    try:
        skip_msg = await client.listen(message.chat.id, timeout=60)
        skip = int(skip_msg.text)
    except:
        return await ask_skip.edit("❌ Invalid skip value.")

    await ask_skip.delete()

    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ START", callback_data=f"index#start#{last_msg_id}#{skip}")],
        [InlineKeyboardButton("❌ CANCEL", callback_data="index#abort")]
    ])

    await message.reply(
        f"⚠️ **Confirm indexing**\n\n"
        f"Channel: `{DATABASE_CHANNEL_ID}`\n"
        f"Last Msg ID: `{last_msg_id}`\n"
        f"Skip: `{skip}`",
        reply_markup=buttons
    )


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
                reverse=True
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





