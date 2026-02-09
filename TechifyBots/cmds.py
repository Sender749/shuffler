from pyrogram import Client, filters
from pyrogram.types import *
from pyrogram.types import InputMediaVideo, InputMediaPhoto, InputMediaDocument, InputMediaAnimation
from pyrogram.errors import MessageNotModified, MessageEmpty, MessageIdInvalid
from vars import *
from Database.maindb import mdb
from Database.userdb import udb
import random, asyncio, base64
from .fsub import get_fsub
from Script import text
import requests
from urllib.parse import quote

# Video message cache (user_id: {"msg": message_object, "delete_task": task})
VIDEO_MSG_CACHE = {}

def encode_string(text: str):
    return base64.urlsafe_b64encode(text.encode()).decode()

def get_shortlink(url, api, website):
    """Generate shortlink using the shortener API"""
    try:
        # Format: https://website.com/api?api=API_KEY&url=ENCODED_URL
        encoded_url = quote(url, safe='')
        shortlink_url = f"https://{website}/api?api={api}&url={encoded_url}"
        
        print(f"[SHORTENER] Requesting: {shortlink_url[:100]}...")
        
        # Make request to shortener API
        response = requests.get(shortlink_url, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        # Different shorteners return data differently
        if 'shortenedUrl' in data:
            result = data['shortenedUrl']
        elif 'shortlink' in data:
            result = data['shortlink']
        elif 'short_url' in data:
            result = data['short_url']
        elif 'url' in data:
            result = data['url']
        else:
            print(f"[SHORTENER] Unexpected response format: {data}")
            return url
        
        print(f"[SHORTENER] Success: {result}")
        return result
            
    except Exception as e:
        print(f"[SHORTENER] Error creating shortlink: {e}")
        return url
            
async def get_updated_limits():
        global FREE_LIMIT, PRIME_LIMIT
        limits = await mdb.get_global_limits()
        FREE_LIMIT = limits["free_limit"]
        PRIME_LIMIT = limits["prime_limit"]
        return limits

@Client.on_message(filters.command("start") & filters.private)
async def start_command(client, message):
    # Handle verification callback
    if len(message.command) > 1:
        data = message.command[1]
        if data.startswith('verify'):
            await handle_verification(client, message, data)
            return
    
    if await udb.is_user_banned(message.from_user.id):
        await message.reply("**🚫 You are banned from using this bot**",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Support 🧑‍💻", url=f"https://t.me/{ADMIN_USERNAME}")]]))
        return
    if IS_FSUB and not await get_fsub(client, message):return
    if await udb.get_user(message.from_user.id) is None:
        await udb.addUser(message.from_user.id, message.from_user.first_name)
        bot = await client.get_me()
        await client.send_message(
            LOG_CHNL,
            text.LOG.format(
                message.from_user.id,
                getattr(message.from_user, "dc_id", "N/A"),
                message.from_user.first_name or "N/A",
                f"@{message.from_user.username}" if message.from_user.username else "N/A",
                bot.username
            )
        )
    await message.reply_photo(
        photo=random.choice(PICS),
        caption=text.START.format(message.from_user.mention),
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🎥 Get More Videos", callback_data="getvideos_cb")],
            [InlineKeyboardButton("🍿 𝖡𝗎𝗒 𝖲𝗎𝖻𝗌𝖼𝗋𝗂𝗉𝗍𝗂𝗈𝗇 🍾", callback_data="pro")],
            [InlineKeyboardButton("ℹ️ 𝖠𝖻𝗈𝗎𝗍", callback_data="about"),
             InlineKeyboardButton("📚 𝖧𝖾𝗅𝗉", callback_data="help")] 
        ])
    )

