from pyrogram import Client, filters
from pyrogram.types import *
from pyrogram.errors import MessageNotModified
from vars import *
from Database.maindb import mdb
from Database.userdb import udb
from datetime import datetime
import pytz, random, asyncio
from .fsub import get_fsub
from Script import text

# Video message cache (user_id: message object)
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
            msg_text = "**✅ First Verification Complete!**\n\n<b>You can now access unlimited videos until midnight (IST)!</b>\n\n<i>After the first timer expires, you'll need to complete the second verification.</i>"
        elif verify_type == "verify2":
            await mdb.update_user(verify_user_id, {"second_time_verified": current_time})
            verify_num = 2
            msg_text = "**✅ Second Verification Complete!**\n\n<b>You can now access unlimited videos until midnight (IST)!</b>\n\n<i>After the second timer expires, you'll need to complete the third verification.</i>"
        elif verify_type == "verify3":
            await mdb.update_user(verify_user_id, {"third_time_verified": current_time})
            verify_num = 3
            msg_text = "**✅ Third Verification Complete!**\n\n<b>You can now access unlimited videos until midnight (IST)!</b>\n\n<i>This is the final verification for today!</i>"
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
            caption_text = ("<b><blockquote>⚠️ This file will auto delete in 5 minutes!</blockquote></b>\n\n")
            
            # Use edit_message if available (for smooth UX)
            if edit_message:
                try:
                    await edit_message.delete()
                except:
                    pass
                    
            dy = await client.copy_message(
                    chat_id=chat_id,
                    from_chat_id=DATABASE_CHANNEL_ID,
                    message_id=random_video["video_id"],
                    caption=caption_text,
                    protect_content=PROTECT_CONTENT,
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔁 Get Again", callback_data="getvideos_cb")]]))
            
            # Cache the message for future edits
            VIDEO_MSG_CACHE[user_id] = dy
            
            await mdb.increment_daily_count(user_id)
            await asyncio.sleep(300)
            try:
                await dy.delete()
            except:
                pass
        except Exception as e:
            print(f"Error sending video: {e}")
            await reply_func("Failed to send video..")
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
                f">Limit will reset every day at 5 AM (IST).**"
            )
            return
        try:
            caption_text = ("<b><blockquote>⚠️ This file will auto delete in 5 minutes!</blockquote></b>\n\n")
            
            if edit_message:
                try:
                    await edit_message.delete()
                except:
                    pass
                    
            dy = await client.copy_message(
                    chat_id=chat_id,
                    from_chat_id=DATABASE_CHANNEL_ID,
                    message_id=random_video["video_id"],
                    caption=caption_text,
                    protect_content=PROTECT_CONTENT,
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔁 Get Again", callback_data="getvideos_cb")]]))
            
            VIDEO_MSG_CACHE[user_id] = dy
            
            await mdb.increment_daily_count(user_id)
            await asyncio.sleep(300)
            try:
                await dy.delete()
            except:
                pass
        except Exception as e:
            print(f"Error sending video: {e}")
            await reply_func("Failed to send video..")
        return
    
    # VERIFICATION ENABLED - Free users
    free_trial_count = db_user.get("free_trial_count", 0)
    
    # Check if user gets free trial videos
    if free_trial_count < FREE_VIDEOS_COUNT:
        videos = await mdb.get_free_videos()
        if not videos:
            await reply_func("No videos available at the moment.")
            return
        random_video = random.choice(videos)
        
        try:
            remaining = FREE_VIDEOS_COUNT - free_trial_count - 1
            caption_text = (
                f"<b><blockquote>⚠️ This file will auto delete in 5 minutes!</blockquote></b>\n\n"
                f"<b>🎁 Free Trial: {free_trial_count + 1}/{FREE_VIDEOS_COUNT}</b>\n"
                f"<b>📝 Remaining Free Videos: {remaining}</b>\n\n"
                f"<i>After {FREE_VIDEOS_COUNT} free videos, you'll need to verify to continue!</i>"
            )
            
            if edit_message:
                try:
                    await edit_message.delete()
                except:
                    pass
                    
            dy = await client.copy_message(
                    chat_id=chat_id,
                    from_chat_id=DATABASE_CHANNEL_ID,
                    message_id=random_video["video_id"],
                    caption=caption_text,
                    protect_content=PROTECT_CONTENT,
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔁 Get Again", callback_data="getvideos_cb")]]))
            
            VIDEO_MSG_CACHE[user_id] = dy
            
            await mdb.increment_free_trial_count(user_id)
            await asyncio.sleep(300)
            try:
                await dy.delete()
            except:
                pass
        except Exception as e:
            print(f"Error sending video: {e}")
            await reply_func("Failed to send video..")
        return
    
    # Free trial exhausted - Check verification status
    user_verified = await mdb.is_user_verified(user_id)
    is_second_shortener = await mdb.use_second_shortener(user_id, VERIFY_EXPIRE_TIME)
    is_third_shortener = await mdb.use_third_shortener(user_id, VERIFY_EXPIRE_TIME)
    
    # Determine which verification to show
    if not user_verified:
        # Need first verification
        verify_hash = encode_string(f"verify_{user_id}_{random.randint(1000, 9999)}")
        await mdb.create_verify_id(user_id, verify_hash)
        
        verify_url = f"https://telegram.me/{(await client.get_me()).username}?start=verify_{user_id}_{verify_hash}"
        shortlink = get_shortlink(verify_url, SHORTENER_API1, SHORTENER_WEBSITE1)
        
        btn = [
            [InlineKeyboardButton("✅ Click Here To Verify", url=shortlink)],
            [InlineKeyboardButton("📚 How To Verify?", url=TUTORIAL1)]
        ]
        
        msg_text = (
            f"<b>🔐 Verification Required (1/3)</b>\n\n"
            f"<b>You've used your {FREE_VIDEOS_COUNT} free videos for today!</b>\n\n"
            f"<b>To continue watching unlimited videos, please complete the verification.</b>\n\n"
            f"<b>⏰ Verification valid until midnight (IST)</b>\n"
            f"<b>💎 Premium users don't need verification!</b>\n\n"
            f"<i>Click the button below to verify:</i>"
        )
        
        if edit_message:
            try:
                await edit_message.edit_text(msg_text, reply_markup=InlineKeyboardMarkup(btn), disable_web_page_preview=True)
            except MessageNotModified:
                pass
        else:
            await reply_func(msg_text, reply_markup=InlineKeyboardMarkup(btn), disable_web_page_preview=True)
        return
        
    elif user_verified and is_second_shortener:
        # Need second verification
        verify_hash = encode_string(f"verify2_{user_id}_{random.randint(1000, 9999)}")
        await mdb.create_verify_id(user_id, verify_hash)
        
        verify_url = f"https://telegram.me/{(await client.get_me()).username}?start=verify2_{user_id}_{verify_hash}"
        shortlink = get_shortlink(verify_url, SHORTENER_API2, SHORTENER_WEBSITE2)
        
        btn = [
            [InlineKeyboardButton("✅ Click Here To Verify", url=shortlink)],
            [InlineKeyboardButton("📚 How To Verify?", url=TUTORIAL2)]
        ]
        
        msg_text = (
            f"<b>🔐 Verification Required (2/3)</b>\n\n"
            f"<b>Your first verification has expired!</b>\n\n"
            f"<b>To continue watching unlimited videos, please complete the second verification.</b>\n\n"
            f"<b>⏰ Verification valid until midnight (IST)</b>\n"
            f"<b>💎 Premium users don't need verification!</b>\n\n"
            f"<i>Click the button below to verify:</i>"
        )
        
        if edit_message:
            try:
                await edit_message.edit_text(msg_text, reply_markup=InlineKeyboardMarkup(btn), disable_web_page_preview=True)
            except MessageNotModified:
                pass
        else:
            await reply_func(msg_text, reply_markup=InlineKeyboardMarkup(btn), disable_web_page_preview=True)
        return
        
    elif user_verified and is_third_shortener:
        # Need third verification
        verify_hash = encode_string(f"verify3_{user_id}_{random.randint(1000, 9999)}")
        await mdb.create_verify_id(user_id, verify_hash)
        
        verify_url = f"https://telegram.me/{(await client.get_me()).username}?start=verify3_{user_id}_{verify_hash}"
        shortlink = get_shortlink(verify_url, SHORTENER_API3, SHORTENER_WEBSITE3)
        
        btn = [
            [InlineKeyboardButton("✅ Click Here To Verify", url=shortlink)],
            [InlineKeyboardButton("📚 How To Verify?", url=TUTORIAL3)]
        ]
        
        msg_text = (
            f"<b>🔐 Verification Required (3/3)</b>\n\n"
            f"<b>Your second verification has expired!</b>\n\n"
            f"<b>To continue watching unlimited videos, please complete the third verification.</b>\n\n"
            f"<b>⏰ Verification valid until midnight (IST)</b>\n"
            f"<b>💎 Premium users don't need verification!</b>\n\n"
            f"<i>Click the button below to verify:</i>"
        )
        
        if edit_message:
            try:
                await edit_message.edit_text(msg_text, reply_markup=InlineKeyboardMarkup(btn), disable_web_page_preview=True)
            except MessageNotModified:
                pass
        else:
            await reply_func(msg_text, reply_markup=InlineKeyboardMarkup(btn), disable_web_page_preview=True)
        return
    
    # User is verified, send video
    videos = await mdb.get_free_videos()
    if not videos:
        await reply_func("No videos available at the moment.")
        return
    random_video = random.choice(videos)
    
    try:
        caption_text = (
            f"<b><blockquote>⚠️ This file will auto delete in 5 minutes!</blockquote></b>\n\n"
            f"<b>✅ Verification Active!</b>\n\n"
            f"<i>Enjoy unlimited videos until midnight!</i>"
        )
        
        if edit_message:
            try:
                await edit_message.delete()
            except:
                pass
                
        dy = await client.copy_message(
                chat_id=chat_id,
                from_chat_id=DATABASE_CHANNEL_ID,
                message_id=random_video["video_id"],
                caption=caption_text,
                protect_content=PROTECT_CONTENT,
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔁 Get Again", callback_data="getvideos_cb")]]))
        
        VIDEO_MSG_CACHE[user_id] = dy
        
        await asyncio.sleep(300)
        try:
            await dy.delete()
        except:
            pass
    except Exception as e:
        print(f"Error sending video: {e}")
        await reply_func("Failed to send video..")

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
