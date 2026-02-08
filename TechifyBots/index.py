from pyrogram import Client, filters
from vars import *
from Database.maindb import mdb
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery
import asyncio
import time
from pyrogram.errors import FloodWait, MessageNotModified

lock = asyncio.Lock()
CANCEL_INDEX = {}
INDEX_STATE = {}
INDEX_TIMEOUT = 900  # 15 minutes in seconds

@Client.on_message(filters.chat([ch for ch in DATABASE_CHANNEL_IDS]) & (filters.video | filters.photo | filters.document | filters.animation))
async def save_video(client: Client, message: Message):
    """Auto-save media when posted in database channels"""
    try:
        video_id = message.id
        
        # Determine duration based on media type
        if message.video:
            video_duration = message.video.duration
        elif message.animation:
            video_duration = message.animation.duration if message.animation.duration else 0
        elif message.document:
            # For documents, check if it's a video file
            if message.document.mime_type and 'video' in message.document.mime_type:
                video_duration = message.document.duration if message.document.duration else 0
            else:
                video_duration = 0  # Not a video document
        else:
            # Photos and other media
            video_duration = 0
        
        is_premium = video_duration > FREE_VIDEO_DURATION
        await mdb.save_video_id(video_id, video_duration, is_premium)
        
        media_type = "video" if message.video else "photo" if message.photo else "document" if message.document else "animation"
        text = f"**✅ Saved | ID: {video_id} | Type: {media_type} | ⏱️ {video_duration}s | 💎 {is_premium}**"
        await client.send_message(chat_id=DATABASE_CHANNEL_LOG, text=text)
    except Exception as t:
        print(f"Error auto-saving media: {str(t)}")

@Client.on_message(filters.command("index") & filters.private & filters.user(ADMIN_ID))
async def start_index(client: Client, message: Message):
    """Start the indexing process"""
    print(f"[INDEX] Command received from user {message.from_user.id}")
    
    if lock.locked():
        print(f"[INDEX] Lock is already held, rejecting request")
        return await message.reply("⏳ An indexing process is already running.")
    
    user_id = message.from_user.id
    CANCEL_INDEX[user_id] = False
    
    # Get channel names
    channel_buttons = []
    for channel_id in DATABASE_CHANNEL_IDS:
        try:
            chat = await client.get_chat(channel_id)
            channel_name = chat.title or f"Channel {channel_id}"
            print(f"[INDEX] Found channel: {channel_name} ({channel_id})")
            channel_buttons.append([
                InlineKeyboardButton(
                    text=f"📁 {channel_name}",
                    callback_data=f"idx_ch_{channel_id}"
                )
            ])
        except Exception as e:
            print(f"[INDEX] Error getting channel {channel_id}: {e}")
            channel_buttons.append([
                InlineKeyboardButton(
                    text=f"📁 Channel {channel_id}",
                    callback_data=f"idx_ch_{channel_id}"
                )
            ])
    
    # Store state
    INDEX_STATE[user_id] = {
        "step": "select_channel",
        "timeout_task": asyncio.create_task(handle_timeout(client, user_id))
    }
    
    print(f"[INDEX] State saved for user {user_id}: {INDEX_STATE[user_id]}")
    print(f"[INDEX] Showing {len(channel_buttons)} channel(s) to select")
    
    await message.reply(
        "📋 **Select Database Channel**\n\nChoose the channel you want to index:",
        reply_markup=InlineKeyboardMarkup(channel_buttons)
    )

async def handle_timeout(client: Client, user_id: int):
    """Handle 15-minute timeout"""
    await asyncio.sleep(INDEX_TIMEOUT)
    state = INDEX_STATE.get(user_id)
    if state:
        INDEX_STATE.pop(user_id, None)
        CANCEL_INDEX.pop(user_id, None)
        try:
            if "status_msg" in state:
                await state["status_msg"].edit_text(
                    "⏱️ **Indexing Timeout**\n\nNo response received within 15 minutes. Process cancelled."
                )
        except:
            pass

