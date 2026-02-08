from pyrogram import Client, filters
from pyrogram.types import *
from pyrogram.errors import MessageNotModified, MessageEmpty, MessageIdInvalid
from vars import *
from Database.maindb import mdb
from Database.userdb import udb
from datetime import datetime
import pytz, random, asyncio
from .fsub import get_fsub
from Script import text

# Video message cache (user_id: {"msg": message_object, "delete_task": task})
VIDEO_MSG_CACHE = {}

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
    """Handle verification callback when user clicks verify link"""
    import pytz
    
    try:
        parts = data.split("_")
        verify_type = parts[0]
        verify_user_id = int(parts[1])
        verify_hash = "_".join(parts[2:])
        
        if message.from_user.id != verify_user_id:
            await message.reply("**⚠️ This verification link is not for you!**")
            return
        
        verify_info = await mdb.get_verify_id_info(verify_user_id, verify_hash)
        if not verify_info:
            await message.reply("**⚠️ Invalid verification link!**")
            return
        
        if verify_info.get("verified"):
            await message.reply("**⚠️ This verification link has already been used!**")
            return
        
        ist_timezone = pytz.timezone('Asia/Kolkata')
        current_time = datetime.now(tz=ist_timezone)
        
        if verify_type == "verify":
            await mdb.update_user(verify_user_id, {"last_verified": current_time})
            verify_num = 1
            from vars import VERIFY_STAGES
            from TechifyBots.verify_utils import format_time_remaining
            expiry_time = format_time_remaining(VERIFY_STAGES[1])
            msg_text = f"**✅ First Verification Complete!**\n\n<b>You can now access unlimited videos for {expiry_time}!</b>\n\n<i>After the first verification expires, you'll need to complete the second verification.</i>"
        elif verify_type == "verify2":
            await mdb.update_user(verify_user_id, {"second_time_verified": current_time})
            verify_num = 2
            from vars import VERIFY_STAGES
            from TechifyBots.verify_utils import format_time_remaining
            expiry_time = format_time_remaining(VERIFY_STAGES[2])
            msg_text = f"**✅ Second Verification Complete!**\n\n<b>You can now access unlimited videos for {expiry_time}!</b>\n\n<i>After the second verification expires, you'll need to complete the third verification.</i>"
        elif verify_type == "verify3":
            await mdb.update_user(verify_user_id, {"third_time_verified": current_time})
            verify_num = 3
            from vars import VERIFY_STAGES
            from TechifyBots.verify_utils import format_time_remaining
            expiry_time = format_time_remaining(VERIFY_STAGES[3])
            msg_text = f"**✅ Third Verification Complete!**\n\n<b>You can now access unlimited videos for {expiry_time}!</b>\n\n<i>This is the final verification for today!</i>"
        else:
            await message.reply("**⚠️ Invalid verification type!**")
            return
        
        await mdb.update_verify_id_info(verify_user_id, verify_hash, {"verified": True})
        
        await message.reply_photo(
            photo=VERIFY_IMG,
            caption=msg_text,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🎥 Get Videos Now", callback_data="getvideos_cb")]
            ])
        )
        
        try:
            await client.send_message(
                LOG_VR_CHANNEL,
                f"**✅ Verification Complete**\n\n"
                f"**User:** {message.from_user.mention}\n"
                f"**User ID:** `{verify_user_id}`\n"
                f"**Verification:** {verify_num}/3\n"
                f"**Time:** {current_time.strftime('%d %B %Y, %I:%M %p IST')}"
            )
        except Exception as e:
            print(f"Error logging verification: {e}")
    
    except Exception as e:
        print(f"Verification error: {e}")
        import traceback
        traceback.print_exc()
        await message.reply("**⚠️ Verification failed! Please try again.**")

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
    """Send new video or edit existing message with new video"""
    
    # Cancel any existing delete task
    cache_entry = VIDEO_MSG_CACHE.get(user_id)
    if cache_entry:
        if cache_entry.get("delete_task"):
            cache_entry["delete_task"].cancel()
    
    existing_msg = cache_entry.get("msg") if cache_entry else None
    
    # Try to edit existing message with new video
    if existing_msg:
        try:
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
            
        except Exception as edit_error:
            print(f"[EDIT-VIDEO] Failed to edit message: {edit_error}")
            # If edit fails, delete old message and send new one
            try:
                await existing_msg.delete()
            except:
                pass
    
    # Send new message (first time or if edit failed)
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
    from .verify_utils import encode_string, get_shortlink
    import pytz
    
    limits = await get_updated_limits()
    if limits.get('maintenance', False):
        await reply_func("**🛠️ Bot Under Maintenance — Back Soon!**")
        return
    
    user_id = user.id
    db_user = await mdb.get_user(user_id)
    plan = db_user.get("plan", "free")
    
    # Premium users bypass verification
    if plan == "prime":
        videos = await mdb.get_all_videos()
        if not videos:
            await reply_func("No videos available at the moment.")
            return
        random_video = random.choice(videos)
        daily_count = db_user.get("daily_count", 0)
        daily_limit = db_user.get("daily_limit", PRIME_LIMIT)
        if daily_count >= daily_limit:
            await reply_func(
                f"**🚫 You've reached your daily limit of {daily_limit} videos.\n\n"
                f">Limit will reset every day at 5 AM (IST).**"
            )
            return
        
        try:
            caption_text = "<b><blockquote>⚠️ This video will auto-delete after 5 minutes of inactivity!</blockquote></b>\n\n"
            
            try:
                await send_or_edit_video(
                    client=client,
                    user_id=user_id,
                    chat_id=chat_id,
                    video_id=random_video["video_id"],
                    caption=caption_text,
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔁 Get Next Video", callback_data="getvideos_cb")]])
                )
            except Exception as send_error:
                print(f"[VIDEO-LOGIC] Failed to send video, trying another: {send_error}")
                await reply_func(f"**⚠️ Video unavailable, trying another...**")
                await send_random_video_logic(client, user, chat_id, reply_func, edit_message=None)
                return
            
            await mdb.increment_daily_count(user_id)
            
        except Exception as e:
            print(f"[VIDEO-LOGIC] Error in premium flow: {e}")
            import traceback
            traceback.print_exc()
            await reply_func("Failed to send video.")
        return
    
    # Free users - Check verification system
    if not IS_VERIFY:
        videos = await mdb.get_free_videos()
        if not videos:
            await reply_func("No videos available at the moment.")
            return
        random_video = random.choice(videos)
        daily_count = db_user.get("daily_count", 0)
        daily_limit = db_user.get("daily_limit", FREE_LIMIT)
        if daily_count >= daily_limit:
            await reply_func(
                f"**🚫 You've reached your daily limit of {daily_limit} videos.\n\n"
                f">Limit will reset every day at 5 AM (IST).**",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🍿 Buy Subscription 🍾", callback_data="pro")]])
            )
            return
        
        try:
            caption_text = (
                f"<b><blockquote>⚠️ This video will auto-delete after 5 minutes of inactivity!</blockquote></b>\n\n"
                f"<b>🆓 Free Video</b>\n\n"
                f"<b>📊 Today Used: {daily_count + 1}/{daily_limit}</b>\n"
                f"<b>📝 Remaining: {daily_limit - daily_count - 1}</b>"
            )
            
            try:
                await send_or_edit_video(
                    client=client,
                    user_id=user_id,
                    chat_id=chat_id,
                    video_id=random_video["video_id"],
                    caption=caption_text,
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔁 Get Next Video", callback_data="getvideos_cb")]])
                )
            except Exception as send_error:
                print(f"[VIDEO-LOGIC] Failed to send video, trying another: {send_error}")
                await reply_func(f"**⚠️ Video unavailable, trying another...**")
                await send_random_video_logic(client, user, chat_id, reply_func, edit_message=None)
                return
            
            await mdb.increment_daily_count(user_id)
            
        except Exception as e:
            print(f"[VIDEO-LOGIC] Error in free flow: {e}")
            import traceback
            traceback.print_exc()
            await reply_func("Failed to send video.")
        return
    
    # Verification-based free user flow
    free_trial_count = db_user.get("free_trial_count", 0)
    
    # Allow first N free videos without verification
    if free_trial_count < FREE_VIDEOS_COUNT:
        videos = await mdb.get_free_videos()
        if not videos:
            await reply_func("No videos available at the moment.")
            return
        random_video = random.choice(videos)
        
        try:
            remaining = FREE_VIDEOS_COUNT - free_trial_count - 1
            caption_text = (
                f"<b><blockquote>⚠️ This video will auto-delete after 5 minutes of inactivity!</blockquote></b>\n\n"
                f"<b>🎁 Free Trial: {free_trial_count + 1}/{FREE_VIDEOS_COUNT}</b>\n"
                f"<b>📝 Remaining: {remaining}</b>\n\n"
                f"<i>After {FREE_VIDEOS_COUNT} videos, verify to continue!</i>"
            )
            
            try:
                await send_or_edit_video(
                    client=client,
                    user_id=user_id,
                    chat_id=chat_id,
                    video_id=random_video["video_id"],
                    caption=caption_text,
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔁 Get Next Video", callback_data="getvideos_cb")]])
                )
            except Exception as send_error:
                print(f"[VIDEO-LOGIC] Failed to send video, trying another: {send_error}")
                await reply_func(f"**⚠️ Video unavailable, trying another...**")
                await send_random_video_logic(client, user, chat_id, reply_func, edit_message=None)
                return
            
            await mdb.increment_free_trial_count(user_id)
            
        except Exception as e:
            print(f"[VIDEO-LOGIC] Error in free trial flow: {e}")
            import traceback
            traceback.print_exc()
            await reply_func("Failed to send video.")
        return
    
    # Free trial exhausted - Check verification status
    # Check which verifications are currently valid
    first_valid = await mdb.is_user_verified(user_id)
    second_valid = await mdb.user_verified(user_id)
    third_valid = await mdb.third_verified(user_id)
    
    # Check which verification is needed
    need_second = await mdb.use_second_shortener(user_id, VERIFY_EXPIRE_TIME)
    need_third = await mdb.use_third_shortener(user_id, VERIFY_EXPIRE_TIME)
    
    # Priority: If any verification is valid, send video
    if third_valid or second_valid or first_valid:
        # User has a valid verification, send video
        videos = await mdb.get_free_videos()
        if not videos:
            await reply_func("No videos available at the moment.")
            return
        random_video = random.choice(videos)
        
        try:
            # Determine which verification is active
            if third_valid:
                verify_msg = "<b>✅ Third Verification Active!</b>"
            elif second_valid:
                verify_msg = "<b>✅ Second Verification Active!</b>"
            else:
                verify_msg = "<b>✅ First Verification Active!</b>"
            
            caption_text = (
                f"<b><blockquote>⚠️ This video will auto-delete after 5 minutes of inactivity!</blockquote></b>

"
                f"{verify_msg}

"
                f"<i>Enjoy unlimited videos until verification expires!</i>"
            )
            
            try:
                await send_or_edit_video(
                    client=client,
                    user_id=user_id,
                    chat_id=chat_id,
                    video_id=random_video["video_id"],
                    caption=caption_text,
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔁 Get Next Video", callback_data="getvideos_cb")]])
                )
            except Exception as send_error:
                print(f"[VIDEO-LOGIC] Failed to send video, trying another: {send_error}")
                await reply_func(f"**⚠️ Video unavailable, trying another...**")
                await send_random_video_logic(client, user, chat_id, reply_func, edit_message=None)
                return
            
        except Exception as e:
            print(f"[VIDEO-LOGIC] Error in verified flow: {e}")
            import traceback
            traceback.print_exc()
            await reply_func("Failed to send video.")
        return
    
    # No valid verification - determine which verification to show
    if need_third:
        # Need third verification
        verify_hash = encode_string(f"verify3_{user_id}_{random.randint(1000, 9999)}")
        await mdb.create_verify_id(user_id, verify_hash)
        
        verify_url = f"https://telegram.me/{(await client.get_me()).username}?start=verify3_{user_id}_{verify_hash}"
        shortlink = get_shortlink(verify_url, SHORTENER_API3, SHORTENER_WEBSITE3)
        
        btn = [
            [InlineKeyboardButton("✅ Click Here To Verify", url=shortlink)],
            [InlineKeyboardButton("📚 How To Verify?", url=TUTORIAL3)]
        ]
        
        from vars import VERIFY_STAGES
        from TechifyBots.verify_utils import format_time_remaining
        
        msg_text = (
            f"<b>🔐 Verification Required (3/3)</b>

"
            f"<b>Second verification expired!</b>

"
            f"<b>Complete final verification to continue.</b>

"
            f"<b>⏰ Valid for: {format_time_remaining(VERIFY_STAGES[3])}</b>
"
            f"<b>💎 Premium users skip verification!</b>"
        )
        
        await reply_func(msg_text, reply_markup=InlineKeyboardMarkup(btn), disable_web_page_preview=True)
        return
        
    elif need_second:
        # Need second verification
        verify_hash = encode_string(f"verify2_{user_id}_{random.randint(1000, 9999)}")
        await mdb.create_verify_id(user_id, verify_hash)
        
        verify_url = f"https://telegram.me/{(await client.get_me()).username}?start=verify2_{user_id}_{verify_hash}"
        shortlink = get_shortlink(verify_url, SHORTENER_API2, SHORTENER_WEBSITE2)
        
        btn = [
            [InlineKeyboardButton("✅ Click Here To Verify", url=shortlink)],
            [InlineKeyboardButton("📚 How To Verify?", url=TUTORIAL2)]
        ]
        
        from vars import VERIFY_STAGES
        from TechifyBots.verify_utils import format_time_remaining
        
        msg_text = (
            f"<b>🔐 Verification Required (2/3)</b>

"
            f"<b>First verification expired!</b>

"
            f"<b>Complete 2nd verification to continue.</b>

"
            f"<b>⏰ Valid for: {format_time_remaining(VERIFY_STAGES[2])}</b>
"
            f"<b>💎 Premium users skip verification!</b>"
        )
        
        await reply_func(msg_text, reply_markup=InlineKeyboardMarkup(btn), disable_web_page_preview=True)
        return
        
    else:
        # Need first verification
        verify_hash = encode_string(f"verify_{user_id}_{random.randint(1000, 9999)}")
        await mdb.create_verify_id(user_id, verify_hash)
        
        verify_url = f"https://telegram.me/{(await client.get_me()).username}?start=verify_{user_id}_{verify_hash}"
        shortlink = get_shortlink(verify_url, SHORTENER_API1, SHORTENER_WEBSITE1)
        
        btn = [
            [InlineKeyboardButton("✅ Click Here To Verify", url=shortlink)],
            [InlineKeyboardButton("📚 How To Verify?", url=TUTORIAL1)]
        ]
        
        from vars import VERIFY_STAGES
        from TechifyBots.verify_utils import format_time_remaining
        
        msg_text = (
            f"<b>🔐 Verification Required (1/3)</b>

"
            f"<b>You've used your {FREE_VIDEOS_COUNT} free videos!</b>

"
            f"<b>Complete verification for unlimited access.</b>

"
            f"<b>⏰ Valid for: {format_time_remaining(VERIFY_STAGES[1])}</b>
"
            f"<b>💎 Premium users skip verification!</b>"
        )
        
        await reply_func(msg_text, reply_markup=InlineKeyboardMarkup(btn), disable_web_page_preview=True)
        return


@Client.on_message(filters.command("getvideos") & filters.private)
async def send_random_video(client: Client, message: Message):
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
