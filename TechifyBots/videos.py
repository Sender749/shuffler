from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from verification import handle_video_request, send_verification_message
from database import db
from vars import *
import random

# Command handler for /getvideos
@Client.on_message(filters.private & filters.command(["getvideos", "getvideo"]))
async def get_videos_command(client: Client, message: Message):
    """Handle /getvideos command with verification"""
    user_id = message.from_user.id
    
    # Check access with verification
    can_send = await handle_video_request(client, message)
    
    if not can_send:
        return
    
    # If we reach here, user can access video
    # Send random video from database channels
    await send_random_video(client, message)

@Client.on_callback_query(filters.regex(r"^get_videos$"))
async def get_videos_callback(client, callback_query):
    """Handle get videos button"""
    user_id = callback_query.from_user.id
    
    # Check access
    can_send = await handle_video_request(client, callback_query.message)
    
    if not can_send:
        await callback_query.answer()
        return
    
    await callback_query.message.delete()
    await send_random_video(client, callback_query.message)
    await callback_query.answer()

async def send_random_video(client, message):
    """Send random video from database channels"""
    user_id = message.from_user.id if hasattr(message, 'from_user') else message.chat.id
    
    try:
        # Get random video from database channels
        # For now, we'll forward a random message from the database channel
        
        if not DATABASE_CHANNEL_IDS:
            await message.reply("❌ No videos available in database.")
            return
        
        # Try to get a random message from database channels
        import random
        channel_id = random.choice(DATABASE_CHANNEL_IDS)
        
        # Get recent messages (this is a simplified approach)
        # In production, you should store video IDs in database
        try:
            # Forward a random message
            # Note: In real implementation, you should query your video database
            # and forward specific messages by ID
            
            # Placeholder: Send a message indicating video should be sent
            await message.reply(
                "🎬 <b>Here is your video!</b>\n\n"
                "Enjoy your content. Use /getvideos for more.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🎬 Get Another", callback_data="get_videos")],
                    [InlineKeyboardButton("📊 My Plan", callback_data="my_plan")]
                ])
            )
            
            # Log video sent
            if LOG_CHNL:
                user = message.from_user if hasattr(message, 'from_user') else None
                if user:
                    log_text = f"""
🎬 <b>Video Sent</b>

👤 User: {user.mention}
🆔 ID: <code>{user_id}</code>
📊 Type: {"Premium" if db.get_user(user_id).get("is_premium") else "Free/Verified"}
"""
                    await client.send_message(LOG_CHNL, log_text)
                    
        except Exception as e:
            print(f"Error sending video: {e}")
            await message.reply("❌ Error retrieving video. Please try again.")
            
    except Exception as e:
        print(f"Error in send_random_video: {e}")
        await message.reply("❌ An error occurred. Please try again.")

# My Plan command
@Client.on_message(filters.private & filters.command("myplan"))
async def my_plan_command(client, message):
    """Show user's current plan"""
    user_id = message.from_user.id
    user_data = db.get_user(user_id)
    
    text = "📊 <b>Your Plan Details</b>\n\n"
    
    # Premium status
    if user_data.get("is_premium"):
        expiry = user_data.get("premium_expiry")
        if expiry:
            if isinstance(expiry, str):
                from datetime import datetime
                expiry = datetime.fromisoformat(expiry)
            expiry_text = expiry.strftime("%d %B, %Y")
        else:
            expiry_text = "Lifetime"
        
        text += f"""
💎 <b>Status:</b> Premium Member
⏰ <b>Expires:</b> {expiry_text}
🎬 <b>Access:</b> Unlimited Videos
✅ <b>Verification:</b> Not Required
"""
    else:
        # Check verification
        verified_until = user_data.get("verified_until")
        stage = user_data.get("verification_stage", 0)
        
        if verified_until and isinstance(verified_until, str):
            from datetime import datetime
            verified_until = datetime.fromisoformat(verified_until)
        
        now = __import__('datetime').datetime.now(__import__('pytz').timezone("Asia/Kolkata"))
        
        if verified_until and verified_until > now:
            time_left = verified_until - now
            hours_left = time_left.seconds // 3600
            minutes_left = (time_left.seconds % 3600) // 60
            
            text += f"""
🔐 <b>Status:</b> Verified (Stage {stage})
⏰ <b>Expires:</b> {verified_until.strftime("%d %B, %Y %I:%M %p")}
🕐 <b>Time Left:</b> {hours_left}h {minutes_left}m
🎬 <b>Access:</b> Unlimited Videos
"""
        else:
            # Free user
            free_used = user_data.get("free_videos_used", 0)
            remaining = max(0, FREE_DAILY_LIMIT - free_used)
            
            text += f"""
🆓 <b>Status:</b> Free User
📊 <b>Daily Limit:</b> {FREE_DAILY_LIMIT} videos
✅ <b>Used Today:</b> {free_used}
🎁 <b>Remaining:</b> {remaining}
"""
            
            if remaining == 0:
                text += "\n⚠️ <b>You've used all free videos!</b>\nComplete verification for unlimited access."
    
    text += f"\n\n<blockquote>🔄 Resets daily at midnight IST</blockquote>"
    
    buttons = []
    if not user_data.get("is_premium"):
        if not (verified_until and verified_until > now):
            buttons.append([InlineKeyboardButton("🔐 Verify Now", callback_data="start_verify")])
        buttons.append([InlineKeyboardButton("💎 Upgrade to Premium", callback_data="premium_info")])
    
    await message.reply(text, reply_markup=InlineKeyboardMarkup(buttons) if buttons else None)

@Client.on_callback_query(filters.regex(r"^my_plan$"))
async def my_plan_callback(client, callback_query):
    """Handle my plan button"""
    await my_plan_command(client, callback_query.message)
    await callback_query.answer()