# IMPORTANT: Use specific filter with higher priority
@Client.on_callback_query(filters.regex(r"^idx_ch_-?\d+$"))
async def handle_channel_selection(client: Client, callback: CallbackQuery):
    """Handle channel selection"""
    user_id = callback.from_user.id
    state = INDEX_STATE.get(user_id)
    
    print(f"[INDEX-CALLBACK] Channel selection callback triggered")
    print(f"[INDEX-CALLBACK] Callback data: {callback.data}")
    print(f"[INDEX-CALLBACK] User {user_id} state: {state}")
    print(f"[INDEX-CALLBACK] Current INDEX_STATE keys: {list(INDEX_STATE.keys())}")
    
    if not state or state.get("step") != "select_channel":
        print(f"[INDEX-CALLBACK] ERROR: Invalid state - state={state}, expected step=select_channel")
        return await callback.answer("⚠️ Session expired. Please start again with /index", show_alert=True)
    
    # Extract channel ID (handle negative IDs properly)
    try:
        # Remove 'idx_ch_' prefix
        channel_id_str = callback.data.replace("idx_ch_", "")
        channel_id = int(channel_id_str)
        print(f"[INDEX-CALLBACK] Extracted channel ID: {channel_id}")
    except Exception as e:
        print(f"[INDEX-CALLBACK] ERROR parsing channel ID: {e}")
        return await callback.answer("⚠️ Invalid channel ID", show_alert=True)
    
    # Update state
    state.update({
        "step": "await_msg_link",
        "channel_id": channel_id,
        "status_msg": callback.message
    })
    
    print(f"[INDEX-CALLBACK] Updated state: {state}")
    
    # Cancel old timeout and create new one
    if "timeout_task" in state:
        state["timeout_task"].cancel()
    state["timeout_task"] = asyncio.create_task(handle_timeout(client, user_id))
    
    print(f"[INDEX-CALLBACK] Showing message ID input prompt")
    
    await callback.message.edit_text(
        "📍 **Send Last Message ID or Link**\n\n"
        "You can send:\n"
        "• Message ID (e.g., `12345`)\n"
        "• Message link from the channel\n"
        "• `0` to index all messages from the beginning\n\n"
        "⏱️ You have 15 minutes to respond.",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("❌ Cancel", callback_data="idx_cancel")
        ]])
    )
    await callback.answer()

@Client.on_callback_query(filters.regex(r"^idx_cancel$"))
async def handle_cancel(client: Client, callback: CallbackQuery):
    """Handle cancel button"""
    user_id = callback.from_user.id
    state = INDEX_STATE.get(user_id)
    
    print(f"Cancel callback triggered for user {user_id}")
    
    if state:
        # Cancel timeout task
        if "timeout_task" in state:
            state["timeout_task"].cancel()
        
        # Set cancel flag
        CANCEL_INDEX[user_id] = True
        
        # Clear state
        INDEX_STATE.pop(user_id, None)
        
        await callback.message.edit_text("❌ **Indexing Cancelled**\n\nThe indexing process has been stopped.")
    
    await callback.answer("Cancelled")

def extract_message_id_from_link(text: str):
    """Extract message ID from Telegram link or plain number"""
    if not text:
        return None
        
    text = text.strip()
    
    # Check if it's just a number
    if text.isdigit():
        return int(text)
    
    # Check if it's 0 (index all)
    if text == "0":
        return 0
    
    # Extract from link
    if "t.me/" in text:
        try:
            # Handle different link formats
            # https://t.me/c/1234567890/123
            # https://t.me/username/123
            parts = text.split("/")
            return int(parts[-1])
        except:
            pass
    
    return None

@Client.on_message(filters.private & filters.user(ADMIN_ID) & ~filters.command(["index", "stats", "broadcast", "ban", "unban", "maintenance", "banlist", "delete", "deleteall"]))
async def handle_index_input(client: Client, message: Message):
    """Handle user input during indexing flow"""
    user_id = message.from_user.id
    state = INDEX_STATE.get(user_id)
    
    if not state:
        return
    
    print(f"[INDEX-INPUT] User input received: {message.text}")
    print(f"[INDEX-INPUT] Current state: {state}")
    print(f"[INDEX-INPUT] Current step: {state.get('step')}")
    
    # Delete user's input message
    try:
        await message.delete()
    except Exception as e:
        print(f"[INDEX-INPUT] Error deleting message: {e}")
    
    # Handle message link input
    if state.get("step") == "await_msg_link":
        msg_id = extract_message_id_from_link(message.text or "")
        
        print(f"[INDEX-INPUT] Extracted message ID: {msg_id}")
        
        if msg_id is None:
            print(f"[INDEX-INPUT] Invalid message ID/link provided")
            return await state["status_msg"].edit_text(
                "❌ **Invalid Input**\n\n"
                "Please send a valid message ID, link, or `0` to index all.\n\n"
                "⏱️ You have 15 minutes to respond.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("❌ Cancel", callback_data="idx_cancel")
                ]])
            )
        
        print(f"[INDEX-INPUT] Valid message ID received, proceeding to indexing")
        
        # Cancel timeout
        if "timeout_task" in state:
            state["timeout_task"].cancel()
        
        # Clear state
        channel_id = state["channel_id"]
        status_msg = state["status_msg"]
        INDEX_STATE.pop(user_id, None)
        
        # Start indexing
        await start_indexing(client, user_id, channel_id, msg_id, status_msg)