async def handle_verification(client: Client, message: Message, data: str):
    """Handle verification link callback"""
    try:
        # Parse: verify1_USER_ID_HASH or verify2_USER_ID_HASH or verify3_USER_ID_HASH
        parts = data.split("_")
        
        if len(parts) < 3:
            await message.reply("⚠️ Invalid verification link format!")
            return
        
        verify_type = parts[0]  # verify1, verify2, or verify3
        verify_user_id = int(parts[1])
        verify_hash = "_".join(parts[2:])  # Rejoin in case hash contains underscores
        
        print(f"[VERIFY] Type: {verify_type}, User: {verify_user_id}, Hash: {verify_hash}")
        
        # Check if the link is for this user
        if message.from_user.id != verify_user_id:
            await message.reply("⚠️ This verification link is not for you!")
            return
        
        # Determine stage
        if verify_type in ["verify", "verify1"]:
            stage = 1
        elif verify_type == "verify2":
            stage = 2
        elif verify_type == "verify3":
            stage = 3
        else:
            await message.reply("⚠️ Invalid verification type!")
            return
        
        # Verify the hash is valid
        verify_info = await mdb.get_verify_id_info(verify_user_id, verify_hash)
        if not verify_info:
            await message.reply("⚠️ Invalid or expired verification link!")
            return
        
        # Mark as verified
        await mdb.update_verify_id_info(verify_user_id, verify_hash, {"verified": True})
        
        # Set the verification timer
        duration = VERIFY_STAGES[stage]
        await mdb.set_verify_timer(verify_user_id, stage, duration)
        
        print(f"[TIMER] User {verify_user_id} verified stage {stage} for {duration}s")
        
        # Send success message
        hours = duration // 3600
        minutes = (duration % 3600) // 60
        time_text = f"{hours}h {minutes}m" if hours > 0 else f"{minutes}m"
        
        await message.reply_photo(
            photo=VERIFY_IMG,
            caption=(
                f"✅ **Verification Stage {stage} Completed!**\n\n"
                f"⏱ Valid for: **{time_text}**\n"
                f"🎬 Unlimited videos until timer expires!\n\n"
                f"<blockquote>Click below to start watching</blockquote>"
            ),
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🎥 Get Videos Now", callback_data="getvideos_cb")]
            ])
        )
        
        # Log to verification channel
        try:
            await client.send_message(
                LOG_VR_CHANNEL,
                f"✅ **Verification Complete**\n\n"
                f"👤 User: {message.from_user.mention}\n"
                f"🆔 ID: `{verify_user_id}`\n"
                f"📊 Stage: {stage}/3\n"
                f"⏱️ Duration: {time_text}"
            )
        except:
            pass
            
    except Exception as e:
        print(f"[VERIFY-ERROR] {e}")
        import traceback
        traceback.print_exc()
        await message.reply("⚠️ Verification failed! Please try again.")

async def auto_delete_video(user_id: int, message: Message, delay: int = 300):
    """Auto delete video after delay if no new request comes"""
    try:
        await asyncio.sleep(delay)
        
        # Check if this is still the current message (not replaced)
        cache_entry = VIDEO_MSG_CACHE.get(user_id)
        if cache_entry and cache_entry.get("msg") and cache_entry["msg"].id == message.id:
            print(f"[AUTO-DELETE] Deleting video for user {user_id} after {delay}s of inactivity")
            try:
                await message.delete()
                # Send deletion notice
                await message.reply_text(
                    "**⏱️ Video Deleted Due to Inactivity**\n\n"
                    "<i>Click below to get more videos!</i>",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🎥 Get More Videos", callback_data="getvideos_cb")
                    ]])
                )
            except:
                pass
            VIDEO_MSG_CACHE.pop(user_id, None)
    except asyncio.CancelledError:
        print(f"[AUTO-DELETE] Delete task cancelled for user {user_id} (new request received)")
    except Exception as e:
        print(f"[AUTO-DELETE] Error in auto_delete_video: {e}")

