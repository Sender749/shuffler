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
    INDEX_STATE[message.from_user.id] = {"step": "await_last_msg"}
    await message.reply(
        "📌 **Forward the last message** from the database channel."
    )

def parse_channel_message(message: Message):
    """Parse forwarded message or message link to extract chat_id and message_id"""
    chat_id = None
    msg_id = None

    # Case 1: Forwarded message
    if message.forward_origin:
        if hasattr(message.forward_origin, 'chat') and message.forward_origin.chat:
            chat_id = message.forward_origin.chat.id
            msg_id = message.forward_origin.message_id
        elif hasattr(message.forward_origin, 'channel_post'):
            # Handle forward from channel
            if message.forward_origin.chat:
                chat_id = message.forward_origin.chat.id
                msg_id = message.forward_origin.message_id

    # Case 2: Message link
    elif message.text and "t.me/" in message.text:
        text = message.text.strip()
        try:
            parts = text.split("/")
            msg_id = int(parts[-1])

            if parts[-2] == "c":  # private channel link
                chat_id = int("-100" + parts[-3])
            else:  # public channel username
                chat_id = parts[-2]
        except Exception as e:
            print(f"Error parsing link: {e}")
            pass

    return chat_id, msg_id

def parse_start_message(message: Message):
    """Parse message ID or link for start indexing point"""
    msg_id = None
    
    # Case 1: Just a number (message ID)
    if message.text and message.text.strip().isdigit():
        msg_id = int(message.text.strip())
    
    # Case 2: Message link
    elif message.text and "t.me/" in message.text:
        try:
            parts = message.text.strip().split("/")
            msg_id = int(parts[-1])
        except:
            pass
    
    # Case 3: Forwarded message
    elif message.forward_origin:
        if hasattr(message.forward_origin, 'message_id'):
            msg_id = message.forward_origin.message_id
    
    return msg_id

@Client.on_message(filters.private & filters.user(ADMIN_ID) & ~filters.command(["index", "stats", "broadcast", "ban", "unban", "maintenance", "banlist", "delete", "deleteall"]))
async def index_flow(client, message):
    """Handle multi-step index flow"""
    state = INDEX_STATE.get(message.from_user.id)
    if not state:
        return

    # ---- STEP 1: Get last message ----
    if state["step"] == "await_last_msg":
        chat_id, last_msg_id = parse_channel_message(message)
        
        if not chat_id or not last_msg_id:
            return await message.reply("❌ Invalid message. Please forward the last message from the database channel.")
        
        if str(chat_id) != str(DATABASE_CHANNEL_ID):
            return await message.reply(f"❌ This message is not from the database channel.\n\nExpected: `{DATABASE_CHANNEL_ID}`\nReceived: `{chat_id}`")

        state.update({
            "step": "await_skip",
            "last_msg_id": last_msg_id
        })
        return await message.reply(
            "🔢 **Send skip numbers (number of messages to skip)**\n\n"
            "Examples:\n• Send `0` to index all messages\n• Send `10` to skip first 10 messages"
        )

    # ---- STEP 2: Get skip count ----
    elif state["step"] == "await_skip":
        try:
            skip = int(message.text.strip())
            if skip < 0:
                return await message.reply("❌ Skip count must be 0 or greater.")
        except:
            return await message.reply("❌ Please send a valid number for skip count.")
        
        state.update({
            "step": "await_start_msg",
            "skip": skip
        })
        return await message.reply(
            "📍 **Send the message ID or link where indexing should start**\n\n"
            "You can:\n• Forward a message from the channel\n• Send message ID (e.g., `12345`)\n• Send message link"
        )

    # ---- STEP 3: Get start message ----
    elif state["step"] == "await_start_msg":
        start_msg_id = parse_start_message(message)
        
        if not start_msg_id:
            return await message.reply("❌ Invalid message ID or link. Please try again.")
        
        last_msg_id = state["last_msg_id"]
        skip = state["skip"]
        
        # Clear state
        INDEX_STATE.pop(message.from_user.id, None)
        
        # Start indexing
        status = await message.reply(
            f"🚀 **Indexing started...**\n\n"
            f"Last Message ID: `{last_msg_id}`\n"
            f"Start Message ID: `{start_msg_id}`\n"
            f"Skip Count: `{skip}`"
        )
        
        await index_channel(client, status, last_msg_id, start_msg_id, skip)

async def index_channel(client, status_msg, last_msg_id, start_msg_id, skip):
    """Index videos from database channel"""
    global CANCEL_INDEX
    saved = skipped = errors = 0
    start_time = time.time()

    async with lock:
        try:
            # Iterate from start_msg_id to last_msg_id
            async for msg in client.iter_messages(
                DATABASE_CHANNEL_ID,
                offset_id=last_msg_id + 1,
                reverse=True  # Changed to True to go from old to new
            ):
                # Skip until we reach start message
                if msg.id < start_msg_id:
                    continue
                
                # Apply skip count
                if skip > 0:
                    skip -= 1
                    skipped += 1
                    continue

                if CANCEL_INDEX:
                    CANCEL_INDEX = False
                    break

                # Only process video messages
                if not msg.video:
                    skipped += 1
                    continue

                try:
                    video_id = msg.id
                    duration = msg.video.duration
                    is_premium = duration > FREE_VIDEO_DURATION

                    await mdb.save_video_id(video_id, duration, is_premium)
                    saved += 1
                except Exception as e:
                    print(f"Error saving video {msg.id}: {e}")
                    errors += 1

                # Update status every 100 messages
                if (saved + skipped) % 100 == 0:
                    try:
                        await status_msg.edit_text(
                            f"📊 **Indexing in progress...**\n\n"
                            f"✅ Saved: `{saved}`\n"
                            f"⏭️ Skipped: `{skipped}`\n"
                            f"❌ Errors: `{errors}`"
                        )
                    except MessageNotModified:
                        pass

        except FloodWait as e:
            await asyncio.sleep(e.value)
        except Exception as e:
            print(f"Indexing error: {e}")
            await status_msg.edit_text(f"❌ **Indexing failed:** `{str(e)}`")
            return

    elapsed = round(time.time() - start_time, 2)

    await status_msg.edit_text(
        f"✅ **Indexing completed successfully!**\n\n"
        f"📊 **Statistics:**\n"
        f"✅ Saved: `{saved}`\n"
        f"⏭️ Skipped: `{skipped}`\n"
        f"❌ Errors: `{errors}`\n\n"
        f"⏱️ **Time taken:** `{elapsed}s`"
    )