async def start_indexing(client: Client, user_id: int, channel_id: int, start_msg_id: int, status_msg: Message):
    """Start the actual indexing process"""
    
    print(f"Starting indexing - Channel: {channel_id}, Start: {start_msg_id}")
    
    # Update status
    await status_msg.edit_text(
        f"🚀 **Indexing Started**\n\n"
        f"Channel: `{channel_id}`\n"
        f"Starting from: `{start_msg_id if start_msg_id > 0 else 'Beginning'}`\n\n"
        f"⏳ Please wait...",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("❌ Cancel", callback_data="idx_cancel")
        ]])
    )
    
    await index_channel(client, user_id, channel_id, start_msg_id, status_msg)

async def index_channel(client: Client, user_id: int, channel_id: int, start_msg_id: int, status_msg: Message):
    """Index videos from the database channel"""
    saved = skipped = duplicates = errors = 0
    start_time = time.time()
    last_update = 0
    
    async with lock:
        try:
            print(f"Starting iteration - Channel: {channel_id}, Offset: {start_msg_id}")
            
            # Iterate through messages using get_chat_history
            async for msg in client.get_chat_history(channel_id, offset_id=start_msg_id if start_msg_id > 0 else 0):
                
                # Check for cancellation
                if CANCEL_INDEX.get(user_id, False):
                    CANCEL_INDEX[user_id] = False
                    await status_msg.edit_text(
                        f"❌ **Indexing Cancelled**\n\n"
                        f"📊 **Statistics:**\n"
                        f"✅ Saved: `{saved}`\n"
                        f"⏭️ Skipped: `{skipped}`\n"
                        f"🔁 Duplicates: `{duplicates}`\n"
                        f"❌ Errors: `{errors}`"
                    )
                    return
                
                # Skip if we're starting from a specific message and haven't reached it yet
                if start_msg_id > 0 and msg.id < start_msg_id:
                    continue
                
                # Only process media messages (video, photo, document, animation)
                if not (msg.video or msg.photo or msg.document or msg.animation):
                    skipped += 1
                    continue
                
                try:
                    video_id = msg.id
                    
                    # Determine duration based on media type
                    if msg.video:
                        duration = msg.video.duration
                    elif msg.animation:
                        duration = msg.animation.duration if msg.animation.duration else 0
                    elif msg.document and msg.document.mime_type and 'video' in msg.document.mime_type:
                        duration = msg.document.duration if msg.document.duration else 0
                    else:
                        duration = 0
                    
                    is_premium = duration > FREE_VIDEO_DURATION
                    
                    # Check if already exists (duplicate check)
                    existing = await mdb.async_video_collection.find_one({"video_id": video_id})
                    if existing:
                        duplicates += 1
                        continue
                    
                    # Save the video
                    await mdb.save_video_id(video_id, duration, is_premium)
                    saved += 1
                    
                except FloodWait as e:
                    print(f"FloodWait: {e.value}s")
                    await asyncio.sleep(e.value)
                except Exception as e:
                    print(f"Error saving video {msg.id}: {e}")
                    errors += 1
                
                # Update status every 5 seconds or every 50 messages
                current_time = time.time()
                if (current_time - last_update) >= 5 or (saved + skipped + duplicates) % 50 == 0:
                    last_update = current_time
                    try:
                        await status_msg.edit_text(
                            f"📊 **Indexing in Progress...**\n\n"
                            f"✅ Saved: `{saved}`\n"
                            f"⏭️ Skipped: `{skipped}`\n"
                            f"🔁 Duplicates: `{duplicates}`\n"
                            f"❌ Errors: `{errors}`\n\n"
                            f"⏱️ Time: `{int(current_time - start_time)}s`",
                            reply_markup=InlineKeyboardMarkup([[
                                InlineKeyboardButton("❌ Cancel", callback_data="idx_cancel")
                            ]])
                        )
                    except MessageNotModified:
                        pass
                    except Exception as e:
                        print(f"Error updating status: {e}")
        
        except FloodWait as e:
            print(f"FloodWait in main loop: {e.value}s")
            await asyncio.sleep(e.value)
        except Exception as e:
            print(f"Indexing error: {e}")
            import traceback
            traceback.print_exc()
            await status_msg.edit_text(
                f"❌ **Indexing Failed**\n\n"
                f"Error: `{str(e)}`\n\n"
                f"📊 **Statistics:**\n"
                f"✅ Saved: `{saved}`\n"
                f"⏭️ Skipped: `{skipped}`\n"
                f"🔁 Duplicates: `{duplicates}`\n"
                f"❌ Errors: `{errors}`"
            )
            return
    
    # Final success message
    elapsed = round(time.time() - start_time, 2)
    
    await status_msg.edit_text(
        f"✅ **Indexing Completed Successfully!**\n\n"
        f"📊 **Final Statistics:**\n"
        f"✅ Saved: `{saved}`\n"
        f"⏭️ Skipped: `{skipped}`\n"
        f"🔁 Duplicates: `{duplicates}`\n"
        f"❌ Errors: `{errors}`\n\n"
        f"⏱️ **Total Time:** `{elapsed}s`\n"
        f"📁 **Channel:** `{channel_id}`"
    )