async def send_or_edit_video(client: Client, user_id: int, chat_id: int, video_id: int, caption: str, reply_markup):
    """Send new video or edit existing message with new video - FIXED to handle deleted messages"""
    
    # Cancel any existing delete task
    cache_entry = VIDEO_MSG_CACHE.get(user_id)
    if cache_entry:
        if cache_entry.get("delete_task"):
            cache_entry["delete_task"].cancel()
    
    existing_msg = cache_entry.get("msg") if cache_entry else None
    
    # Check if message still exists before trying to edit
    if existing_msg:
        try:
            # Test if message still exists by trying to get it
            try:
                await client.get_messages(chat_id, existing_msg.id)
                message_exists = True
            except:
                message_exists = False
                print(f"[EDIT-VIDEO] Message {existing_msg.id} no longer exists (user deleted it)")
            
            if message_exists:
                print(f"[EDIT-VIDEO] Attempting to edit message {existing_msg.id} with new video {video_id}")
                
                # Get the media from the database channel
                source_msg = await client.get_messages(DATABASE_CHANNEL_ID, video_id)
                
                if not source_msg or not (source_msg.video or source_msg.photo or source_msg.document or source_msg.animation):
                    raise Exception(f"Source message {video_id} has no media")
                
                # Determine media type and edit accordingly
                if source_msg.video:
                    media = InputMediaVideo(media=source_msg.video.file_id, caption=caption)
                elif source_msg.animation:
                    media = InputMediaAnimation(media=source_msg.animation.file_id, caption=caption)
                elif source_msg.document:
                    media = InputMediaDocument(media=source_msg.document.file_id, caption=caption)
                elif source_msg.photo:
                    media = InputMediaPhoto(media=source_msg.photo.file_id, caption=caption)
                else:
                    raise Exception("Unsupported media type")
                
                # Edit the message media
                edited_msg = await existing_msg.edit_media(media=media, reply_markup=reply_markup)
                print(f"[EDIT-VIDEO] Successfully edited message with new video")
                
                # Update cache with edited message
                VIDEO_MSG_CACHE[user_id] = {
                    "msg": edited_msg,
                    "delete_task": asyncio.create_task(auto_delete_video(user_id, edited_msg))
                }
                
                return edited_msg
            else:
                # Message was deleted by user, need to send new one
                print(f"[EDIT-VIDEO] Message was deleted, sending new message instead")
                
        except Exception as edit_error:
            print(f"[EDIT-VIDEO] Failed to edit message: {edit_error}")
            # If edit fails, try to delete old message and send new one
            try:
                await existing_msg.delete()
            except:
                pass
    
    # Send new message (first time, if edit failed, or if message was deleted)
    print(f"[SEND-VIDEO] Sending new video message {video_id}")
    try:
        new_msg = await client.copy_message(
            chat_id=chat_id,
            from_chat_id=DATABASE_CHANNEL_ID,
            message_id=video_id,
            caption=caption,
            protect_content=PROTECT_CONTENT,
            reply_markup=reply_markup
        )
        
        # Cache the new message with auto-delete task
        VIDEO_MSG_CACHE[user_id] = {
            "msg": new_msg,
            "delete_task": asyncio.create_task(auto_delete_video(user_id, new_msg))
        }
        
        return new_msg
        
    except MessageEmpty:
        print(f"[SEND-VIDEO] ERROR: Video {video_id} is empty or deleted")
        await mdb.mark_video_as_invalid(video_id)
        raise Exception("Video file not found in database channel")
    except Exception as e:
        print(f"[SEND-VIDEO] ERROR: {e}")
        raise

async def send_random_video_logic(client: Client, user, chat_id, reply_func, edit_message=None):
    """Main logic for sending videos with verification system"""
    limits = await get_updated_limits()
    if limits.get('maintenance', False):
        await reply_func("**🛠️ Bot Under Maintenance — Back Soon!**")
        return
    
    user_id = user.id
    db_user = await mdb.get_user(user_id)
    plan = db_user.get("plan", "free")
    
    print(f"[VIDEO-LOGIC] User {user_id} requesting video, plan: {plan}")

    # ================= PREMIUM USER =================
    if plan == "prime":
        # Premium users get unlimited videos without verification
        videos = await mdb.get_all_videos()
        if not videos:
            await reply_func("❌ No videos available at the moment.")
            return

        random_video = random.choice(videos)
        
        caption_text = (
            f"<b><blockquote>⚠️ This video will auto-delete after 5 minutes of inactivity!</blockquote></b>\n\n"
            f"<b>💎 Premium User - Unlimited Access!</b>\n"
            f"<i>No verification needed</i>"
        )

        await send_or_edit_video(
            client=client,
            user_id=user_id,
            chat_id=chat_id,
            video_id=random_video["video_id"],
            caption=caption_text,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔁 Get Next Video", callback_data="getvideos_cb")]])
        )

        return


    # ================= FREE USER WITH TIMER VERIFICATION SYSTEM =================

    # Check if user has active verification timer
    is_valid, stage = await mdb.get_verify_status(user_id)

    print(f"[TIMER] User {user_id}: valid={is_valid}, stage={stage}")

    # ---- USER IS VERIFIED (TIMER ACTIVE) ----
    if is_valid:
        # User is verified, give unlimited access until timer expires
        videos = await mdb.get_all_videos()
        if not videos:
            await reply_func("❌ No videos available at the moment.")
            return

        random_video = random.choice(videos)

        # Get remaining time
        user_data = await mdb.get_user(user_id)
        expire = user_data.get("verify_expire", 0)
        import time as time_module
        remaining_seconds = max(0, expire - int(time_module.time()))
        
        hours = remaining_seconds // 3600
        minutes = (remaining_seconds % 3600) // 60
        
        if hours > 0:
            time_left = f"{hours}h {minutes}m"
        else:
            time_left = f"{minutes}m"

        caption_text = (
            f"<b>✅ Verified - Stage {stage}/3</b>\n"
            f"<b>⏱️ Time Left: {time_left}</b>\n"
            f"<i>Unlimited access until timer ends!</i>\n\n"
            f"<b><blockquote>⚠️ This video will auto-delete after 5 minutes of inactivity!</blockquote></b>"
        )

        await send_or_edit_video(
            client=client,
            user_id=user_id,
            chat_id=chat_id,
            video_id=random_video["video_id"],
            caption=caption_text,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔁 Get Next Video", callback_data="getvideos_cb")]])
        )

        return


    # ---- NOT VERIFIED → CHECK FREE TRIAL ----

    free_trial_count = db_user.get("free_trial_count", 0)
    print(f"[VIDEO-LOGIC] Free trial count: {free_trial_count}/{FREE_VIDEOS_COUNT}")

    if free_trial_count < FREE_VIDEOS_COUNT:
        # Give free trial videos
        print(f"[VIDEO-LOGIC] Sending free trial video {free_trial_count + 1}/{FREE_VIDEOS_COUNT}")

        videos = await mdb.get_all_videos()
        if not videos:
            await reply_func("❌ No videos available at the moment.")
            return

        random_video = random.choice(videos)

        remaining = FREE_VIDEOS_COUNT - free_trial_count - 1

        caption_text = (
            f"<b><blockquote>⚠️ This video will auto-delete after 5 minutes of inactivity!</blockquote></b>\n\n"
            f"<b>🎁 Free Trial: {free_trial_count + 1}/{FREE_VIDEOS_COUNT}</b>\n"
            f"<b>📝 Remaining: {remaining}</b>\n\n"
            f"<i>After {FREE_VIDEOS_COUNT} videos, verify to continue!</i>"
        )

        await send_or_edit_video(
            client=client,
            user_id=user_id,
            chat_id=chat_id,
            video_id=random_video["video_id"],
            caption=caption_text,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔁 Get Next Video", callback_data="getvideos_cb")]])
        )

        # Increment free trial count
        await mdb.increment_free_trial_count(user_id)
        return


    # ================= NEED VERIFICATION =================
    
    # User has exhausted free videos and has no active verification
    # Determine which stage they need next
    next_stage = await mdb.next_stage(user_id)
    print(f"[TIMER] User {user_id} needs verification stage {next_stage}")
    
    # Create verification hash
    verify_hash = encode_string(f"verify{next_stage}_{user_id}_{random.randint(1000,9999)}")
    await mdb.create_verify_id(user_id, verify_hash)
    
    # Create verification URL
    bot_username = (await client.get_me()).username
    verify_url = f"https://telegram.me/{bot_username}?start=verify{next_stage}_{user_id}_{verify_hash}"
    
    # Get appropriate shortener for this stage
    if next_stage == 1:
        shortlink = get_shortlink(verify_url, SHORTENER_API1, SHORTENER_WEBSITE1)
        tutorial = TUTORIAL1
        duration = VERIFY_STAGES[1]
    elif next_stage == 2:
        shortlink = get_shortlink(verify_url, SHORTENER_API2, SHORTENER_WEBSITE2)
        tutorial = TUTORIAL2
        duration = VERIFY_STAGES[2]
    else:  # stage 3
        shortlink = get_shortlink(verify_url, SHORTENER_API3, SHORTENER_WEBSITE3)
        tutorial = TUTORIAL3
        duration = VERIFY_STAGES[3]
    
    # Calculate duration display
    hours = duration // 3600
    minutes = (duration % 3600) // 60
    
    if hours > 0:
        duration_text = f"{hours}h {minutes}m"
    else:
        duration_text = f"{minutes}m"
    
    btn = [
        [InlineKeyboardButton("✅ Click Here To Verify", url=shortlink)],
        [InlineKeyboardButton("📚 How To Verify?", url=tutorial)]
    ]
    
    await reply_func(
        f"<b>🔐 Verification Required (Stage {next_stage}/3)</b>\n\n"
        f"<b>⏱️ Duration: {duration_text}</b>\n"
        f"<b>🎬 Benefit: Unlimited videos!</b>\n\n"
        f"<i>Complete verification to continue watching.</i>\n\n"
        f"<blockquote>Your free trial of {FREE_VIDEOS_COUNT} videos has ended.\n"
        f"Verify to get unlimited access for {duration_text}!</blockquote>",
        reply_markup=InlineKeyboardMarkup(btn),
        disable_web_page_preview=True
    )
    return

@Client.on_message(filters.command("getvideos") & filters.private)
async def send_random_video(client: Client, message: Message):
    """Command to get random videos"""
    if await udb.is_user_banned(message.from_user.id):
        await message.reply(
            "**🚫 You are banned from using this bot**",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Support 🧑‍💻", url=f"https://t.me/{ADMIN_USERNAME}")]]))
        return
    if IS_FSUB and not await get_fsub(client, message):
        return
    await send_random_video_logic(
        client=client,
        user=message.from_user,
        chat_id=message.chat.id,
        reply_func=message.reply_text
    )
